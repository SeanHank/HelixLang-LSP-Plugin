"""``textDocument/definition`` — resolve symbol references to definitions.

Resolves gene/promoter symbols (references from ``#regulate``, ``promoter=``,
``target=``, ``call_target=``, codon ``OP_CALL_GENE`` wobble mapping, ``#type``
symbol keys) to their definition ``Location`` (doc/03 §10.3).
"""

from __future__ import annotations

from typing import Any

from helixlang_lsp import positions as pos
from helixlang_lsp.analysis import Analysis
from helixlang_lsp.protocol import Location, Position


def definitions(text: str, analysis: Analysis,
                params: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Handle ``textDocument/definition``."""
    position = Position.from_dict(params.get("position", {}))
    line0, char0 = pos.position_at(text, position)
    line0 -= 1
    char0 -= 1
    if line0 < 0:
        return None

    sym = analysis.symbol_at(line0, char0)
    if sym is None:
        return None
    rng = sym.definition_range(text)
    return [Location(uri=analysis.uri, range=rng).to_dict()]
