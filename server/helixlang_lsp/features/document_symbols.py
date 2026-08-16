"""``textDocument/documentSymbol`` — hierarchical document symbols.

Hierarchy per doc/03 §10.4: gene=Function, promoter=Variable, regulation=
Operator, lsystem=Class, field=Class, config=Constant, bio instructions=Event.
``selectionRange`` is the name range; ``range`` is the whole block.
"""

from __future__ import annotations

from typing import Any

from helixlang_lsp import positions as pos
from helixlang_lsp.analysis import Analysis
from helixlang_lsp.protocol import DocumentSymbol, SymbolKind

_KIND_MAP: dict[str, int] = {
    "gene": SymbolKind["function"],
    "promoter": SymbolKind["variable"],
    "regulate": SymbolKind["operator"],
    "lsystem": SymbolKind["class"],
    "field": SymbolKind["class"],
    "config": SymbolKind["constant"],
    "type": SymbolKind["type_parameter"],
    "crispr": SymbolKind["event"],
    "evolve": SymbolKind["event"],
    "methylate": SymbolKind["event"],
    "histone": SymbolKind["event"],
    "transcribe": SymbolKind["event"],
    "translate": SymbolKind["event"],
    "quorum": SymbolKind["event"],
    "media": SymbolKind["class"],
    "enzyme": SymbolKind["class"],
    "metabolite": SymbolKind["class"],
    "sim": SymbolKind["event"],
    "genome": SymbolKind["constant"],
    "morphogen": SymbolKind["field"],
    "species": SymbolKind["class"],
    "patch": SymbolKind["class"],
    "dna": SymbolKind["module"],
}


def document_symbols(text: str, analysis: Analysis,
                     _params: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle ``textDocument/documentSymbol``."""
    anns = analysis.structure.annotations
    out: list[DocumentSymbol] = []
    for ann in anns:
        name = _symbol_name(ann)
        kind = _KIND_MAP.get(ann.kind, SymbolKind["key"])
        start = ann.line0
        end = ann.end_line0 if ann.has_end and ann.end_line0 is not None \
            else _block_end(text, ann, anns)
        block_range = pos.whole_line_range(text, start)
        block_range.end = pos.linecol_to_position(text, end + 1, 1)
        sel = _selection_range(text, ann, name)
        out.append(DocumentSymbol(
            name=name, detail=ann.kind, kind=kind,
            range=block_range, selection_range=sel,
        ))
    if analysis.structure.dna_blocks:
        for blk in analysis.structure.dna_blocks:
            rng = pos.whole_line_range(text, blk.start_line0)
            rng.end = pos.linecol_to_position(text, blk.end_line0 + 1, 1)
            out.append(DocumentSymbol(
                name="DNA", detail="dna", kind=SymbolKind["module"],
                range=rng, selection_range=rng,
            ))
    return [s.to_dict() for s in out]


def _name_field(ann: Any) -> str:
    return next((f.value for f in ann.fields if f.key == "name"), "")


def _symbol_name(ann: Any) -> str:
    if ann.kind == "media":
        nut = next((f.value for f in ann.fields if f.key == "nutrient"), "")
        return f"Media nutrient={nut}"
    if ann.kind == "enzyme":
        gene = next((f.value for f in ann.fields if f.key == "gene"), "")
        return f"Enzyme gene={gene}"
    if ann.kind == "metabolite":
        name = next((f.value for f in ann.fields if f.key == "name"), "")
        return f"Metabolite name={name}"
    if ann.kind == "sim":
        kind = next((f.value for f in ann.fields if f.key == "kind"), "")
        return f"Sim kind={kind}" if kind else "Sim"
    if ann.kind == "genome":
        src = next((f.value for f in ann.fields if f.key == "source"), "")
        return f"Genome source={src}" if src else "Genome"
    if ann.kind == "morphogen":
        gene = next((f.value for f in ann.fields if f.key == "gene"), "")
        return f"Morphogen gene={gene}" if gene else "Morphogen"
    if ann.kind == "species":
        genome = next((f.value for f in ann.fields if f.key == "genome"), "")
        return f"Species {_name_field(ann)}" \
            + (f" genome={genome}" if genome else "")
    if ann.kind == "patch":
        kind = next((f.value for f in ann.fields if f.key == "kind"), "")
        return f"Patch {_name_field(ann)}" + (f" kind={kind}" if kind else "")
    for f in ann.fields:
        if f.key == "name":
            return f.value
    if ann.kind == "regulate":
        src = next((f.value for f in ann.fields if f.key == "__arrow_src"), "")
        tgt = next((f.value for f in ann.fields if f.key == "__arrow_tgt"), "")
        return f"{src} -> {tgt}".strip(" -")
    if ann.kind == "config":
        return "Config"
    return ann.kind.capitalize()


def _block_end(text: str, ann: Any, anns: list[Any]) -> int:
    """Last line of an unclosed block = line before next annotation (or EOF)."""
    lines = text.split("\n")
    nxt = min((a.line0 for a in anns if a.line0 > ann.line0),
              default=len(lines))
    return max(ann.line0, nxt - 1)


def _selection_range(text: str, ann: Any, name: str) -> Any:
    for f in ann.fields:
        if f.key == "name":
            return pos.token_span_to_range(text, f.line0 + 1, f.value_start + 1,
                                           len(f.value))
    return pos.whole_line_range(text, ann.line0)
