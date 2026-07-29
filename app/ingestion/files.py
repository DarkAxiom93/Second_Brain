"""Bounded upload validation and deterministic TXT/PDF extraction."""

from __future__ import annotations

from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import PurePath
from typing import BinaryIO, Literal

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from app.ingestion.text import TextChunk, normalize_plain_text

MAX_UPLOAD_BYTES = 20_000_000
MAX_EXTRACTED_BYTES = 5_000_000
MAX_PDF_PAGES = 1_000
READ_SIZE = 64 * 1024


class DocumentTooLargeError(ValueError):
    """The raw upload or extracted text exceeds its configured bound."""


class UnsupportedDocumentTypeError(ValueError):
    """The extension, declared type, and content do not consistently agree."""


class DocumentExtractionError(ValueError):
    """A supported document could not be decoded or parsed."""


class NoExtractableTextError(ValueError):
    """A supported document contains no nonblank extracted text."""


@dataclass(frozen=True)
class PageRange:
    page_number: int
    start: int
    end: int


@dataclass(frozen=True)
class ExtractedDocument:
    text: str
    media_type: Literal["text/plain", "application/pdf"]
    original_filename: str
    byte_size: int
    page_ranges: tuple[PageRange, ...] = ()


def validate_filename(filename: str | None) -> str:
    """Return a safe filename containing no path information."""
    if filename is None:
        raise DocumentExtractionError("invalid filename")
    value = filename.strip()
    if (
        not value
        or len(value) > 255
        or value in {".", ".."}
        or any(character in value for character in "/\\\0")
        or PurePath(value).name != value
        or (len(value) >= 2 and value[1] == ":")
    ):
        raise DocumentExtractionError("invalid filename")
    return value


def read_bounded(stream: BinaryIO, limit: int = MAX_UPLOAD_BYTES) -> bytes:
    """Read no more than the limit plus one byte, rejecting empty input."""
    parts: list[bytes] = []
    total = 0
    while True:
        part = stream.read(min(READ_SIZE, limit - total + 1))
        if not part:
            break
        parts.append(part)
        total += len(part)
        if total > limit:
            raise DocumentTooLargeError("document too large")
    if total == 0:
        raise DocumentExtractionError("empty document")
    return b"".join(parts)


def _has_pdf_signature(data: bytes) -> bool:
    return b"%PDF-" in data[:1024]


def _check_extracted_size(text: str) -> None:
    if len(text.encode("utf-8")) > MAX_EXTRACTED_BYTES:
        raise DocumentTooLargeError("document too large")
    if not text.strip():
        raise NoExtractableTextError("no extractable text")


def _resolve_type(filename: str, content_type: str | None, data: bytes) -> str:
    extension = PurePath(filename).suffix.lower()
    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if extension not in {".txt", ".pdf"} or declared not in {
        "text/plain",
        "application/pdf",
        "application/octet-stream",
    }:
        raise UnsupportedDocumentTypeError("unsupported document type")
    is_pdf = _has_pdf_signature(data)
    if extension == ".pdf":
        if not is_pdf or declared == "text/plain":
            raise UnsupportedDocumentTypeError("unsupported document type")
        return "application/pdf"
    if is_pdf or declared == "application/pdf":
        raise UnsupportedDocumentTypeError("unsupported document type")
    return "text/plain"


def _extract_txt(data: bytes, filename: str) -> ExtractedDocument:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DocumentExtractionError("text decoding failed") from error
    text = normalize_plain_text(text)
    _check_extracted_size(text)
    return ExtractedDocument(text, "text/plain", filename, len(data))


def _extract_pdf(data: bytes, filename: str) -> ExtractedDocument:
    try:
        reader = PdfReader(BytesIO(data), strict=True)
        if reader.is_encrypted:
            raise DocumentExtractionError("encrypted PDF")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentExtractionError("PDF page limit exceeded")
        texts: list[str] = []
        ranges: list[PageRange] = []
        cursor = 0
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = normalize_plain_text(page.extract_text() or "")
            texts.append(page_text)
            ranges.append(PageRange(page_number, cursor, cursor + len(page_text)))
            cursor += len(page_text)
            if page_number < len(reader.pages):
                cursor += 2
    except DocumentExtractionError:
        raise
    except (PyPdfError, OSError, ValueError, TypeError, KeyError) as error:
        raise DocumentExtractionError("PDF extraction failed") from error
    text = "\n\n".join(texts)
    _check_extracted_size(text)
    return ExtractedDocument(
        text, "application/pdf", filename, len(data), tuple(ranges)
    )


def extract_document(
    data: bytes, filename: str | None, content_type: str | None
) -> ExtractedDocument:
    """Validate metadata and extract one supported in-memory document."""
    validated_filename = validate_filename(filename)
    if not data:
        raise DocumentExtractionError("empty document")
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentTooLargeError("document too large")
    media_type = _resolve_type(validated_filename, content_type, data)
    if media_type == "text/plain":
        return _extract_txt(data, validated_filename)
    return _extract_pdf(data, validated_filename)


def assign_page_locators(
    chunks: list[TextChunk], page_ranges: tuple[PageRange, ...]
) -> list[TextChunk]:
    """Copy chunks with deterministic locators for actual page-text overlap."""
    located: list[TextChunk] = []
    for chunk in chunks:
        pages = [
            page.page_number
            for page in page_ranges
            if max(chunk.char_start, page.start) < min(chunk.char_end, page.end)
        ]
        locator = None
        if len(pages) == 1:
            locator = f"page {pages[0]}"
        elif pages:
            locator = f"pages {pages[0]}-{pages[-1]}"
        located.append(replace(chunk, locator=locator))
    return located
