"""Raw file bytes -> plain text, the first step of the Parsing Worker
(VHIRE-2x / E6). Supports PDF (the common resume format) via `pypdf` and
falls back to UTF-8 decoding for plain-text formats (.txt/.md) - no DOCX
support yet, an acknowledged gap rather than a silent one.
"""


class UnsupportedFileTypeError(Exception):
    """Raised when `filename`'s extension has no extraction path."""


def extract_text(content: bytes, filename: str) -> str:
    """Extract plain text from `content`, dispatching on `filename`'s extension.

    Raises:
        UnsupportedFileTypeError: for extensions with no extraction path
            (e.g. .docx - not yet supported).
    """
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if suffix == "pdf":
        return _extract_pdf_text(content)
    if suffix in ("txt", "md"):
        return content.decode("utf-8", errors="replace")

    raise UnsupportedFileTypeError(f"no text extraction path for file type: .{suffix}")


def _extract_pdf_text(content: bytes) -> str:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)
