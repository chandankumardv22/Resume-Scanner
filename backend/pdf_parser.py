from __future__ import annotations

import io
import os
import re
from typing import Any

# ==============================================================================
# TECH STACK: [pdfminer.six & pypdf] - Robust, Validated Multi-Stage PDF Parsing
# ==============================================================================
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.layout import LAParams

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

# Configurable limits for safe processing (configurable via MAX_UPLOAD_SIZE_MB or MAX_PDF_FILE_SIZE_BYTES)
_mb_env = os.getenv("MAX_UPLOAD_SIZE_MB", "").strip()
if _mb_env and _mb_env.isdigit():
    MAX_PDF_FILE_SIZE_BYTES: int = int(_mb_env) * 1024 * 1024
else:
    MAX_PDF_FILE_SIZE_BYTES: int = int(os.getenv("MAX_PDF_FILE_SIZE_BYTES", 10 * 1024 * 1024))  # 10 MB default

MAX_PDF_PAGES: int = int(os.getenv("MAX_PDF_PAGES", 30))
MIN_EXTRACTED_CHARS_THRESHOLD: int = int(os.getenv("MIN_EXTRACTED_CHARS_THRESHOLD", 30))


class PDFProcessingError(ValueError):
    """Base class for all PDF validation and parsing errors."""
    pass


class EmptyPDFError(PDFProcessingError):
    """Raised when an uploaded PDF file has 0 bytes."""
    pass


class FileSizeLimitExceededError(PDFProcessingError):
    """Raised when an uploaded PDF exceeds the configured size limit."""
    pass


class InvalidPDFSignatureError(PDFProcessingError):
    """Raised when an uploaded file lacks the standard %PDF- magic signature."""
    pass


class EncryptedPDFError(PDFProcessingError):
    """Raised when an uploaded PDF is password-protected or encrypted."""
    pass


class CorruptedPDFError(PDFProcessingError):
    """Raised when a PDF has corrupt structural objects or unreadable xref table."""
    pass


class ExcessivePageCountError(PDFProcessingError):
    """Raised when a PDF exceeds the allowable page count limit."""
    pass


class ScannedPDFError(PDFProcessingError):
    """Raised when a PDF has pages/images but no extractable text layer (requires OCR)."""
    pass


def normalize_extracted_text(text: str) -> str:
    """
    Conservative normalization preserving headings, technical terms, symbols (C++, C#, .NET),
    bullet points, dates, and metrics while removing noisy extraction artifacts and blank runs.
    """
    if not text:
        return ""
    cleaned = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
    # Normalize carriage returns
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    # Replace non-breaking spaces and excessive inline tabs/spaces
    cleaned = re.sub(r"[ \t\f\v]+", " ", cleaned)
    # Collapse runs of 3+ blank lines into standard 2 blank lines (paragraph breaks)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    # Strip leading/trailing line whitespace while keeping newlines
    lines = [ln.strip() for ln in cleaned.split("\n")]
    return "\n".join(lines).strip()


def validate_pdf_bytes(data: bytes) -> dict[str, Any]:
    """
    Validate PDF byte stream against size, signature, corruption, encryption, and page count.
    """
    if not data or len(data) == 0:
        raise EmptyPDFError("Uploaded file is empty (0 bytes). Please upload a valid PDF resume.")

    if len(data) > MAX_PDF_FILE_SIZE_BYTES:
        mb_limit = MAX_PDF_FILE_SIZE_BYTES // (1024 * 1024)
        raise FileSizeLimitExceededError(
            f"File size exceeds the {mb_limit}MB limit. Please upload a smaller PDF."
        )

    # Magic bytes check: must contain %PDF- in the first 1024 bytes (some PDFs have leading BOM/comments)
    header_chunk = data[:1024]
    if b"%PDF-" not in header_chunk:
        raise InvalidPDFSignatureError(
            "Invalid file format. The file is missing the standard PDF header signature (%PDF-)."
        )

    page_count = 0
    if PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(data))
            if getattr(reader, "is_encrypted", False):
                raise EncryptedPDFError(
                    "This PDF is password-protected or encrypted. Please upload an unencrypted document."
                )
            page_count = len(reader.pages)
            if page_count > MAX_PDF_PAGES:
                raise ExcessivePageCountError(
                    f"PDF contains {page_count} pages, exceeding the maximum limit of {MAX_PDF_PAGES}. "
                    "Resumes should typically be 1-4 pages."
                )
            if page_count == 0:
                raise CorruptedPDFError("PDF contains 0 valid readable pages.")
        except (EncryptedPDFError, ExcessivePageCountError, CorruptedPDFError):
            raise
        except Exception as exc:
            # If pypdf failed to even read page headers, it's corrupt
            raise CorruptedPDFError(f"Corrupted or structurally unreadable PDF: {type(exc).__name__}") from exc

    return {"byte_size": len(data), "page_count": page_count}


def _extract_pdfminer_from_stream(stream: io.BytesIO, laparams: LAParams | None = None) -> str:
    try:
        stream.seek(0)
        if laparams:
            return pdfminer_extract_text(stream, laparams=laparams) or ""
        return pdfminer_extract_text(stream) or ""
    except Exception:
        return ""


def _extract_pypdf_from_stream(stream: io.BytesIO) -> str:
    if PdfReader is None:
        return ""
    try:
        stream.seek(0)
        reader = PdfReader(stream)
        chunks: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text() or ""
            if page_text.strip():
                chunks.append(page_text)
        return "\n".join(chunks)
    except Exception:
        return ""


def extract_pdf_text_from_bytes(data: bytes) -> str:
    """
    Validates PDF bytes and extracts text cleanly with fallback order:
    1. pdfminer.six standard
    2. pdfminer.six with tuned layout parameters
    3. pypdf page-by-page text extraction
    Detects scanned/image-only PDFs and raises ScannedPDFError.
    """
    if isinstance(data, bytearray):
        data = bytes(data)
    metadata = validate_pdf_bytes(data)
    with io.BytesIO(data) as stream:
        candidates = [
            ("pdfminer_default", _extract_pdfminer_from_stream(stream)),
            (
                "pdfminer_tuned",
                _extract_pdfminer_from_stream(
                    stream, LAParams(all_texts=True, line_margin=0.12, word_margin=0.08)
                ),
            ),
            ("pypdf", _extract_pypdf_from_stream(stream)),
        ]

        best_text = ""
        for _, raw in candidates:
            normalized = normalize_extracted_text(raw)
            if len(normalized) > len(best_text):
                best_text = normalized

        if len(best_text) < MIN_EXTRACTED_CHARS_THRESHOLD:
            page_count = metadata.get("page_count", 0)
            if page_count > 0:
                raise ScannedPDFError(
                    "This PDF appears to be scanned or image-only with no extractable text layer. "
                    "Please upload a text-based PDF (exported from Word/Docs/Canva) or run OCR before uploading."
                )
            raise CorruptedPDFError("Unable to extract readable text from this PDF document.")

        return best_text


def extract_pdf_text(path: str) -> str:
    """
    Legacy and path-based entry point. Validates file existence and delegates to extract_pdf_text_from_bytes.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PDF file not found: {path}")

    with open(path, "rb") as f:
        data = f.read()

    return extract_pdf_text_from_bytes(data)
