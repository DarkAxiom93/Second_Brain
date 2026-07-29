"""Pure tests for bounded TXT/PDF extraction and page locators."""

from io import BytesIO

import pytest
from pypdf import PdfWriter

from app.ingestion.files import (
    DocumentExtractionError,
    DocumentTooLargeError,
    NoExtractableTextError,
    PageRange,
    UnsupportedDocumentTypeError,
    assign_page_locators,
    extract_document,
    read_bounded,
    validate_filename,
)
from app.ingestion.text import TextChunk, chunk_text, hash_chunk


def _pdf_bytes(page_texts: list[str]) -> bytes:
    """Build a tiny deterministic text-layer PDF without a fixture dependency."""
    kids = " ".join(f"{4 + index * 2} 0 R" for index in range(len(page_texts)))
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_texts)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for index, text in enumerate(page_texts):
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        content_id = 5 + index * 2
        objects.extend(
            [
                (
                    f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                    "/Resources << /Font << /F1 3 0 R >> >> "
                    f"/Contents {content_id} 0 R >>"
                ).encode(),
                b"<< /Length "
                + str(len(stream)).encode()
                + b" >>\nstream\n"
                + stream
                + b"\nendstream",
            ]
        )
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)


def test_txt_utf8_bom_normalization_whitespace_and_raw_size() -> None:
    raw = b"\xef\xbb\xbf  first\r\nlast\r  "
    result = extract_document(raw, " notes.txt ", "text/plain")
    assert result.text == "  first\nlast\n  "
    assert result.original_filename == "notes.txt"
    assert result.byte_size == len(raw)
    assert result.media_type == "text/plain" and result.page_ranges == ()


@pytest.mark.parametrize(
    "data,error",
    [
        (b"\xff", DocumentExtractionError),
        (b" \r\n\t", NoExtractableTextError),
    ],
)
def test_txt_rejects_invalid_or_blank(data: bytes, error: type[ValueError]) -> None:
    with pytest.raises(error):
        extract_document(data, "a.txt", "text/plain")


@pytest.mark.parametrize(
    "filename", [None, " ", ".", "..", "a/b.txt", "a\\b.txt", "C:note.txt", "a\0.txt"]
)
def test_filename_rejection(filename: str | None) -> None:
    with pytest.raises(DocumentExtractionError):
        validate_filename(filename)


@pytest.mark.parametrize(
    "filename,content_type,data",
    [
        ("a.docx", "application/octet-stream", b"hello"),
        ("a.txt", "application/pdf", b"hello"),
        ("a.txt", "text/plain", b"%PDF-1.4"),
        ("a.pdf", "application/pdf", b"hello"),
        ("a.pdf", "text/plain", b"%PDF-1.4"),
    ],
)
def test_type_contradictions_are_unsupported(
    filename: str, content_type: str, data: bytes
) -> None:
    with pytest.raises(UnsupportedDocumentTypeError):
        extract_document(data, filename, content_type)


def test_octet_stream_requires_conclusive_supported_content() -> None:
    assert (
        extract_document(b"hello", "a.txt", "application/octet-stream").text == "hello"
    )
    pdf = _pdf_bytes(["hello"])
    assert (
        extract_document(pdf, "a.pdf", "application/octet-stream").media_type
        == "application/pdf"
    )


def test_bounded_reader_accepts_boundary_and_stops_after_limit() -> None:
    assert read_bounded(BytesIO(b"1234"), 4) == b"1234"
    stream = BytesIO(b"12345more")
    with pytest.raises(DocumentTooLargeError):
        read_bounded(stream, 4)
    assert stream.tell() == 5
    with pytest.raises(DocumentExtractionError):
        read_bounded(BytesIO(), 4)


def test_pdf_page_order_separator_and_locators_are_deterministic() -> None:
    data = _pdf_bytes(["First", "Second"])
    first = extract_document(data, "a.pdf", "application/pdf")
    second = extract_document(data, "a.pdf", "application/pdf")
    assert first == second
    assert first.text == "First\n\nSecond"
    chunks = chunk_text(first.text, 1000, 0)
    located = assign_page_locators(chunks, first.page_ranges)
    assert located[0].locator == "pages 1-2"
    assert located[0].content_hash == chunks[0].content_hash
    assert (located[0].char_start, located[0].char_end) == (
        chunks[0].char_start,
        chunks[0].char_end,
    )


def test_separator_only_overlap_has_no_locator() -> None:
    chunks = [TextChunk(0, "\n\n", 1, 3, hash_chunk("\n\n"))]
    located = assign_page_locators(chunks, (PageRange(1, 0, 1), PageRange(2, 3, 4)))
    assert located[0].locator is None


def test_malformed_encrypted_and_blank_pdfs_are_rejected() -> None:
    with pytest.raises(DocumentExtractionError):
        extract_document(b"%PDF-broken", "a.pdf", "application/pdf")
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    stream = BytesIO()
    writer.write(stream)
    with pytest.raises(DocumentExtractionError):
        extract_document(stream.getvalue(), "a.pdf", "application/pdf")
    with pytest.raises(NoExtractableTextError):
        extract_document(_pdf_bytes([""]), "a.pdf", "application/pdf")
