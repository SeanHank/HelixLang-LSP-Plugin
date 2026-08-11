"""Unit tests for position/range mapping and UTF-16 handling."""

from __future__ import annotations

from helixlang_lsp import positions as p
from helixlang_lsp.protocol import Position


def test_linecol_to_position_basic():
    text = "ab\ncdef\n"
    assert p.linecol_to_position(text, 1, 1) == Position(line=0, character=0)
    assert p.linecol_to_position(text, 2, 3) == Position(line=1, character=2)


def test_position_to_linecol_roundtrip():
    text = "abc\ndefgh"
    for line1, col1 in [(1, 1), (1, 3), (2, 1), (2, 5)]:
        pos = p.linecol_to_position(text, line1, col1)
        assert p.position_to_linecol(text, pos) == (line1, col1)


def test_utf16_surrogate_handling():
    # emoji = 2 UTF-16 units, 1 code point
    line = "a😀b"
    # char offset 2 (the emoji) is 3 UTF-16 units
    assert p.code_unit_offset_of_char(line, 2) == 3
    assert p.utf16_offset_of_line(line, 3) == 2
    # col1=3 (1-based) -> unit offset 2 -> lands inside the emoji pair
    pos = p.linecol_to_position(line + "\n", 1, 3)
    assert pos.character == 2


def test_token_span_to_range():
    text = "#gene name=foo\n"
    rng = p.token_span_to_range(text, 1, 7, 3)
    assert rng.start == Position(line=0, character=6)
    assert rng.end == Position(line=0, character=9)


def test_whole_line_range():
    text = "abc\n"
    rng = p.whole_line_range(text, 0)
    assert rng.start == Position(line=0, character=0)
    assert rng.end == Position(line=0, character=3)


def test_position_at_clamps():
    text = "one\ntwo"
    assert p.position_at(text, Position(line=5, character=5)) == (2, 4)
