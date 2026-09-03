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
            "`call_target=` (optional), `replicon=` (optional; must match a "
            "`#config sim replicons=` entry).\n"
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
              "`species=` (ecoli | yeast | human), `units=` (gameplay | real), "
              "`enzyme_mass_fraction=` (g protein / gDW, default 0.55), "
              "`dry_weight_conc=` (gDW / L, default 0.3).",
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
    "genome": "**#genome** — genome-scale backend switch "
              "(doc/18 §13 Design 5).\n\n"
              "Sets `genome=true`; fields merge into `Program.sim_extensions` "
              "under a `genome_` prefix (same extension point as `#sim`).\n"
              "Fields: `source=` (`ecoli-mg1655` | `synth-4300` | path), "
              "`tf_map=` (`regulon` | `random` | `regulondb` | `off`), "
              "`grn_mode=` (`sparse` | `full`), `active_gene_budget=` "
              "(default 512), `seed=` (default 7).\n"
              "`tf_map=regulondb` imports a real regulatory map "
              "(`parse_regulondb`) instead of the synthetic attachment "
              "(doc/19 §5.5 C1).\n"
              "Inert under the `classic` backend.",
    "morphogen": "**#morphogen** — morphogen→gene feedback wiring.\n\n"
                 "Fields: `gene=` (required), `channel=` (`U` | `V`, "
                 "default `V`), `gain=` (float, default 0.1).",
    "species": "**#species** — a species in the ecosystem backend "
               "(doc/19 §5.3 A2).\n\n"
               "Fields (after `name=`): `genome=` (or a DNA code block, "
               "not both), `photo=`, `photo_vmax=`, `cn_ratio=`, "
               "`maintenance=`, `substrate=`/`vmax=`/`ks=` "
               "(+ `substrate2`/`vmax2`/`ks2`), dotted "
               "`consumption.<sub>.vmax/.ks`, `secretion=<sub>:<rate>`, "
               "`diet=<prey>:<eff>`, `attack=<prey>:<rate>`.\n"
               "Namespaced into `Program.sim_extensions` under "
               "`species.<name>.`; consumed by `#sim kind=ecosystem`.",
    "patch": "**#patch** — a habitat in the ecosystem backend "
             "(doc/19 §5.3 A2, G10).\n\n"
             "Fields (after `name=`): `kind=` (`water` | `sediment` | "
             "`chemostat` | `soil` | `biofilm`), `width=`, `height=`, "
             "`carrying_capacity=`, `anoxic=`, `moisture=`, `clay=`, "
             "`cn_som=`, `cn_species=`, `initial_nh4_mm=`, `initial_no3_mm=`, "
             "`flow_rate=`, `fluctuation_period=`, `fluctuation_amplitude=`, "
             "plus dotted `initial.<species>=`, "
             "`substrate.<sub>.initial/.bulk/.diffusion/.carbon_per_mol`, "
             "`scalar.<name>.kind/.initial/.forcing/.amplitude` and "
             "`dispersal.<neighbor>=`.\n"
             "Namespaced into `Program.sim_extensions` under `patch.<name>.`; "
             "consumed by `#sim kind=ecosystem`.",
    "end": "**#end** — terminates the current annotation block.",
    "dna": "**#dna** — a raw DNA body (codons outside annotations).",
    "gem": "**#gem** — genome-scale model (GEM) reconstruction directive.\n\n"
           "Fields: `organism=` (required; e.g. `e_coli_k12`, "
           "`synechocystis_pcc6803`), `genome=` (FASTA path), "
           "`use_database=` (bool), `include_spontaneous=` (bool), "
           "`gapfill=` (bool), `target_organism=` (display name), "
           "`medium=` (`glucose_minimal` | `lb` | `bg11` | `custom`), "
           "`medium_override=` (comma-separated `met:value` pairs), "
           "`max_growth_rate=` (float cap), "
           "`dynamic=` (bool), `duration=` (hours), `dt=` (hours, "
           "default 0.05), `expression=` (bool), `use_full_model=` (bool).\n"
           "May contain an inline DNA block (codons after fields, "
           "terminated by `#end`) with `#geneId` markers.\n"
           "Repeatable — one block per organism.",
    "reaction": "**#reaction** — DSL-authored metabolic reaction "
                "(repeatable).\n\n"
                "Fields: `id=` (required), `name=`, `substrate=`, `product=`, "
                "`substrate_coeff=` (default −1), `product_coeff=` (default 1), "
                "`lower_bound=` (default 0), `upper_bound=` (default 1000), "
                "`subsystem=` (default `other`), `reversible=` (bool).\n"
                 "Collected into `Program.reactions` and built into a "
                 "`MetabolicModel` by `_build_model_from_reactions()`.",
    "quantity": "**#quantity** — physical-units composition declaration "
                "(doc/41 §6, Ring 1).\n\n"
                "Accepted forms: `#quantity name=TOTAL expr=A+B` or the "
                "compact `#quantity TOTAL=A+B`.\n"
                "`expr=` is a two-atom composition `A+B`/`A-B` where each "
                "atom is a `#type`-annotated symbol or a bare number; "
                "dimension checking runs in the semantic phase "
                "(`DimInferencer`).\n"
                "Stored verbatim under `sim_extensions[\"quantity\"]`.",
    "person": "**#person** — virtual patient demographics "
              "(doc/27, doc/28).\n\n"
              "Fields: `name=`, `age=` (years, default 30), "
              "`sex=` (male | female), `weight=` (kg, default 70), "
              "`height=` (cm, default 170), `ethnicity=` (default european).\n"
              "Stored in `Program.sim_extensions` under `person_` prefix.\n"
              "Consumed by `#sim kind=human` when present.",
    "trait": "**#trait** — patient lifestyle traits "
             "(doc/27, doc/28).\n\n"
             "Fields: `smoking=` (never | former | current), "
             "`pack_years=` (float), `alcohol=` (drinks/week, float), "
             "`exercise=` (sedentary | light | moderate | vigorous), "
             "`pregnant=` (bool).\n"
             "Stored under `trait_` prefix. Consumed by `#sim kind=human`.",
    "disease": "**#disease** — disease state definition "
               "(doc/27, doc/28).\n\n"
               "Fields: `name=`, `category=` (e.g. metabolic_overload), "
               "`severity=` (0.0–1.0), `onset_age=` (years), "
               "`description=`.\n"
               "Stored under `disease_` prefix. Consumed by `#sim kind=human`.",
    "disease_gene": "**#disease_gene** — gene perturbation from disease "
                    "(doc/27).\n\n"
                    "Fields: `gene=` (required), "
                    "`type=` (downregulate | upregulate | knockout), "
                    "`activity=` (fraction, default 0.0).\n"
                    "Repeatable — accumulates into `disease_genes` list.",
    "disease_metabolite": "**#disease_metabolite** — metabolite perturbation "
                          "from disease (doc/27).\n\n"
                          "Fields: `id=` (required), "
                          "`type=` (accumulate | deplete), "
                          "`concentration=` (mM), `normal=` (mM).\n"
                          "Repeatable — accumulates into `disease_metabolites` list.",
    "drug": "**#drug** — drug molecule specification "
            "(doc/27, doc/28, doc/32).\n\n"
            "Fields: `name=` (required), `smiles=` (SMILES string), "
            "`formula=`, `mw=` (auto-inferred from SMILES), "
             "`drug_type=` (small_molecule | biologic | antibody | peptide), "
            "`target_protein=`, `binding_affinity_kd=` (nM), "
            "`dose=` (mg), `route=` (oral | iv | im | sc), "
            "`interval=` (hours), `duration=` (days).\n"
            "ADME fields (`bioavailability`, `absorption_rate`, `vd`, `cl`, "
            "`half_life`, `hepatic_eh`, `renal_fraction`, `protein_binding`) "
            "are auto-inferred from SMILES when not explicit.\n"
            "CYP/transporter: `cyp_metabolism=`, `transporter_affected=`, "
            "`non_cyp_metabolism=`.\n"
            "Repeatable — accumulates into `drugs` list.",
    "pd_effect": "**#pd_effect** — pharmacodynamic effect of a drug "
                 "(doc/27, doc/32).\n\n"
                 "Fields: `drug=` (required; references `#drug name=`), "
                 "`target=` (default BIOMASSReaction), "
                 "`type=` (inhibition | agonism), "
                 "`ec50=` (µM), `emax=` (0.0–1.0), `hill=` (coefficient).\n"
                 "Repeatable — accumulates into `pd_effects` list.",
    "qsp_binding": "**#qsp_binding** — QSP target-binding model "
                   "(doc/32).\n\n"
                   "Fields: `drug=` (required), `kind=` (required; "
                   "mass_action | tmdd | competitive), "
                   "`kd_nM=`, `kss_nM=`, `emax=`, `kd_agonist=`, `ki=`.\n"
                   "Repeatable — accumulates into `qsp_bindings` list.",
    "endocrine_config": "**#endocrine_config** — endocrine axis config "
                        "(doc/32).\n\n"
                        "Fields: `axis=` (required; diabetes | addison | "
                        "hypothyroid | stress), `severity=` (0.0–1.0), "
                        "`level=` (hormone offset).\n"
                        "Repeatable — accumulates into `endocrine_configs` list.",
    "immune_config": "**#immune_config** — immune system config "
                     "(doc/32).\n\n"
                     "Fields: `infection_severity=` (0.0–1.0), "
                     "`autoimmune_activation=` (0.0–1.0), "
                     "`immunosuppression=` (0.0–1.0).\n"
                     "Repeatable — accumulates into `immune_configs` list.",
    "tumor_biopsy": "**#tumor_biopsy** — tumor molecular profile for "
                    "biomarker-driven cancer therapy (doc/33 §12).\n\n"
                    "Fields: `mutation=` (comma-separated, e.g. "
                    "`EGFR_L858R,TP53_R175H`), `amplification=`, "
                    "`fusion=`, `pd_l1_expression=` (0.0–1.0 TPS), "
                    "`msi_status=` (MSS | MSI-L | MSI-H), "
                    "`tmb_per_mb=`, `hr_status=` (HRC | HRP).\n"
                     "Stores into `sim_extensions[\"tumor_biopsy\"]`.",
    "use": "**#use** — opt into a bundled plugin (doc/41 §7).\n\n"
           "Usage: `#use <plugin> [--flag ...]`.\n"
           "Bundled plugins: `grn`, `fba`, `human`, `apps`, `annotation`, "
           "`gem`, `kinetics`, `omics`, `cardiology`, `ode_model`.\n"
           "Capability flags: `--pure-python`, `--approx-euler`, "
           "`--low-fidelity` (mutually incompatible with `native`).\n"
           "Plugin-registered annotation keywords (e.g. `#cardiac_cycle`, "
           "`#model`, `#ode_species`, `#ode_reaction`) are only active after "
           "the corresponding `#use`.",
    "cardiac_cycle": "**#cardiac_cycle** — cardiac-cycle force/timing params "
                     "(cardiology plugin; needs `#use cardiology`).\n\n"
                     "Fields: `period=` (float, required), "
                     "`conduction=` (string, default `normal`).",
    "model": "**#model** — mechanistic ODE model (ode_model plugin; needs "
             "`#use ode_model`).\n\n"
             "Fields: `name=` (string, required), `k1=` (float, required), "
             "`k2=` (float, required), `t_end=` (float, default 10), "
             "`steps=` (int, default 100).",
    "ode_species": "**#ode_species** — an ODE species (ode_model plugin; "
                   "needs `#use ode_model`).\n\n"
                   "Fields: `name=` (string, required), "
                   "`initial=` (float, required), `units=` (string).",
    "ode_reaction": "**#ode_reaction** — an ODE reaction (ode_model plugin; "
                    "needs `#use ode_model`).\n\n"
                    "Fields: `species=` (string, required), "
                    "`expr=` (string, required).",
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
                "`calibration`, `benchmark`, `gem`, `ecosystem` (default `classic`)."
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
    elif f.key == "channel":
        body += "\n\nOne of `U`, `V`."
    elif f.key == "source":
        body += "\n\n`ecoli-mg1655` | `synth-4300` | a genome file/model path."
    elif f.key == "tf_map":
        body += "\n\nOne of `regulon`, `random`, `regulondb`, `off`."
    elif f.key == "grn_mode":
        body += "\n\nOne of `sparse`, `full`."
    elif f.key == "active_gene_budget":
        body += "\n\nPer-cell per-tick active-gene budget (default 512)."
    elif f.key == "replicon":
        body += "\n\nReplicon name; must match a `#config sim replicons=` entry."
    elif f.key == "replicons":
        body += ("\n\n`name:copy,...` (e.g. `pBR322:20`); the chromosome is "
                 "implicit and fork-driven.")
    elif f.key == "photo":
        body += "\n\n`true | false` — light-gated photoautotrophy."
    elif f.key == "anoxic":
        body += "\n\n`true | false` — no initial oxygen."
    elif f.key == "diet":
        body += "\n\n`prey:<conversion efficiency>` — predation (L6)."
    elif f.key == "attack":
        body += "\n\n`prey:<mass-action rate>` — predation (L6)."
    elif f.key == "secretion":
        body += "\n\n`sub:<rate>` — cross-feeding / syntrophy (L3)."
    elif f.key == "gem_driven":
        body += "\n\n`true | false` — species with `genome=` trigger GEM pipeline runs at runtime."
    elif f.key == "medium":
        body += "\n\nOne of `glucose_minimal`, `lb`, `bg11`, `custom`."
    elif f.key == "organism":
        body += "\n\nOrganism identifier. E.g. `e_coli_k12`, `synechocystis_pcc6803`."
    elif f.key == "duration":
        body += "\n\nSimulation duration in hours."
    elif f.key == "expression":
        body += "\n\n`true | false` — include gene-expression layer in GEM."
    elif f.key == "use_full_model":
        body += "\n\n`true | false` — import full genome-scale model (SBML/Bigg)."
    elif f.key == "km":
        body += "\n\nMichaelis constant (mM) for enzyme uptake kinetics (Monod model)."
    elif f.key == "temperature":
        body += ("\n\nTemperature in °C for the patch environment"
                 " (affects enzyme kcat via Arrhenius).")
    elif f.key == "ph":
        body += ("\n\npH for the patch environment"
                 " (affects enzyme activity via protonation).")
    elif f.key == "medium_override":
        body += ("\n\nComma-separated `met:value` pairs to override"
                 " preset medium. E.g. `fe3_e:0.5,co2_e:500`.")
    elif f.key == "max_growth_rate":
        body += "\n\nFloat: cap maximum growth rate (overrides organism default from registry)."
    elif f.key == "expression_level":
        body += "\n\nFloat: per-gene expression level override (enzyme concentration calibration)."
    elif f.key == "id":
        body += "\n\nReaction identifier (required). E.g. `PGI`, `CS`."
    elif f.key == "substrate":
        body += "\n\nSubstrate metabolite id."
    elif f.key == "product":
        body += "\n\nProduct metabolite id."
    elif f.key == "substrate_coeff":
        body += "\n\nStoichiometric coefficient for substrate (default −1)."
    elif f.key == "product_coeff":
        body += "\n\nStoichiometric coefficient for product (default 1)."
    elif f.key == "lower_bound":
        body += "\n\nFlux lower bound (default 0)."
    elif f.key == "upper_bound":
        body += "\n\nFlux upper bound (default 1000)."
    elif f.key == "subsystem":
        body += "\n\nMetabolic subsystem (default `other`)."
    elif f.key == "reversible":
        body += "\n\n`true | false` — shorthand for setting lower_bound = −upper_bound."
    elif f.key == "age":
        body += "\n\nPatient age in years (float, default 30)."
    elif f.key == "sex":
        body += "\n\nOne of `male`, `female`."
    elif f.key == "weight":
        body += "\n\nBody weight in kg (float, default 70)."
    elif f.key == "height":
        body += "\n\nHeight in cm (float, default 170)."
    elif f.key == "ethnicity":
        body += "\n\nEthnicity (default `european`)."
    elif f.key == "smoking":
        body += "\n\nOne of `never`, `former`, `current`."
    elif f.key == "pack_years":
        body += "\n\nSmoking pack-years (float)."
    elif f.key == "alcohol":
        body += "\n\nAlcohol drinks per week (float)."
    elif f.key == "exercise":
        body += "\n\nOne of `sedentary`, `light`, `moderate`, `vigorous`."
    elif f.key == "pregnant":
        body += "\n\n`true | false` — pregnant status."
    elif f.key == "category":
        body += "\n\nDisease category (e.g. `metabolic_overload`)."
    elif f.key == "severity":
        body += "\n\nSeverity 0.0–1.0."
    elif f.key == "onset_age":
        body += "\n\nAge of disease onset (years)."
    elif f.key == "description":
        body += "\n\nFree-text disease description."
    elif f.key == "activity":
        body += "\n\nActivity fraction 0.0–1.0."
    elif f.key == "normal":
        body += "\n\nNormal concentration (mM)."
    elif f.key == "smiles":
        body += "\n\nSMILES string for the drug molecule."
    elif f.key == "formula":
        body += "\n\nMolecular formula (e.g. `C4H11N5`)."
    elif f.key == "mw":
        body += "\n\nMolecular weight (g/mol; auto-inferred from SMILES)."
    elif f.key == "drug_type":
        body += "\n\nOne of `small_molecule`, `antibody`, `peptide`."
    elif f.key == "target_protein":
        body += "\n\nProtein target of the drug."
    elif f.key == "binding_affinity_kd":
        body += "\n\nBinding affinity Kd (nM)."
    elif f.key == "dose":
        body += "\n\nDose in mg."
    elif f.key == "route":
        body += "\n\nOne of `oral`, `iv`, `im`, `sc`."
    elif f.key == "interval":
        body += "\n\nDosing interval in hours (default 24)."
    elif f.key == "bioavailability":
        body += "\n\nBioavailability fraction (auto-inferred from SMILES)."
    elif f.key == "absorption_rate":
        body += "\n\nAbsorption rate constant (auto-inferred)."
    elif f.key == "vd":
        body += "\n\nVolume of distribution in L (auto-inferred)."
    elif f.key == "cl":
        body += "\n\nClearance in mL/min (auto-inferred)."
    elif f.key == "half_life":
        body += "\n\nHalf-life in hours (auto-inferred)."
    elif f.key == "hepatic_eh":
        body += "\n\nHepatic extraction ratio (auto-inferred)."
    elif f.key == "renal_fraction":
        body += "\n\nRenal elimination fraction (auto-inferred)."
    elif f.key == "protein_binding":
        body += "\n\nProtein binding fraction (auto-inferred)."
    elif f.key == "cyp_metabolism":
        body += "\n\nCYP enzyme metabolism (e.g. `CYP3A4:0.5,CYP2D6:0.3`)."
    elif f.key == "transporter_affected":
        body += "\n\nTransporter effects (e.g. `SLCO1B1:0.6`)."
    elif f.key == "non_cyp_metabolism":
        body += "\n\nNon-CYP metabolism (e.g. `UGT1A1:0.7`)."
    elif f.key == "ec50":
        body += "\n\nEC50 for PD effect (µM)."
    elif f.key == "emax":
        body += "\n\nMaximum effect fraction 0.0–1.0."
    elif f.key == "hill":
        body += "\n\nHill coefficient for dose-response."
    elif f.key == "kd_nM":
        body += "\n\nDissociation constant for QSP binding (nM)."
    elif f.key == "kss_nM":
        body += "\n\nSteady-state Kss for QSP binding (nM)."
    elif f.key == "kd_agonist":
        body += "\n\nKd for agonist binding (nM)."
    elif f.key == "ki":
        body += "\n\nInhibition constant Ki (nM)."
    elif f.key == "axis":
        body += "\n\nOne of `diabetes`, `addison`, `hypothyroid`, `stress`."
    elif f.key == "level":
        body += "\n\nHormone level offset."
    elif f.key == "infection_severity":
        body += "\n\nInfection severity 0.0–1.0."
    elif f.key == "autoimmune_activation":
        body += "\n\nAutoimmune activation level 0.0–1.0."
    elif f.key == "immunosuppression":
        body += "\n\nImmunosuppression level 0.0–1.0."
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
