# TransitLens

TransitLens is a functional Flask prototype that turns printed public-transport timetables into searchable, verifiable structured data.

## Features

- JPG, JPEG, PNG, and PDF upload with validation and drag and drop
- OpenCV preprocessing: grayscale, denoising, CLAHE contrast, and adaptive thresholding
- Tesseract OCR with modular parsing into route and schedule records
- SQLite persistence for timetables, routes, and schedule rows
- Editable verification table before data is treated as final
- Search by route, source, destination, stop, and departure window
- Route detail pages, processing history, and CSV, JSON, and PDF export
- Seeded multi-route demo timetable for immediate exploration

## Setup

Python 3.10+ is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000.

### Tesseract OCR

Install Tesseract separately and ensure `tesseract.exe` is on PATH. On Windows, the UB Mannheim installer is a commonly used distribution. If it is installed elsewhere, set `pytesseract.pytesseract.tesseract_cmd` in `utils/ocr.py` to the executable path.

### PDF support

`pdf2image` also needs Poppler on Windows. Install Poppler, add its `bin` folder to PATH, and restart the terminal. Image uploads work without Poppler.

## How OCR works

1. The upload is stored with a generated prefix and a sanitized original filename.
2. Images are loaded directly; PDFs are rendered into 250 DPI pages.
3. OpenCV preprocesses each page for readability.
4. Tesseract returns text; `utils/parser.py` detects routes and time pairs.
5. Parsed records are stored as a route plus schedule rows.
6. The verification page lets a user correct rows before exploring or exporting them.

The parser intentionally lives outside the Flask routes so support for additional timetable layouts can be added later.

## API

- `POST /api/upload` multipart field `file`
- `POST /api/process/<id>` process an uploaded document
- `GET /api/process/<id>/status` read the current processing stage
- `GET /api/timetables` list upload history
- `GET /api/timetables/<id>` timetable and structured rows
- `GET /api/routes` and `GET /api/routes/<id>` route data
- `PUT /api/schedule/<id>` update `stop`, `departure_time`, `arrival_time`, and `day`
- `DELETE /api/schedule/<id>` remove a row
- `GET /api/search?route=&source=&destination=&stop=&departure_from=&departure_to=`
- `GET /api/export/csv/<id>`, `/api/export/json/<id>`, `/api/export/pdf/<id>`
- `GET /api/demo/sample-pdf` download a printable OCR test document

The upload screen also provides a sample CSV containing the same timetable in structured form.

## Database

`timetables` stores the source file and processing status. `routes` stores route identity and endpoints. `schedule` stores stop, departure, arrival, and service day rows. Foreign keys cascade when a timetable or route is deleted.

## Example usage

The dashboard starts with a demo timetable covering routes 101, 202, and 303. Open it from the recent list, filter route `101`, select a route number to inspect its stops, or upload a real scan and correct the OCR output before saving.
