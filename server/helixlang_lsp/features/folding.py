"""``textDocument/foldingRange`` — annotation blocks and long DNA bodies.

Doc/03 §10.5: ``#gene … #end`` blocks and DNA bodies longer than 3 lines get
``region`` folding ranges.
"""

from __future__ import annotations

from typing import Any

from helixlang_lsp.analysis import Analysis
from helixlang_lsp.protocol import FoldingRange


def folding_ranges(text: str, analysis: Analysis,
                   _params: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle ``textDocument/foldingRange``."""
    out: list[FoldingRange] = []

    for ann in analysis.structure.annotations:
        end = ann.end_line0 if ann.has_end and ann.end_line0 is not None \
            else _eof_or_next(text, analysis, ann)
        if end - ann.line0 >= 1:
            out.append(FoldingRange(
                start_line=ann.line0, end_line=end, kind="region"))

    for blk in analysis.structure.dna_blocks:
        if blk.end_line0 - blk.start_line0 >= 2:
            out.append(FoldingRange(
                start_line=blk.start_line0, end_line=blk.end_line0, kind="region"))

    return [r.to_dict() for r in out]


def _eof_or_next(text: str, analysis: Analysis, ann: Any) -> int:
    """Last foldable line for an unclosed block."""
    nxt = min((a.line0 for a in analysis.structure.annotations
               if a.line0 > ann.line0),
              default=text.count("\n"))
    return max(ann.line0, nxt - 1)
