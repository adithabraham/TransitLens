import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database.db"
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS timetables (id INTEGER PRIMARY KEY, filename TEXT NOT NULL, stored_name TEXT, upload_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'uploaded');
        CREATE TABLE IF NOT EXISTS routes (id INTEGER PRIMARY KEY, timetable_id INTEGER NOT NULL REFERENCES timetables(id) ON DELETE CASCADE, route_number TEXT NOT NULL, route_name TEXT, source TEXT, destination TEXT);
        CREATE TABLE IF NOT EXISTS schedule (id INTEGER PRIMARY KEY, route_id INTEGER NOT NULL REFERENCES routes(id) ON DELETE CASCADE, stop TEXT, departure_time TEXT, arrival_time TEXT, day TEXT);
        """)


def row_dict(row):
    return dict(row) if row else None


def create_timetable(filename, stored_name):
    with connection() as conn:
        cursor = conn.execute("INSERT INTO timetables(filename, stored_name, upload_date, status) VALUES (?, ?, ?, ?)", (filename, stored_name, datetime.now(timezone.utc).isoformat(), "uploaded"))
        return cursor.lastrowid


def seed_demo_data():
    with connection() as conn:
        if conn.execute("SELECT 1 FROM timetables WHERE filename = 'demo-nilambur-timetable.pdf'").fetchone():
            return
        timetable_id = conn.execute("INSERT INTO timetables(filename, stored_name, upload_date, status) VALUES (?, ?, ?, ?)", ("demo-nilambur-timetable.pdf", "", datetime.now(timezone.utc).isoformat(), "verified")).lastrowid
        routes = [("101", "Nilambur - Kozhikode", "Nilambur", "Kozhikode"), ("202", "Kochi - Thrissur", "Kochi", "Thrissur"), ("303", "Palakkad - Coimbatore", "Palakkad", "Coimbatore")]
        schedule_data = [[("08:00", "10:15"), ("09:15", "11:30"), ("10:30", "12:45"), ("12:00", "14:15"), ("14:15", "16:30"), ("16:30", "18:45")], [("06:20", "07:45"), ("08:10", "09:35"), ("11:00", "12:25"), ("15:30", "16:55"), ("18:00", "19:25")], [("07:15", "08:40"), ("10:00", "11:25"), ("13:45", "15:10"), ("17:20", "18:45")]]
        stops = [["Edakkara", "Vazhikkadavu", "Perinthalmanna"], ["Aluva", "Angamaly", "Chalakudy"], ["Ottapalam", "Shoranur", "Pollachi"]]
        for index, route in enumerate(routes):
            route_id = conn.execute("INSERT INTO routes(timetable_id, route_number, route_name, source, destination) VALUES (?, ?, ?, ?, ?)", (timetable_id, *route)).lastrowid
            for schedule_index, (departure, arrival) in enumerate(schedule_data[index]):
                stop = stops[index][schedule_index % len(stops[index])]
                conn.execute("INSERT INTO schedule(route_id, stop, departure_time, arrival_time, day) VALUES (?, ?, ?, ?, ?)", (route_id, stop, departure, arrival, "Weekdays"))


def _rows_for_timetable(conn, timetable_id):
    rows = conn.execute("""SELECT s.id, r.id route_id, r.route_number, r.route_name, r.source, r.destination, s.stop, s.departure_time, s.arrival_time, s.day FROM schedule s JOIN routes r ON r.id=s.route_id WHERE r.timetable_id=? ORDER BY r.route_number, s.departure_time""", (timetable_id,)).fetchall()
    return [row_dict(row) for row in rows]


def get_timetable(timetable_id, include_rows=False):
    with connection() as conn:
        value = row_dict(conn.execute("SELECT * FROM timetables WHERE id=?", (timetable_id,)).fetchone())
        if value and include_rows:
            value["rows"] = _rows_for_timetable(conn, timetable_id)
            value["route_count"] = conn.execute("SELECT COUNT(*) FROM routes WHERE timetable_id=?", (timetable_id,)).fetchone()[0]
        return value


def list_timetables():
    with connection() as conn:
        rows = conn.execute("""SELECT t.*, COUNT(DISTINCT r.id) route_count, COUNT(s.id) record_count FROM timetables t LEFT JOIN routes r ON r.timetable_id=t.id LEFT JOIN schedule s ON s.route_id=r.id GROUP BY t.id ORDER BY t.upload_date DESC""").fetchall()
        return [row_dict(row) for row in rows]


def list_routes():
    with connection() as conn:
        rows = conn.execute("""SELECT r.*, t.filename, COUNT(s.id) record_count FROM routes r JOIN timetables t ON t.id=r.timetable_id LEFT JOIN schedule s ON s.route_id=r.id GROUP BY r.id ORDER BY r.route_number""").fetchall()
        return [row_dict(row) for row in rows]


def get_route(route_id):
    with connection() as conn:
        route = row_dict(conn.execute("SELECT r.*, t.filename FROM routes r JOIN timetables t ON t.id=r.timetable_id WHERE r.id=?", (route_id,)).fetchone())
        if route:
            route["rows"] = [row_dict(row) for row in conn.execute("SELECT * FROM schedule WHERE route_id=? ORDER BY departure_time", (route_id,)).fetchall()]
        return route


def search_schedule(args):
    query = """SELECT s.id, r.id route_id, r.route_number, r.route_name, r.source, r.destination, s.stop, s.departure_time, s.arrival_time, s.day, t.filename, t.id timetable_id FROM schedule s JOIN routes r ON r.id=s.route_id JOIN timetables t ON t.id=r.timetable_id WHERE 1=1"""
    params = []
    for field in ("route", "source", "destination", "stop"):
        value = args.get(field, "").strip()
        if value:
            column = "r.route_number" if field == "route" else f"r.{field}" if field in ("source", "destination") else "s.stop"
            query += f" AND LOWER({column}) LIKE LOWER(?)"
            params.append(f"%{value}%")
    departure_from = args.get("departure_from", "").strip()
    if departure_from:
        query += " AND s.departure_time >= ?"
        params.append(departure_from)
    departure_to = args.get("departure_to", "").strip()
    if departure_to:
        query += " AND s.departure_time <= ?"
        params.append(departure_to)
    query += " ORDER BY s.departure_time, r.route_number"
    with connection() as conn:
        return [row_dict(row) for row in conn.execute(query, params).fetchall()]


def update_schedule(schedule_id, payload):
    required = ("route_number", "route_name", "source", "destination", "stop", "departure_time", "arrival_time", "day")
    if any(not str(payload.get(field, "")).strip() for field in required):
        raise ValueError("All timetable fields are required.")
    if not TIME_PATTERN.match(payload["departure_time"]) or not TIME_PATTERN.match(payload["arrival_time"]):
        raise ValueError("Departure and arrival times must use HH:MM format.")
    with connection() as conn:
        schedule = conn.execute("SELECT route_id FROM schedule WHERE id=?", (schedule_id,)).fetchone()
        if not schedule:
            return None
        route_id = schedule[0]
        conn.execute("UPDATE routes SET route_number=?, route_name=?, source=?, destination=? WHERE id=?", tuple(payload[field] for field in required[:4]) + (route_id,))
        cursor = conn.execute("UPDATE schedule SET stop=?, departure_time=?, arrival_time=?, day=? WHERE id=?", tuple(payload[field] for field in required[4:]) + (schedule_id,))
        if not cursor.rowcount:
            return None
        return row_dict(conn.execute("SELECT * FROM schedule WHERE id=?", (schedule_id,)).fetchone())


def add_schedule(timetable_id, payload):
    required = ("route_number", "route_name", "source", "destination", "stop", "departure_time", "arrival_time", "day")
    if any(not str(payload.get(field, "")).strip() for field in required):
        raise ValueError("All timetable fields are required for a new row.")
    if not TIME_PATTERN.match(payload["departure_time"]) or not TIME_PATTERN.match(payload["arrival_time"]):
        raise ValueError("Departure and arrival times must use HH:MM format.")
    with connection() as conn:
        route = conn.execute("SELECT id FROM routes WHERE timetable_id=? AND route_number=? AND source=? AND destination=?", (timetable_id, payload["route_number"], payload["source"], payload["destination"])).fetchone()
        route_id = route[0] if route else conn.execute("INSERT INTO routes(timetable_id, route_number, route_name, source, destination) VALUES (?, ?, ?, ?, ?)", (timetable_id, payload["route_number"], payload["route_name"], payload["source"], payload["destination"])).lastrowid
        schedule_id = conn.execute("INSERT INTO schedule(route_id, stop, departure_time, arrival_time, day) VALUES (?, ?, ?, ?, ?)", (route_id, payload["stop"], payload["departure_time"], payload["arrival_time"], payload["day"])).lastrowid
        return row_dict(conn.execute("SELECT * FROM schedule WHERE id=?", (schedule_id,)).fetchone())


def delete_schedule(schedule_id):
    with connection() as conn:
        cursor = conn.execute("DELETE FROM schedule WHERE id=?", (schedule_id,))
        return bool(cursor.rowcount)


def delete_timetable(timetable_id):
    with connection() as conn:
        cursor = conn.execute("DELETE FROM timetables WHERE id=?", (timetable_id,))
        return bool(cursor.rowcount)


def save_extracted_rows(timetable_id, records):
    with connection() as conn:
        conn.execute("DELETE FROM routes WHERE timetable_id=?", (timetable_id,))
        route_ids = {}
        for record in records:
            key = (record.get("route_number", "Unknown"), record.get("route_name", ""), record.get("source", ""), record.get("destination", ""))
            if key not in route_ids:
                route_ids[key] = conn.execute("INSERT INTO routes(timetable_id, route_number, route_name, source, destination) VALUES (?, ?, ?, ?, ?)", (timetable_id, *key)).lastrowid
            conn.execute("INSERT INTO schedule(route_id, stop, departure_time, arrival_time, day) VALUES (?, ?, ?, ?, ?)", (route_ids[key], record.get("stop", ""), record.get("departure_time", ""), record.get("arrival_time", ""), record.get("day", "Every day")))
        conn.execute("UPDATE timetables SET status=? WHERE id=?", ("processed", timetable_id))
    return len(route_ids)


def mark_status(timetable_id, status):
    with connection() as conn:
        conn.execute("UPDATE timetables SET status=? WHERE id=?", (status, timetable_id))
