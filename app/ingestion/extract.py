import io
from dataclasses import dataclass

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


@dataclass
class Page:
    number: int
    text: str


class ExtractionError(ValueError):
    pass


def extract_pages(filename: str, data: bytes) -> list[Page]:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in SUPPORTED_EXTENSIONS:
        raise ExtractionError(f"Unsupported file type '{ext}'. Allowed: {sorted(SUPPORTED_EXTENSIONS)}")

    if ext == ".pdf":
        if not data.startswith(b"%PDF"):
            raise ExtractionError("File has a .pdf extension but is not a PDF")
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [Page(i + 1, (p.extract_text() or "").strip()) for i, p in enumerate(reader.pages)]
    elif ext == ".docx":
        from docx import Document as DocxDocument

        try:
            doc = DocxDocument(io.BytesIO(data))
        except Exception as exc:  # python-docx raises several unrelated types for bad zips
            raise ExtractionError("Could not read .docx file") from exc
        pages = [Page(1, "\n".join(p.text for p in doc.paragraphs).strip())]
    else:
        try:
            pages = [Page(1, data.decode("utf-8").strip())]
        except UnicodeDecodeError as exc:
            raise ExtractionError("Text file is not valid UTF-8") from exc

    pages = [p for p in pages if p.text]
    if not pages:
        raise ExtractionError("No extractable text (scanned PDFs need OCR, which is not enabled)")
    return pages
