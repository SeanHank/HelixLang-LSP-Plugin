"""Position and range mapping between the HelixLang compiler and LSP.

The compiler reports 1-based ``line``/``col`` plus a global 0-based
``codon_index``. LSP uses 0-based lines and 0-based UTF-16 code-unit columns.
"""

from __future__ import annotations

from helixlang_lsp.protocol import Position, Range


def utf16_offset_of_line(line_text: str, code_units: int) -> int:
    """Convert a code-unit offset to a character offset within ``line_text``.

    Non-BMP characters (surrogate pairs) count as 2 code units in LSP but 1
    Python code point; we skip over them.
    """
    char_offset = 0
    remaining = code_units
    while remaining > 0 and char_offset < len(line_text):
        cp = ord(line_text[char_offset])
        char_offset += 1
        remaining -= 1 if cp < 0x10000 else 2
    return char_offset


def code_unit_offset_of_char(line_text: str, char_offset: int) -> int:
    """Convert a character offset to a UTF-16 code-unit offset."""
    units = 0
    for ch in line_text[:char_offset]:
        units += 1 if ord(ch) < 0x10000 else 2
    return units


def linecol_to_position(text: str, line1: int, col1: int) -> Position:
    """Compiler (1-based line, 1-based col) -> LSP Position (0-based)."""
    line0 = max(line1 - 1, 0)
    col0 = max(col1 - 1, 0)
    lines = text.split("\n")
    if line0 < len(lines):
        char_off = utf16_offset_of_line(lines[line0], col0)
    else:
        char_off = 0
    return Position(line=line0, character=char_off)


def position_to_linecol(text: str, pos: Position) -> tuple[int, int]:
    """LSP Position -> (1-based line, 1-based col)."""
    lines = text.split("\n")
    line1 = pos.line + 1
    if pos.line < len(lines):
        char_off = code_unit_offset_of_char(lines[pos.line], pos.character)
    else:
        char_off = 0
    return line1, char_off + 1


def position_at(text: str, pos: Position) -> tuple[int, int]:
    """Resolve an LSP position to (1-based line, 1-based col), clamped."""
    lines = _split_lines(text)
    line0 = max(0, min(pos.line, len(lines) - 1))
    line_text = lines[line0]
    char_off = utf16_offset_of_line(line_text, pos.character)
    return line0 + 1, char_off + 1


def _split_lines(text: str) -> list[str]:
    """Split lines ignoring a phantom empty trailing line from a final newline."""
    lines = text.split("\n")
    if len(lines) > 1 and lines[-1] == "":
        lines = lines[:-1]
    return lines


def token_span_to_range(text: str, line1: int, col1: int, length: int) -> Range:
    """Build an LSP Range from a 1-based position and a character length."""
    start = linecol_to_position(text, line1, col1)
    end = linecol_to_position(text, line1, col1 + length)
    return Range(start=start, end=end)


def whole_line_range(text: str, line0: int) -> Range:
    """Range covering one whole 0-based line (excluding the newline)."""
    lines = text.split("\n")
    if line0 < len(lines):
        length = len(lines[line0])
    else:
        length = 0
    start = Position(line=line0, character=0)
    end = Position(line=line0, character=code_unit_offset_of_char(lines[line0], length)
                   if line0 < len(lines) else 0)
    return Range(start=start, end=end)
