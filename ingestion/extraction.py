import docx
from django.conf import settings


class ExtractionError(Exception):
    """Raised when the uploaded file can't be turned into raw text at all."""


def extract_text(uploaded_file) -> str:
    name = (uploaded_file.name or "").lower()

    if uploaded_file.size > settings.MAX_INGESTION_FILE_SIZE_BYTES:
        max_mb = settings.MAX_INGESTION_FILE_SIZE_BYTES / (1024 * 1024)
        raise ExtractionError(f"File is too large (max {max_mb:.0f} MB).")

    if name.endswith(".docx"):
        return _extract_docx(uploaded_file)
    if name.endswith(".txt"):
        return _extract_txt(uploaded_file)
    raise ExtractionError("Unsupported file type. Please upload a .txt or .docx file.")


def _extract_txt(uploaded_file) -> str:
    raw = uploaded_file.read()
    return raw.decode("utf-8", errors="replace")


def _extract_docx(uploaded_file) -> str:
    try:
        document = docx.Document(uploaded_file)
    except Exception as exc:  # python-docx raises varied errors on bad files
        raise ExtractionError(f"Could not read this .docx file: {exc}") from exc
    paragraphs = [p.text for p in document.paragraphs]
    return "\n".join(paragraphs)
