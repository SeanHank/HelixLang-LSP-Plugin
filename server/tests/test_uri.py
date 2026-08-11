"""Unit tests for path<->URI conversion."""

from __future__ import annotations

from helixlang_lsp import uri as u


def test_path_to_uri_basic():
    assert u.path_to_uri("/tmp/x.helix") == "file:///tmp/x.helix"


def test_uri_to_path_basic():
    assert u.uri_to_path("file:///tmp/x.helix") == "/tmp/x.helix"


def test_roundtrip():
    for path in ["/a/b/c.helix", "/tmp/with space.helix", "/tmp/café.helix"]:
        assert u.uri_to_path(u.path_to_uri(path)) == path


def test_idempotent_path_to_uri():
    uri = "file:///tmp/x.helix"
    assert u.path_to_uri(uri) == uri


def test_non_file_scheme_passthrough():
    assert u.uri_to_path("untitled:Untitled-1") == "untitled:Untitled-1"
    assert u.path_to_uri("untitled:Untitled-1") == "untitled:Untitled-1"


def test_percent_encoding():
    uri = u.path_to_uri("/tmp/a b.helix")
    assert "a%20b.helix" in uri
    assert u.uri_to_path(uri) == "/tmp/a b.helix"


def test_normalize_uri():
    assert u.normalize_uri("file:///tmp/x.helix") == "file:///tmp/x.helix"


def test_path_to_uri_windows_drive():
    assert u.path_to_uri(r"C:\Users\me\a.helix") == "file:///C:/Users/me/a.helix"


def test_uri_to_path_windows_drive():
    # "file:C:/..." -> path already starts with a drive letter, no leading
    # slash to strip on POSIX.
    assert u.uri_to_path("file:C:/Users/me/a.helix") == "C:/Users/me/a.helix"


def test_from_uri_dict():
    assert u._from_uri_dict(None) is None
    assert u._from_uri_dict({}) is None
    assert u._from_uri_dict({"uri": "file:///x.helix"}) == "file:///x.helix"


def test_uri_text_document_params():
    assert u.uri_text_document_params(None) == ("", "")
    assert u.uri_text_document_params({}) == ("", "")
    assert u.uri_text_document_params(
        {"textDocument": {"uri": "file:///x.helix", "text": "ATG"}}
    ) == ("file:///x.helix", "ATG")


def test_normalize_uri_empty_and_non_file():
    assert u.normalize_uri("") == ""
    assert u.normalize_uri("untitled:Untitled-1") == "untitled:Untitled-1"
