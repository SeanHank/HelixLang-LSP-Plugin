"""``textDocument/completion`` — context-sensitive items.

See doc/03 §10.2. Trigger characters ``# = >``; contexts: annotation kinds,
per-kind fields, enum values, symbol names, codon snippets, type values.
"""

from __future__ import annotations

from typing import Any

from helixlang_lsp import _helix_contract as helix
from helixlang_lsp import codons
from helixlang_lsp import positions as pos
from helixlang_lsp.analysis import Analysis
from helixlang_lsp.protocol import (
    CompletionItem,
    CompletionKind,
    CompletionList,
    MarkupContent,
    Position,
)

FIELD_SETS: dict[str, list[str]] = {
    "gene": ["name", "promoter", "call_target"],
    "promoter": ["name", "strength"],
    "regulate": [],
    "lsystem": ["name", "axiom", "rules"],
    "field": ["name", "size", "init"],
    "config": ["ticks", "output", "table", "ops_per_tick", "react_steps",
               "use_central_dogma", "species", "units"],
    "type": ["name"],
    "crispr": ["target", "cas", "repair"],
    "evolve": ["target", "mutation"],
    "methylate": ["target", "mark"],
    "histone": ["target", "mark"],
    "transcribe": ["target"],
    "translate": ["target"],
    "quorum": ["target"],
}

FIELD_DOCS: dict[str, str] = {
    "name": "Symbol name (unique).",
    "promoter": "Promoter driving this gene.",
    "call_target": "Gene called by this gene's body.",
    "strength": "Binding strength, 0.0-1.0.",
    "axiom": "L-system axiom string.",
    "rules": "L-system rewrite rules.",
    "ticks": "Max simulation ticks (<=64 when VM validation on).",
    "output": "stdout | csv | png | none",
    "table": "standard | mito_vertebrate | ciliate",
    "ops_per_tick": "Operations per tick budget.",
    "react_steps": "Reaction-diffusion steps.",
    "use_central_dogma": "bool: central-dogma mode.",
    "species": "ecoli | yeast | human",
    "units": "gameplay | real",
    "target": "Target gene symbol.",
    "cas": "SpCas9 | SaCas9 | Cas12a",
    "repair": "NHEJ | HDR",
    "mark": "H3K4me3 | H3K27me3 | H3K36me3 | H3K9me3 | H3K27ac",
    "mutation": "Mutation kind.",
    "size": "Field size in lattice units.",
    "init": "Initial field value.",
}

ENUM_VALUES: dict[str, list[str]] = {
    "table": ["standard", "mito_vertebrate", "ciliate"],
    "species": ["ecoli", "yeast", "human"],
    "units": ["gameplay", "real"],
    "output": ["stdout", "csv", "png", "none"],
    "cas": ["SpCas9", "SaCas9", "Cas12a"],
    "repair": ["NHEJ", "HDR"],
    "mark": ["H3K4me3", "H3K27me3", "H3K36me3", "H3K9me3", "H3K27ac"],
    "methylase": ["dam", "dcm", "cpg"],
}

TYPE_VALUES = ["Protein", "Signal", "Float", "Int", "Bool", "String",
               "Gene", "Record", "Any"]

ANNOTATION_KINDS = ["gene", "promoter", "regulate", "lsystem", "field",
                    "config", "type", "crispr", "evolve", "methylate",
                    "histone", "transcribe", "translate", "quorum"]

_BIO_KINDS = {"crispr", "evolve", "methylate", "histone", "transcribe",
              "translate", "quorum"}


def completions(text: str, analysis: Analysis,
                params: dict[str, Any]) -> dict[str, Any]:
    """Handle ``textDocument/completion``."""
    position = Position.from_dict(params.get("position", {}))
    line0, char0 = pos.position_at(text, position)
    line0 -= 1
    char0 -= 1
    line = _line(text, line0)
    before = line[:char0]

    ctx = _context(text, analysis, line0, char0, before)
    items = _items_for_context(ctx, analysis)
    items = _sort_items(items, ctx)
    return CompletionList(is_incomplete=False, items=items).to_dict()


# --------------------------------------------------------------------------
# context detection
# --------------------------------------------------------------------------

def _context(text: str, analysis: Analysis, line0: int, char0: int,
             before: str) -> dict[str, Any]:
    """Determine what is being completed on the current line."""
    line = _line(text, line0)

    if before.rstrip().endswith("#"):
        return {"kind": "annotation"}
    if "#" in before:
        m = _re_find(r"#([A-Za-z_][A-Za-z0-9_]*)\s*$", before)
        if m:
            return {"kind": "annotation", "prefix": m.group(1)}

    ann = _current_annotation(analysis, line0)
    if ann is not None:
        key, val = _field_being_edited(line, char0)
        if key is not None:
            return {"kind": "field_value", "field": key, "ann_kind": ann.kind,
                    "prefix": val}
        if ann.kind == "regulate":
            if "->" in before:
                return {"kind": "symbol", "role": "target",
                        "prefix": _word_before(before, char0)}
            return {"kind": "symbol", "role": "source",
                    "prefix": _word_before(before, char0)}
        if _field_region(line, char0):
            return {"kind": "field", "ann_kind": ann.kind,
                    "prefix": _word_before(before, char0)}
        if ann.kind in _BIO_KINDS:
            return {"kind": "symbol", "role": "target",
                    "prefix": _word_before(before, char0)}
        if ann.kind == "gene":
            if line0 > ann.line0:
                return {"kind": "codon", "prefix": _word_before(before, char0)}
            return {"kind": "symbol", "role": "promoter",
                    "prefix": _word_before(before, char0)}
        if ann.kind == "type":
            return {"kind": "type", "prefix": _word_before(before, char0)}

    if _in_body(text, line0):
        return {"kind": "codon", "prefix": _word_before(before, char0)}
    return {"kind": "annotation", "prefix": ""}


def _items_for_context(ctx: dict[str, Any],
                       analysis: Analysis) -> list[CompletionItem]:
    kind = ctx.get("kind")
    prefix = ctx.get("prefix", "")
    if kind == "annotation":
        items = [_annotation_item(k, k) for k in ANNOTATION_KINDS]
        return _filter_prefix(items, prefix)
    if kind == "field":
        return [_field_item(f, ctx.get("ann_kind", ""), f)
                for f in FIELD_SETS.get(ctx.get("ann_kind", ""), [])]
    if kind == "field_value":
        field = ctx.get("field", "")
        if field in ("promoter", "call_target", "target", "source"):
            role = "promoter" if field == "promoter" else "target"
            items = [_symbol_item(n, s, n)
                     for n, s in analysis.structure.symbols.items()
                     if _role_ok(s.kind, role)]
            return _filter_prefix(items, ctx.get("prefix", ""))
        return [_enum_item(field, v, v) for v in ENUM_VALUES.get(field, [])]
    if kind == "symbol":
        role = ctx.get("role", "target")
        return [_symbol_item(n, s, n)
                for n, s in analysis.structure.symbols.items()
                if _role_ok(s.kind, role)]
    if kind == "type":
        return [_type_item(t, t) for t in TYPE_VALUES]
    if kind == "codon":
        return [_codon_item(c, c) for c in sorted(helix.STANDARD_TABLE)]
    return []


def _role_ok(symbol_kind: str, role: str) -> bool:
    if role == "promoter":
        return symbol_kind == "promoter"
    if role == "target":
        return symbol_kind == "gene"
    return True


def _sort_items(items: list[CompletionItem],
                ctx: dict[str, Any]) -> list[CompletionItem]:
    prefix = ctx.get("prefix", "")
    if not prefix:
        return items
    exact = [i for i in items if i.label == prefix]
    starts = [i for i in items if i.label.startswith(prefix) and i.label != prefix]
    rest = [i for i in items if not i.label.startswith(prefix)]
    return exact + starts + rest


def _filter_prefix(items: list[CompletionItem], prefix: str) -> list[CompletionItem]:
    if not prefix:
        return items
    return [i for i in items if i.label.lower().startswith(prefix.lower())]


# --------------------------------------------------------------------------
# item builders
# --------------------------------------------------------------------------

def _annotation_item(label: str, doc_key: str) -> CompletionItem:
    from helixlang_lsp.features.hover import ANNOTATION_DOCS
    doc = ANNOTATION_DOCS.get(doc_key, "")
    return CompletionItem(
        label=label, kind=CompletionKind["keyword"],
        documentation=MarkupContent(value=doc),
        insert_text=label, sort_text="0" + label,
    )


def _field_item(label: str, ann_kind: str, doc_key: str) -> CompletionItem:
    doc = FIELD_DOCS.get(doc_key, "")
    return CompletionItem(
        label=label, kind=CompletionKind["property"],
        documentation=MarkupContent(value=f"**{ann_kind}** field.\n\n{doc}"),
        insert_text=label + "=", sort_text="1" + label,
    )


def _enum_item(field: str, label: str, _v: str) -> CompletionItem:
    return CompletionItem(
        label=label, kind=CompletionKind["value"],
        documentation=MarkupContent(value=f"Allowed value for `{field}`."),
        insert_text=label, sort_text="1" + label,
    )


def _symbol_item(label: str, sym: Any, _v: str) -> CompletionItem:
    kind = CompletionKind["function"] if sym.kind == "gene" else CompletionKind["variable"]
    return CompletionItem(
        label=label, kind=kind,
        detail=f"{sym.kind} · line {sym.def_line0 + 1}",
        documentation=MarkupContent(value=f"**{sym.kind}** `{label}`"),
        insert_text=label, sort_text="1" + label,
    )


def _type_item(label: str, _v: str) -> CompletionItem:
    return CompletionItem(
        label=label, kind=CompletionKind["type_parameter"],
        documentation=MarkupContent(value="Symbolic type name."),
        insert_text=label, sort_text="1" + label,
    )


def _codon_item(label: str, _v: str) -> CompletionItem:
    decoded = codons.decode_codon(label)
    detail = ""
    if decoded is not None:
        op, _w = decoded
        aa = codons.amino_acid(label)
        detail = f"{op.name}" + (f" · {aa[0]}" if aa else "")
    return CompletionItem(
        label=label, kind=CompletionKind["unit"],
        detail=detail,
        documentation=MarkupContent(value=f"Codon `{label}` ({detail})"),
        insert_text=label, sort_text="2" + label,
    )


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _line(text: str, line0: int) -> str:
    lines = text.split("\n")
    if 0 <= line0 < len(lines):
        return lines[line0]
    return ""


def _word_before(before: str, _char0: int) -> str:
    m = _re_find(r"([A-Za-z_][A-Za-z0-9_]*)\s*$", before)
    return m.group(1) if m else ""


def _re_find(pattern: str, s: str):
    import re
    m = re.search(pattern, s)
    return m


def _current_annotation(analysis: Analysis, line0: int) -> Any | None:
    """The innermost annotation block active on ``line0``."""
    active: list[Any] = []
    for ann in analysis.structure.annotations:
        end = ann.end_line0 if ann.has_end and ann.end_line0 is not None else _EOF
        if ann.line0 <= line0 <= end:
            active.append(ann)
    if not active:
        return None
    # innermost = the one that opened most recently
    return max(active, key=lambda a: a.line0)


def _field_being_edited(line: str, char0: int) -> tuple[str | None, str]:
    """Return ``(key, value_prefix)`` if the cursor is on ``key=val``."""
    m = _re_find(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z0-9_]*)$",
                 line[: char0 + 1])
    if m:
        return m.group(1), m.group(2)
    return None, ""


def _field_region(line: str, char0: int) -> bool:
    """True if the cursor sits in the field region (not on the # line)."""
    return "#" in line[: char0 + 1]


_EOF = 1 << 30


def _in_body(text: str, line0: int) -> bool:
    """True if ``line0`` is inside a codon body (gene body or raw DNA)."""
    lines = text.split("\n")
    i = line0
    while i >= 0:
        stripped = lines[i].strip()
        if stripped.startswith("#gene") or _is_codon_line(stripped):
            return True
        if stripped.startswith("#") and not _is_codon_line(stripped):
            return False
        i -= 1
    return False


def _is_codon_line(stripped: str) -> bool:
    return bool(_re_find(r"^[ATCG]{3}(?:[ \t]+[ATCG]{3})+$", stripped))
