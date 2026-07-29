"""Pure-function and schema coverage for explicit text ingestion."""

from hashlib import sha256

import pytest
from pydantic import ValidationError

from app.ingestion.text import chunk_text, normalize_plain_text
from app.schemas.source import SourceTextIngest


def test_normalization_preserves_everything_except_line_endings() -> None:
    original = " \tHebrew עברית  Russian русский 😀\r\ncode()\rtrailing \t"
    assert normalize_plain_text(original) == (
        " \tHebrew עברית  Russian русский 😀\ncode()\ntrailing \t"
    )
    assert normalize_plain_text("a\nb") == "a\nb"


@pytest.mark.parametrize("text", ["", " \t\r\n"])
def test_blank_text_is_rejected(text: str) -> None:
    with pytest.raises(ValidationError):
        SourceTextIngest(text=text)


def test_utf8_byte_limit_and_multibyte_counting() -> None:
    assert SourceTextIngest(text="a" * 5_000_000).text
    assert SourceTextIngest(text="😀" * 1_250_000).text
    with pytest.raises(ValidationError):
        SourceTextIngest(text="😀" * 1_250_001)


@pytest.mark.parametrize("filename", ["a/b", "a\\b", ".", "..", "a\0b"])
def test_invalid_filenames_are_rejected(filename: str) -> None:
    with pytest.raises(ValidationError):
        SourceTextIngest(text="valid", original_filename=filename)


def test_filename_is_trimmed_and_blank_becomes_none() -> None:
    assert (
        SourceTextIngest(text="x", original_filename=" file.txt ").original_filename
        == "file.txt"
    )
    assert SourceTextIngest(text="x", original_filename="   ").original_filename is None


@pytest.mark.parametrize("size", [1000, 10000])
@pytest.mark.parametrize("overlap", [0, 500])
def test_chunk_setting_boundaries(size: int, overlap: int) -> None:
    SourceTextIngest(text="x", chunk_size=size, chunk_overlap=overlap)


@pytest.mark.parametrize(
    "values",
    [
        {"chunk_size": 999},
        {"chunk_size": 10001},
        {"chunk_overlap": -1},
        {"chunk_overlap": 501},
        {"chunk_size": 1000, "chunk_overlap": 1000},
    ],
)
def test_invalid_chunk_settings_are_rejected(values: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        SourceTextIngest(text="x", **values)


def test_chunks_are_deterministic_exact_and_hashed() -> None:
    text = "abcdefghij"
    first = chunk_text(text, 4, 1)
    second = chunk_text(text, 4, 1)
    assert first == second
    assert [chunk.content for chunk in first] == ["abcd", "defg", "ghij"]
    assert [chunk.chunk_index for chunk in first] == [0, 1, 2]
    for chunk in first:
        assert text[chunk.char_start : chunk.char_end] == chunk.content
        assert chunk.content_hash == sha256(chunk.content.encode("utf-8")).hexdigest()


def test_whitespace_windows_are_skipped_without_index_gaps() -> None:
    chunks = chunk_text("x   y", 2, 0)
    assert [(chunk.chunk_index, chunk.content) for chunk in chunks] == [
        (0, "x "),
        (1, "y"),
    ]


def test_more_than_ten_thousand_emitted_chunks_is_rejected() -> None:
    with pytest.raises(ValueError, match="more than 10000"):
        chunk_text("x" * 10_001, 1, 0)
