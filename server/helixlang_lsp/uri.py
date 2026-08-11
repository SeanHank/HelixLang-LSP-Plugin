"""Path <-> URI conversion for LSP ``DocumentUri`` values.

``file://`` URIs follow RFC 8089: hostname (usually empty), then a
percent-encoded path. Windows drive letters get a ``/C:/`` prefix.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, unquote, urlsplit

_WINDOWS_DRIVE_RE = re.compile(r"^([A-Za-z]:[\\/].*)$")
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_ANY_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:[^/\\]")


def path_to_uri(path: str) -> str:
    """Convert a filesystem path to a ``file://`` URI."""
    if path.startswith("file://"):
        return path
    if _WINDOWS_DRIVE_RE.match(path):
        pass  # fall through to path handling below
    elif _SCHEME_RE.match(path) or _ANY_SCHEME_RE.match(path):
        return path
    p = path.replace("\\", "/")
    if _WINDOWS_DRIVE_RE.match(p):
        p = "/" + p
    if not p.startswith("/"):
        p = "/" + p
    encoded = quote(p, safe="/:")
    return "file://" + encoded


def uri_to_path(uri: str) -> str:
    """Convert a ``file://`` URI back to a filesystem path."""
    parsed = urlsplit(uri)
    if parsed.scheme and parsed.scheme != "file":
        return unquote(uri)
    p = unquote(parsed.path)
    if _WINDOWS_DRIVE_RE.match(p):
        p = p.lstrip("/")
    return p.replace("/", "\\") if _is_windows() and "/" in p and "\\" not in p else p


def _is_windows() -> bool:
    import os

    return os.name == "nt"


def _from_uri_dict(d: dict[str, Any] | None) -> str | None:
    if not d:
        return None
    return str(d.get("uri", ""))


def uri_text_document_params(params: Any) -> tuple[str, str]:
    """Extract ``(uri, text)`` from textDocument params."""
    text_doc = params.get("textDocument", {}) if isinstance(params, dict) else {}
    uri = text_doc.get("uri", "")
    text = text_doc.get("text", "")
    return str(uri), str(text)


def normalize_uri(uri: str) -> str:
    """Normalize a document URI for use as an analysis cache key."""
    if not uri:
        return uri
    if uri.startswith("file://"):
        return path_to_uri(uri_to_path(uri))
    return uri
