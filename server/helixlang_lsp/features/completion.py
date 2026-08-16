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

CONFIG_CLASSIC_KEYS = ["ticks", "output", "table", "ops_per_tick",
                       "react_steps", "use_central_dogma", "species", "units"]

# helix-language-wiring.md §6.2: sim-backend keys preserved verbatim in
# Program.config.sim. Names mirror the target dataclass fields.
SIM_KEYS = [
    # common
    "seed",
    # whole-cell (VirtualCellConfig)
    "division_rule", "division_energy", "adder_volume_um3", "adder_noise_std",
    "volume_init_um3", "biomass_to_volume_pg_per_min", "cell_density_dry_pg_um3",
    "surface_scaling", "surface_exponent", "replication_mode", "c_period_min",
    "d_period_min", "doubling_time_min", "chromosome_map", "energy_init",
    "maintenance_atp_per_min", "biomass_to_atp", "transcription_atp_per_nt",
    "translation_atp_per_aa", "protein_yield_per_mrna", "minutes_per_step",
    "enzyme_capacity", "enzyme_scale", "protein_mass_fraction",
    "metabolite_pools", "protein_maturation_mode", "frac_cotranslational_fold",
    "folding_atp_per_protein", "k_fold", "misfold_rate_per_min",
    "aggregation_rate_per_min", "degraded_rate_per_min", "protein_half_life_min",
    # population (PopulationConfig)
    "population_size", "grid_width", "grid_height", "grid_depth",
    "division_threshold", "death_threshold", "signaling", "signal_diffusion",
    "signal_threshold", "crowding", "mechanics", "noise_enabled", "noise_seed",
    "trace_streaming", "dfba", "dfba_dt_h", "dfba_energy_scale",
    "dfba_initial_biomass_gdw", "dfba_glucose_half_saturation_mm",
    "dfba_oxygen_max_uptake", "dfba_oxygen_half_saturation_mm",
    # fba (DynamicFluxBalance)
    "fba_model", "dynfba", "fba_dt_h", "fba_glucose_mm", "fba_oxygen_max",
    "fba_steps",
    # replicons (doc/19 §5.5 C2)
    "replicons",
    # ecosystem (doc/19 §5.3-§5.6; apps/ecosystem.py)
    "fast_forward", "scheduler_max_step", "community_fba", "sample_every",
    "generations", "evaluation_ticks", "evolution_enabled", "stress_field",
    "stress_level",
    # population DBTL (doc/19 §5.6 D3; apps/population_dbtl.py)
    "n_rounds", "substrate", "vmax", "ks", "substrate_mm", "initial_nh4_mm",
    "carrying_capacity", "target_protein", "mutation_rate", "bias_fraction",
    "n_candidates",
]

FIELD_SETS: dict[str, list[str]] = {
    "gene": ["name", "promoter", "call_target", "replicon"],
    "promoter": ["name", "strength"],
    "regulate": [],
    "lsystem": ["name", "axiom", "rules"],
    "field": ["name", "size", "init"],
    "config": CONFIG_CLASSIC_KEYS + ["backend"] + SIM_KEYS,
    "type": ["name"],
    "crispr": ["target", "cas", "repair"],
    "evolve": ["target", "mutation"],
    "methylate": ["target", "mark"],
    "histone": ["target", "mark"],
    "transcribe": ["target"],
    "translate": ["target"],
    "quorum": ["target"],
    "media": ["nutrient", "concentration", "diffusion_um2_s"],
    "enzyme": ["gene", "reaction", "kcat"],
    "metabolite": ["name", "init"],
    "sim": ["kind"],
    "genome": ["source", "tf_map", "grn_mode", "active_gene_budget", "seed"],
    "morphogen": ["gene", "channel", "gain"],
    "species": ["name", "genome", "photo", "photo_vmax", "cn_ratio",
                "maintenance", "substrate", "vmax", "ks", "substrate2",
                "vmax2", "ks2", "secretion", "diet", "attack"],
    "patch": ["name", "kind", "width", "height", "carrying_capacity",
              "anoxic", "moisture", "clay", "cn_som", "cn_species",
              "initial_nh4_mm", "initial_no3_mm", "flow_rate",
              "fluctuation_period", "fluctuation_amplitude", "dispersal"],
}

LONG_TAIL_KINDS = [
    "3d_morphology", "codec_benchmark", "codon_usage", "cello_workflow",
    "consortium", "digital_evolution", "directed_evolution", "ecosystem",
    "fate_analysis", "morphogen_gradient", "omics_calibration",
    "population_calibration", "population_dbtl", "protein_fitness",
    "protein_structure", "spatial_dfba", "spatial_evolution", "stochastic",
    "synbio_design",
]

PATCH_KINDS = ["water", "sediment", "chemostat", "soil", "biofilm"]

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
    "nutrient": "Metabolite id (e.g. GLC, O2, AC).",
    "concentration": "Medium concentration (mM); FBA uptake bound.",
    "diffusion_um2_s": "Fick diffusion coefficient (µm²/s).",
    "gene": "Gene symbol bound to the reaction.",
    "reaction": "Reaction id in the model.",
    "kcat": "Enzyme turnover (s⁻¹).",
    "kind": "`#sim` backend selector; `#patch` habitat kind.",
    "replicon": "Replicon name (must match a `#config sim replicons=` entry).",
    "replicons": "`name:copy,...` — e.g. `pBR322:20` (chromosome implicit, fork-driven).",
    "source": "Genome source: `ecoli-mg1655` | `synth-4300` | model path.",
    "tf_map": "regulon | random | regulondb | off — transcription-factor map.",
    "grn_mode": "sparse | full — GRN topology.",
    "active_gene_budget": "Per-cell per-tick active-gene budget (default 512).",
    "channel": "U | V — morphogen channel.",
    "gain": "Feedback gain (float, default 0.1).",
    "genome": "Species genotype: a genome= source or a DNA code block.",
    "photo": "bool: light-gated photoautotrophy.",
    "photo_vmax": "Max CO₂ fixation rate (per biomass C per tick).",
    "cn_ratio": "Biomass C:N ratio (CENTURY N cycle).",
    "maintenance": "Per-tick biomass fraction respired (maintenance + mortality).",
    "substrate": "Growth substrate (dotted `consumption.<sub>.vmax/.ks` also accepted).",
    "vmax": "Uptake vmax (per biomass C per tick).",
    "ks": "Uptake half-saturation Ks (mM).",
    "substrate2": "Second growth substrate (with `vmax2`/`ks2`).",
    "vmax2": "Uptake vmax for `substrate2`.",
    "ks2": "Half-saturation Ks for `substrate2` (mM).",
    "secretion": "`sub:<rate>` — cross-feeding secretion (mM per biomass C per tick).",
    "diet": "`prey:<efficiency>` — predation conversion efficiency.",
    "attack": "`prey:<rate>` — mass-action attack rate.",
    "width": "Patch lattice width (well-mixed uses 1x1).",
    "height": "Patch lattice height.",
    "carrying_capacity": "Total biomass-C (mmol) density cap.",
    "anoxic": "bool: no initial oxygen.",
    "moisture": "Water-filled pore-space fraction (soil; DAMM).",
    "clay": "Clay fraction slowing active→slow SOM transfer (CENTURY).",
    "cn_som": "Soil organic-matter C:N ratio.",
    "cn_species": "Species C:N ratio.",
    "initial_nh4_mm": "Initial NH₄⁺ (mM).",
    "initial_no3_mm": "Initial NO₃⁻ (mM).",
    "flow_rate": "Chemostat refresh rate (0 = sealed/batch).",
    "fluctuation_period": "Periodic substrate-supply forcing period (ticks; 0 off).",
    "fluctuation_amplitude": "Forcing amplitude.",
    "dispersal": "`dispersal.<neighbor>=<rate>` — per-tick migration fraction.",
    "fast_forward": "bool: event-driven fast-forward of quiescent epochs.",
    "scheduler_max_step": "Longest fast-forward hop (ticks).",
    "community_fba": "bool: OptCom-style community FBA engine.",
    "sample_every": "Observation sampling stride (ticks).",
    "generations": "Evolution generations (1 disables the outer loop).",
    "evaluation_ticks": "Fitness-evaluation window (ticks).",
    "evolution_enabled": "bool: invasion-fitness evolution loop.",
    "stress_field": "Scalar field driving selection (default `toxin`).",
    "stress_level": "Ambient stress-field level.",
    "n_rounds": "DBTL rounds.",
    "substrate_mm": "Batch substrate (mM).",
    "target_protein": "Protein sequence the DBTL loop evolves toward.",
    "mutation_rate": "Mutation rate per site.",
    "bias_fraction": "Unsaturated-trait biasing fraction.",
    "n_candidates": "Candidates tested per round.",
    "backend": "classic | whole_cell | population | fba | calibration | benchmark",
    "seed": "int | none: RNG seed for determinism.",
    "division_rule": "energy | adder",
    "division_energy": "ATP division threshold.",
    "adder_volume_um3": "Adder volume increment (default 1.6).",
    "adder_noise_std": "Relative Gaussian noise on the adder rule.",
    "volume_init_um3": "Newborn cell volume.",
    "biomass_to_volume_pg_per_min": "Volume-model coupling.",
    "cell_density_dry_pg_um3": "Dry density rho (default 0.15).",
    "surface_scaling": "bool: S/V uptake scaling.",
    "surface_exponent": "float: default 2/3.",
    "replication_mode": "flat | cooper_helmstetter",
    "c_period_min": "Cooper–Helmstetter C-period (min).",
    "d_period_min": "Cooper–Helmstetter D-period (min).",
    "doubling_time_min": "Doubling time (min).",
    "chromosome_map": "dict: gene=coord,... with coord in [0,1].",
    "energy_init": "Initial ATP budget.",
    "maintenance_atp_per_min": "Maintenance ATP flux.",
    "biomass_to_atp": "ATP per biomass flux.",
    "transcription_atp_per_nt": "Transcription energy cost per nt.",
    "translation_atp_per_aa": "Translation energy cost per aa.",
    "protein_yield_per_mrna": "Proteins per mRNA.",
    "minutes_per_step": "Simulation step (min, default 1.0).",
    "enzyme_capacity": "bool: Phase-4 MOMENT enzyme caps.",
    "enzyme_scale": "kcat rescale factor.",
    "protein_mass_fraction": "sMOMENT pool mass fraction.",
    "metabolite_pools": "bool: pool ODE integration.",
    "protein_maturation_mode": "instant | chaperone",
    "frac_cotranslational_fold": "Fraction of cotranslational folding.",
    "folding_atp_per_protein": "ATP cost per folded protein.",
    "k_fold": "Fold-rate constant (derives fold_rate_per_min).",
    "misfold_rate_per_min": "Misfolding rate.",
    "aggregation_rate_per_min": "Aggregation rate.",
    "degraded_rate_per_min": "Degradation rate.",
    "protein_half_life_min": "Protein half-life (min).",
    "population_size": "Colony max cell count.",
    "grid_width": "Lattice width.",
    "grid_height": "Lattice height.",
    "grid_depth": "Lattice depth.",
    "division_threshold": "Division energy gate.",
    "death_threshold": "Death energy gate.",
    "signaling": "bool: AI-2 quorum field.",
    "signal_diffusion": "Signal diffusion (µm²/s).",
    "signal_threshold": "Quorum threshold (µM).",
    "crowding": "bool: CROMICS crowding factor.",
    "mechanics": "none | shoving | force",
    "noise_enabled": "bool: per-cell GRN noise.",
    "noise_seed": "GRN noise RNG seed.",
    "trace_streaming": "bool: per-cell snapshot streaming.",
    "dfba": "bool: per-cell dynamic FBA.",
    "dfba_dt_h": "dFBA integration step (h).",
    "dfba_energy_scale": "dFBA energy scale.",
    "dfba_initial_biomass_gdw": "Initial biomass (gDW).",
    "dfba_glucose_half_saturation_mm": "Glucose Ks (mM).",
    "dfba_oxygen_max_uptake": "Oxygen max uptake.",
    "dfba_oxygen_half_saturation_mm": "Oxygen Ks (mM).",
    "fba_model": "core | <path> (SBML/JSON model).",
    "dynfba": "bool: DynamicFluxBalance batch.",
    "fba_dt_h": "dFBA integration step (h).",
    "fba_glucose_mm": "Batch glucose (mM).",
    "fba_oxygen_max": "Respiratory O2 cap.",
    "fba_steps": "dFBA iteration count.",
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
    "backend": ["classic", "whole_cell", "population", "fba",
                "calibration", "benchmark"],
    "division_rule": ["energy", "adder"],
    "replication_mode": ["flat", "cooper_helmstetter"],
    "protein_maturation_mode": ["instant", "chaperone"],
    "mechanics": ["none", "shoving", "force"],
    "fba_model": ["core"],
    "seed": ["none"],
    "surface_scaling": ["true", "false"],
    "enzyme_capacity": ["true", "false"],
    "metabolite_pools": ["true", "false"],
    "signaling": ["true", "false"],
    "crowding": ["true", "false"],
    "noise_enabled": ["true", "false"],
    "trace_streaming": ["true", "false"],
    "dfba": ["true", "false"],
    "dynfba": ["true", "false"],
    "kind": LONG_TAIL_KINDS,
    "source": ["ecoli-mg1655", "synth-4300"],
    "tf_map": ["regulon", "random", "regulondb", "off"],
    "grn_mode": ["sparse", "full"],
    "channel": ["U", "V"],
    "photo": ["true", "false"],
    "anoxic": ["true", "false"],
    "fast_forward": ["true", "false"],
    "community_fba": ["true", "false"],
    "evolution_enabled": ["true", "false"],
}

TYPE_VALUES = ["Protein", "Signal", "Float", "Int", "Bool", "String",
               "Gene", "Record", "Any"]

ANNOTATION_KINDS = ["gene", "promoter", "regulate", "lsystem", "field",
                    "config", "type", "crispr", "evolve", "methylate",
                    "histone", "transcribe", "translate", "quorum",
                    "media", "enzyme", "metabolite", "sim", "genome",
                    "morphogen", "species", "patch"]

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
        if field in ("promoter", "call_target", "target", "gene") or \
                (field == "source" and ctx.get("ann_kind") != "genome"):
            role = "promoter" if field == "promoter" else "target"
            items = [_symbol_item(n, s, n)
                     for n, s in analysis.structure.symbols.items()
                     if _role_ok(s.kind, role)]
            return _filter_prefix(items, ctx.get("prefix", ""))
        values = _enum_values(field, ctx.get("ann_kind", ""))
        return [_enum_item(field, v, v) for v in values]
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


def _enum_values(field: str, ann_kind: str) -> list[str]:
    """Enum values for ``field``; ``kind`` is context-dependent."""
    if field == "kind":
        if ann_kind == "patch":
            return PATCH_KINDS
        return LONG_TAIL_KINDS
    return ENUM_VALUES.get(field, [])


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
