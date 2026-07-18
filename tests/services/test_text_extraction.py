"""Tests for app.services.text_extraction (VHIRE-2x / E6)."""

import pytest

from app.services.text_extraction import UnsupportedFileTypeError, extract_text


def test_extract_text_decodes_plain_text_files():
    assert extract_text(b"hello world", "resume.txt") == "hello world"


def test_extract_text_decodes_markdown_files():
    assert extract_text(b"# Resume", "resume.md") == "# Resume"


def test_extract_text_raises_for_unsupported_extension():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(b"binary data", "resume.docx")


def test_extract_text_raises_for_no_extension():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(b"binary data", "resume")
