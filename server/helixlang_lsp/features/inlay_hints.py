"""``textDocument/inlayHint`` — decoded-opcode hints after each codon.

Doc/03 §10.8: for each codon in a gene body, a hint positioned after the
codon text carrying ``{kind:"codon", opcode, operand, codon, table}``.
"""

from __future__ import annotations

from typing import Any

from helixlang_lsp.analysis import Analysis
from helixlang_lsp.codons import decode_codon
from helixlang_lsp.protocol import InlayHint, Position


def inlay_hints(text: str, analysis: Analysis,
                _params: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle ``textDocument/inlayHint``."""
    hints: list[InlayHint] = []
    for ann in analysis.structure.annotations:
        if ann.kind != "gene":
            continue
        for ci in ann.body_codons:
            decoded = decode_codon(ci.seq, analysis.table_name)
            if decoded is None:
                continue
            op, operand = decoded
            label = op.name
            if ci.operand is not None and ci.opcode == op.name:
                label += f" arg={ci.operand}"
            hints.append(InlayHint(
                position=Position(line=ci.line0, character=ci.col0 + len(ci.seq)),
                label=label,
                kind=1,
                padding_right=True,
                data={"kind": "codon", "opcode": op.name, "operand": operand,
                      "codon": ci.seq, "table": analysis.table_name},
            ))
    return [h.to_dict() for h in hints]
