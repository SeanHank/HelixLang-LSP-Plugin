"""``textDocument/references`` — all usages of a symbol.

Walks the per-document symbol table; honors ``includeDeclaration``
(doc/03 §10.3).
"""

from __future__ import annotations

from typing import Any

from helixlang_lsp import positions as pos
from helixlang_lsp.analysis import Analysis
from helixlang_lsp.protocol import Location, Position


def references(text: str, analysis: Analysis,
               params: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle ``textDocument/references``."""
    position = Position.from_dict(params.get("position", {}))
    include_decl = bool(params.get("context", {}).get("includeDeclaration", False))
    line0, char0 = pos.position_at(text, position)
    line0 -= 1
    char0 -= 1
    if line0 < 0:
        return []

    sym = analysis.symbol_at(line0, char0)
    if sym is None:
        return []

    out: list[dict[str, Any]] = []
    for rng in sym.usages:
        if not include_decl and _is_definition(rng, sym, text):
            continue
        out.append(Location(uri=analysis.uri, range=rng).to_dict())
    return out


def _is_definition(rng: Any, sym: Any, text: str) -> bool:
    def_rng = sym.definition_range(text)
    return (def_rng.start.line == rng.start.line
            and def_rng.start.character == rng.start.character)
