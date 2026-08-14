"""``textDocument/hover`` — Markdown context on codons, annotations, symbols.

See doc/03 §10.1: codon decode + amino acid + family table; annotation grammar;
gene/promoter symbol summary; field semantics.
"""

from __future__ import annotations

from typing import Any

from helixlang_lsp import codons
from helixlang_lsp import positions as pos
from helixlang_lsp.analysis import Analysis, AnnotationInfo, SymbolInfo
from helixlang_lsp.codons import amino_acid, decode_codon
from helixlang_lsp.protocol import Hover, MarkupContent, Position

ANNOTATION_DOCS: dict[str, str] = {
    "gene": "**#gene** — a functional unit of DNA.\n\n"
            "Fields: `name=` (required), `promoter=` (optional), "
            "`call_target=` (optional).\n"
            "Body: an ORF beginning with `ATG` (START) and ending with a "
            "stop codon (`TAA`/`TAG`/`TGA`).",
    "promoter": "**#promoter** — a regulation site.\n\n"
                "Fields: `name=` (required), `strength=` (required).",
    "regulate": "**#regulate** — a regulation edge `source -> target`.",
    "lsystem": "**#lsystem** — a plant morphology grammar.\n\n"
               "Fields: `name=`, `axiom=`, `rules=`.",
    "field": "**#field** — a global environment field.\n\n"
             "Fields: `name=`, `size=`, `init=`.",
    "config": "**#config** — runtime configuration.\n\n"
              "Fields: `table=` (standard | mito_vertebrate | ciliate), "
              "`ticks=`, `output=` (stdout | csv | png | none), "
              "`ops_per_tick=`, `react_steps=`, `use_central_dogma=`, "
              "`species=` (ecoli | yeast | human), `units=` (gameplay | real).",
    "type": "**#type** — a symbolic type declaration `symbol=Type`.",
    "crispr": "**#crispr** — CRISPR editing instruction. "
              "Fields: `target=`, `cas=` (SpCas9 | SaCas9 | Cas12a), "
              "`repair=` (NHEJ | HDR).",
    "evolve": "**#evolve** — evolution instruction. Fields: `target=`, `mutation=`.",
    "methylate": "**#methylate** — methylation instruction. "
                 "Fields: `target=`, `mark=` "
                 "(H3K4me3 | H3K27me3 | H3K36me3 | H3K9me3 | H3K27ac).",
    "histone": "**#histone** — histone modification instruction. "
               "Fields: `target=`, `mark=`.",
    "transcribe": "**#transcribe** — transcription instruction. Fields: `target=`.",
    "translate": "**#translate** — translation instruction. Fields: `target=`.",
    "quorum": "**#quorum** — quorum-sensing instruction. Fields: `target=`.",
    "media": "**#media** — growth-medium declaration (repeatable).\n\n"
              "Fields: `nutrient=` (required), `concentration=` (required), "
              "`diffusion_um2_s=` (optional).\n"
              "Sets the FBA uptake bound / environment field for the sim "
              "backends; inert under `classic`.",
    "enzyme": "**#enzyme** — gene→reaction binding for enzyme-constrained FBA "
              "(repeatable).\n\n"
              "Fields: `gene=` (required), `reaction=` (required), "
              "`kcat=` (optional).\n"
              "When `#config enzyme_capacity=true` and no `#enzyme` is given, "
              "the default enzyme tables are used.",
    "metabolite": "**#metabolite** — intracellular pool initialisation "
                  "(repeatable).\n\n"
                  "Fields: `name=` (required), `init=` (optional, default 0.0).\n"
                  "Requires `#config metabolite_pools=true` to take effect; "
                  "inert under `classic`.",
    "sim": "**#sim** — open `key=value` extension point (repeatable).\n\n"
           "Merges fields into `Program.sim_extensions` for long-tail "
           "backends, e.g. `#sim kind=spatial_dfba`. "
           "Inert until a backend registers it.",
    "end": "**#end** — terminates the current annotation block.",
    "dna": "**#dna** — a raw DNA body (codons outside annotations).",
}


def hover(text: str, analysis: Analysis, params: dict[str, Any]) -> dict[str, Any] | None:
    """Handle ``textDocument/hover``. Returns a serializable Hover or ``None``."""
    position = Position.from_dict(params.get("position", {}))
    line0, char0 = pos.position_at(text, position)
    line0 -= 1
    char0 -= 1
    if line0 < 0:
        return None

    codon = _codon_at(analysis, line0, char0)
    if codon is not None:
        return _hover_codon(codon, analysis)

    ann = _annotation_at(analysis, line0, char0)
    if ann is not None:
        return _hover_annotation(ann, analysis)

    sym = analysis.symbol_at(line0, char0)
    if sym is not None:
        return _hover_symbol(sym, analysis)

    field = _field_at(analysis, line0, char0)
    if field is not None:
        ann2, f = field
        return _hover_field(ann2, f)

    return None


# --------------------------------------------------------------------------
# hit-testing
# --------------------------------------------------------------------------

def _codon_at(analysis: Analysis, line0: int, char0: int) -> Any | None:
    for ci in analysis.structure.codon_tokens:
        if ci.line0 == line0 and ci.col0 <= char0 <= ci.col0 + len(ci.seq):
            return ci
    return None


def _annotation_at(analysis: Analysis, line0: int, char0: int) -> AnnotationInfo | None:
    for ann in analysis.structure.annotations:
        if ann.line0 == line0 and ann.col0 <= char0 <= ann.col0 + len(ann.kind) + 1:
            return ann
    return None


def _field_at(analysis: Analysis, line0: int,
              char0: int) -> tuple[AnnotationInfo, Any] | None:
    for ann in analysis.structure.annotations:
        for f in ann.fields:
            if f.line0 == line0 and f.key_start <= char0 <= f.value_end:
                return ann, f
    return None


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------

def _hover_codon(codon: Any, analysis: Analysis) -> dict[str, Any]:
    decoded = decode_codon(codon.seq, analysis.table_name)
    if decoded is None:
        body = (f"`{codon.seq}` — **unknown codon** for table "
                f"`{analysis.table_name}`.")
    else:
        op, w = decoded
        aa = amino_acid(codon.seq)
        aa_txt = f" ({aa[0]}, {aa[1]})" if aa else ""
        body = (
            f"`{codon.seq}` **→ {op.name}**{aa_txt}  \n"
            f"operand = {w} (wobble {codons.wobble_base(codon.seq)})  \n"
            f"table: `{analysis.table_name}`"
        )
        family = codons.codon_family(op)
        if family:
            body += "\n\n**Family aliases:**\n\n" + ", ".join(
                f"`{c}`" for c in family)
    return Hover(contents=MarkupContent(value=body),
                 range=_codon_range(codon)).to_dict()


def _codon_range(codon: Any) -> Any:
    from helixlang_lsp.protocol import Position, Range
    return Range(start=Position(line=codon.line0, character=codon.col0),
                 end=Position(line=codon.line0, character=codon.col0 + 3))


def _hover_annotation(ann: AnnotationInfo, analysis: Analysis) -> dict[str, Any]:
    doc = ANNOTATION_DOCS.get(ann.kind)
    if doc is None:
        doc = f"**#{ann.kind}** — annotation block."
    lines = doc.split("\n")
    body = "\n".join(f"  \n{ln}" if ln.startswith("**") else ln for ln in lines)
    return Hover(contents=MarkupContent(value=body),
                 range=_line_range(ann.line0)).to_dict()


def _hover_symbol(sym: SymbolInfo, analysis: Analysis) -> dict[str, Any]:
    lines = [f"**{sym.kind}** `{sym.name}`"]
    lines.append(f"defined at line {sym.def_line0 + 1}")
    # find annotation details
    ann = next((a for a in analysis.structure.annotations
                if a.kind == sym.kind and _field_value(a, "name") == sym.name),
               None)
    if ann is not None:
        promoter = _field_value(ann, "promoter")
        if promoter:
            lines.append(f"promoter: `{promoter}`")
        orf = [c.seq for c in ann.body_codons]
        if orf:
            aa_count = len(orf) - 1 if orf else 0
            start = orf[0] if orf else "?"
            stop = orf[-1] if len(orf) > 1 else "?"
            lines.append(f"ORF: `{start} … {stop}`, {len(orf)} codons "
                         f"({max(aa_count, 0)} amino acids)")
    edges = _regulation_edges(analysis, sym.name)
    if edges:
        lines.append("**Regulation:** " + "; ".join(edges))
    usages = len(sym.usages)
    if usages:
        lines.append(f"{usages} reference{'s' if usages > 1 else ''}")
    return Hover(contents=MarkupContent(value="  \n".join(lines)),
                 range=_line_range(sym.def_line0)).to_dict()


def _hover_field(ann: AnnotationInfo, f: Any) -> dict[str, Any]:
    body = f"Field **`{f.key}`** of **#{ann.kind}**  \nvalue: `{f.value}`"
    if f.key == "strength":
        body += "\n\nRange 0.0–1.0; higher binds/activates more strongly."
    elif f.key == "table":
        body += "\n\nOne of `standard`, `mito_vertebrate`, `ciliate`."
    elif f.key == "species":
        body += "\n\nOne of `ecoli`, `yeast`, `human`."
    elif f.key == "units":
        body += "\n\nOne of `gameplay`, `real`."
    elif f.key == "output":
        body += "\n\nOne of `stdout`, `csv`, `png`, `none`."
    elif f.key == "cas":
        body += "\n\nOne of `SpCas9`, `SaCas9`, `Cas12a`."
    elif f.key == "repair":
        body += "\n\nOne of `NHEJ`, `HDR`."
    elif f.key == "mark":
        body += "\n\nOne of `H3K4me3`, `H3K27me3`, `H3K36me3`, `H3K9me3`, `H3K27ac`."
    elif f.key == "backend":
        body += "\n\nOne of `classic`, `whole_cell`, `population`, `fba`, " \
                "`calibration`, `benchmark` (default `classic`)."
    elif f.key == "seed":
        body += "\n\n`int | none` — RNG seed (adder noise, GRN/population " \
                "noise, calibration). Same source + same seed ⇒ identical output."
    elif f.key == "nutrient":
        body += "\n\nMetabolite id (e.g. `GLC`, `O2`, `AC`)."
    elif f.key == "concentration":
        body += "\n\nMedium concentration (mM); sets the FBA uptake bound / " \
                "environment field."
    elif f.key == "diffusion_um2_s":
        body += "\n\nFick diffusion coefficient (µm²/s); population field only."
    elif f.key == "gene":
        body += "\n\nGene symbol bound to the reaction (must match a `#gene` name)."
    elif f.key == "reaction":
        body += "\n\nReaction id in the model."
    elif f.key == "kcat":
        body += "\n\nEnzyme turnover (s⁻¹); overrides the default kcat table."
    elif f.key == "init":
        body += "\n\nInitial pool value."
    elif f.key == "division_rule":
        body += "\n\nOne of `energy`, `adder`."
    elif f.key == "replication_mode":
        body += "\n\nOne of `flat`, `cooper_helmstetter`."
    elif f.key == "protein_maturation_mode":
        body += "\n\nOne of `instant`, `chaperone`."
    elif f.key == "mechanics":
        body += "\n\nOne of `none`, `shoving`, `force`."
    elif f.key == "fba_model":
        body += "\n\n`core | <path>` — `ECOLI_CORE_MODEL` or an SBML/JSON model path."
    return Hover(contents=MarkupContent(value=body),
                 range=_line_range(f.line0)).to_dict()


def _field_value(ann: AnnotationInfo, key: str) -> str | None:
    for f in ann.fields:
        if f.key == key:
            return f.value
    return None


def _regulation_edges(analysis: Analysis, name: str) -> list[str]:
    out: list[str] = []
    prog = analysis.program
    if prog is None:
        return out
    for r in prog.regulations:
        if r.source == name:
            out.append(f"`{r.source}` → `{r.target}`")
        elif r.target == name:
            out.append(f"`{r.source}` → `{r.target}`")
    return out


def _line_range(line0: int) -> Any:
    from helixlang_lsp.protocol import Position, Range
    return Range(start=Position(line=line0, character=0),
                 end=Position(line=line0, character=0))
