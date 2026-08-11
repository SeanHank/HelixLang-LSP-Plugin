"""``textDocument/formatting`` — conservative, semantics-preserving formatter.

Doc/03 §10.7: normalizes codon spacing (group every 3 bases with single
spaces), keeps annotation ``key=value`` spacing, never reorders fields, never
changes DNA case or rewrites ``#regulate`` arrows. Emits a single full-document
``TextEdit``.
"""

from __future__ import annotations

import re
from typing import Any

from helixlang_lsp.analysis import Analysis
from helixlang_lsp.protocol import Position, Range, TextEdit

_CODON_LINE_RE = re.compile(r"^[ \t]*([ATCG]{3}[ \t]+)+[ATCG]{3}[ \t]*$")
_CODON_RE = re.compile(r"[ATCG]{3}")


def formatting(text: str, analysis: Analysis,
               params: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle ``textDocument/formatting``."""
    options = params.get("options", {}) or {}
    _insert_spaces = bool(options.get("insertSpaces", True))
    _tab_size = int(options.get("tabSize", 4) or 4)

    lines = text.split("\n")
    out_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if _CODON_LINE_RE.match(stripped):
            indentation = line[: len(line) - len(line.lstrip())]
            codons = _CODON_RE.findall(stripped)
            out_lines.append(indentation + " ".join(codons))
        else:
            out_lines.append(line)

    new_text = "\n".join(out_lines)
    if new_text == text:
        return []
    return [TextEdit(
        range=Range(start=Position(line=0, character=0),
                    end=_end_position(text)),
        new_text=new_text,
    ).to_dict()]


def _end_position(text: str) -> Position:
    lines = text.split("\n")
    if not lines:
        return Position(line=0, character=0)
    last = lines[-1]
    if text.endswith("\n"):
        return Position(line=len(lines), character=0)
    return Position(line=len(lines) - 1, character=len(last))
