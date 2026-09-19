import csv
import io
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file
from werkzeug.utils import secure_filename

from utils.database import (
    add_schedule,
    create_timetable,
    delete_timetable,
    get_route,
    get_timetable,
    init_db,
    list_routes,
    list_timetables,
    search_schedule,
    seed_demo_data,
    mark_status,
    update_schedule,
)
from utils.ocr import process_document

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
PROCESSED_DIR = BASE_DIR / "processed"
UPLOAD_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAX_FILE_SIZE = 15 * 1024 * 1024

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE
app.config["JSON_SORT_KEYS"] = False
init_db()
seed_demo_data()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/upload")
def upload_page():
    return render_template("upload.html")


@app.get("/verify/<int:timetable_id>")
def verify_page(timetable_id):
    return render_template("verify.html", timetable_id=timetable_id)


@app.get("/timetable/<int:timetable_id>")
def timetable_page(timetable_id):
    return render_template("timetable.html", timetable_id=timetable_id)


@app.get("/history")
def history_page():
    return render_template("history.html")


@app.get("/api/demo/sample-pdf")
def sample_pdf():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=28, leftMargin=28, topMargin=28, bottomMargin=28)
        rows = [["Route 101", "Nilambur", "Kozhikode", "Stop", "Departure", "Arrival", "Service"], ["101", "Nilambur", "Kozhikode", "Edakkara", "08:00", "10:15", "Weekdays"], ["101", "Nilambur", "Kozhikode", "Vazhikkadavu", "09:15", "11:30", "Weekdays"], ["101", "Nilambur", "Kozhikode", "Perinthalmanna", "10:30", "12:45", "Weekdays"], ["101", "Nilambur", "Kozhikode", "Edakkara", "12:00", "14:15", "Weekdays"], ["101", "Nilambur", "Kozhikode", "Vazhikkadavu", "14:15", "16:30", "Weekdays"], ["101", "Nilambur", "Kozhikode", "Perinthalmanna", "16:30", "18:45", "Weekdays"]]
        table = Table(rows, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123b5d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef4f7")])]))
        document.build([Paragraph("TransitLens sample public-transport timetable", getSampleStyleSheet()["Title"]), table])
        buffer.seek(0)
        return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name="transitlens-sample-timetable.pdf")
    except ImportError:
        return jsonify(error="PDF sample requires the reportlab package."), 501


@app.get("/route/<int:route_id>")
def route_page(route_id):
    return render_template("route.html", route_id=route_id)


@app.post("/api/upload")
def upload():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify(error="Choose a timetable image or PDF first."), 400
    if not allowed_file(uploaded_file.filename):
        return jsonify(error="Unsupported file type. Use JPG, JPEG, PNG, or PDF."), 400

    safe_name = secure_filename(uploaded_file.filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    file_path = UPLOAD_DIR / stored_name
    uploaded_file.save(file_path)
    timetable_id = create_timetable(safe_name, stored_name)
    return jsonify(id=timetable_id, filename=safe_name, status="uploaded"), 201


@app.post("/api/process/<int:timetable_id>")
def process(timetable_id):
    timetable = get_timetable(timetable_id)
    if not timetable:
        return jsonify(error="Timetable not found."), 404
    file_path = UPLOAD_DIR / timetable["stored_name"]
    if not file_path.exists():
        return jsonify(error="The uploaded file is no longer available."), 404
    try:
        result = process_document(file_path, timetable_id)
        return jsonify(result), 200
    except Exception as exc:
        mark_status(timetable_id, "failed")
        return jsonify(error=f"Processing failed: {exc}"), 422


@app.get("/api/process/<int:timetable_id>/status")
def process_status(timetable_id):
    timetable = get_timetable(timetable_id)
    if not timetable:
        return jsonify(error="Timetable not found."), 404
    return jsonify(id=timetable_id, status=timetable["status"])


@app.get("/api/timetables")
def timetables():
    return jsonify(list_timetables())


@app.get("/api/timetables/<int:timetable_id>")
def timetable(timetable_id):
    value = get_timetable(timetable_id, include_rows=True)
    if not value:
        return jsonify(error="Timetable not found."), 404
    return jsonify(value)


@app.get("/api/routes")
def routes():
    return jsonify(list_routes())


@app.get("/api/routes/<int:route_id>")
def route(route_id):
    value = get_route(route_id)
    if not value:
        return jsonify(error="Route not found."), 404
    return jsonify(value)


@app.put("/api/schedule/<int:schedule_id>")
def schedule_update(schedule_id):
    payload = request.get_json(silent=True) or {}
    try:
        updated = update_schedule(schedule_id, payload)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if not updated:
        return jsonify(error="Schedule row not found."), 404
    return jsonify(updated)


@app.post("/api/schedule")
def schedule_create():
    payload = request.get_json(silent=True) or {}
    timetable_id = payload.pop("timetable_id", None)
    if not timetable_id:
        return jsonify(error="A timetable is required."), 400
    try:
        return jsonify(add_schedule(timetable_id, payload)), 201
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@app.delete("/api/schedule/<int:schedule_id>")
def schedule_delete(schedule_id):
    from utils.database import delete_schedule
    if not delete_schedule(schedule_id):
        return jsonify(error="Schedule row not found."), 404
    return jsonify(success=True)


@app.get("/api/search")
def search():
    return jsonify(search_schedule(request.args))


@app.delete("/api/timetables/<int:timetable_id>")
def timetable_delete(timetable_id):
    if not delete_timetable(timetable_id):
        return jsonify(error="Timetable not found."), 404
    return jsonify(success=True)


def export_rows(timetable_id):
    value = get_timetable(timetable_id, include_rows=True)
    if not value:
        return None, None
    return value, value.get("rows", [])


@app.get("/api/export/json/<int:timetable_id>")
def export_json(timetable_id):
    value, _ = export_rows(timetable_id)
    if not value:
        return jsonify(error="Timetable not found."), 404
    response = app.response_class(json.dumps(value, indent=2), mimetype="application/json")
    response.headers["Content-Disposition"] = f"attachment; filename=transitlens-{timetable_id}.json"
    return response


@app.get("/api/export/csv/<int:timetable_id>")
def export_csv(timetable_id):
    value, rows = export_rows(timetable_id)
    if not value:
        return jsonify(error="Timetable not found."), 404
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["route_number", "route_name", "source", "destination", "stop", "departure_time", "arrival_time", "day"])
    writer.writeheader()
    writer.writerows({key: row.get(key, "") for key in writer.fieldnames} for row in rows)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name=f"transitlens-{timetable_id}.csv")


@app.get("/api/export/pdf/<int:timetable_id>")
def export_pdf(timetable_id):
    value, rows = export_rows(timetable_id)
    if not value:
        return jsonify(error="Timetable not found."), 404
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        buffer = io.BytesIO()
        document = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=24, leftMargin=24, topMargin=24, bottomMargin=24)
        styles = getSampleStyleSheet()
        data = [["Route", "From", "To", "Stop", "Departure", "Arrival", "Day"]]
        data += [[r.get("route_number", ""), r.get("source", ""), r.get("destination", ""), r.get("stop", ""), r.get("departure_time", ""), r.get("arrival_time", ""), r.get("day", "") ] for r in rows]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123b5d")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef4f7")])]))
        document.build([Paragraph(value["filename"], styles["Title"]), table])
        buffer.seek(0)
        return send_file(buffer, mimetype="application/pdf", as_attachment=True, download_name=f"transitlens-{timetable_id}.pdf")
    except ImportError:
        return jsonify(error="PDF export requires the reportlab package."), 501


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="That file is too large. Maximum size is 15 MB."), 413


if __name__ == "__main__":
    app.run(debug=True, port=5000)
