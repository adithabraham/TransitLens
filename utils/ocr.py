from pathlib import Path

from utils.database import mark_status, save_extracted_rows
from utils.image_processing import load_pages, preprocess_image
from utils.parser import extract_records


def process_document(path: Path, timetable_id: int):
    mark_status(timetable_id, "preprocessing")
    pages = load_pages(path)
    if not pages:
        raise ValueError("No readable pages were found in the file.")
    try:
        import pytesseract
    except ImportError as exc:
        raise ValueError("OCR is unavailable. Install pytesseract and Tesseract OCR.") from exc
    mark_status(timetable_id, "ocr_processing")
    text_parts = []
    for page in pages:
        prepared = preprocess_image(page)
        text_parts.append(pytesseract.image_to_string(prepared, config="--psm 6"))
    processed_dir = Path(__file__).resolve().parent.parent / "processed"
    processed_dir.mkdir(exist_ok=True)
    (processed_dir / f"timetable-{timetable_id}.txt").write_text("\n".join(text_parts), encoding="utf-8")
    mark_status(timetable_id, "extracting_data")
    records = extract_records("\n".join(text_parts))
    if not records:
        raise ValueError("No timetable rows detected. Try a sharper, well-lit scan.")
    route_count = save_extracted_rows(timetable_id, records)
    mark_status(timetable_id, "processed")
    return {"id": timetable_id, "status": "processed", "records": len(records), "routes": route_count}
