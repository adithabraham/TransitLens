import re

TIME_RE = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")


def normalize_time(value):
    match = TIME_RE.search(value or "")
    return f"{int(match.group(1)):02d}:{match.group(2)}" if match else ""


def extract_records(text):
    records = []
    current_route = "Unknown"
    current_source = ""
    current_destination = ""
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        route_match = re.search(r"(?:route\s*)?(\d{2,4})", line, re.I)
        if route_match and not TIME_RE.search(line):
            current_route = route_match.group(1)
            places = re.split(r"\s*(?:->|→|to)\s*", line, flags=re.I)
            if len(places) >= 2:
                current_source = re.sub(r".*?\b" + re.escape(current_route) + r"\b\s*", "", places[0], flags=re.I).strip(" -:")
                current_destination = places[-1].strip(" -:")
        times = TIME_RE.findall(line)
        if len(times) >= 1:
            normalized = [f"{int(hour):02d}:{minute}" for hour, minute in times]
            records.append({"route_number": current_route, "route_name": f"{current_source} - {current_destination}".strip(" -"), "source": current_source, "destination": current_destination, "stop": "", "departure_time": normalized[0], "arrival_time": normalized[1] if len(normalized) > 1 else "", "day": "Every day"})
    return records
