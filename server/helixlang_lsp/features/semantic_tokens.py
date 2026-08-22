"""``textDocument/semanticTokens/full`` — token classification.

Legend (doc/03 §9 + doc/08 §3.2): keyword, type, function, variable, number,
string, comment, operator, arrow, and the nine ``opcode*`` codon families;
modifiers: declaration, defaultLibrary. Codons are classified by the family of
their decoded opcode (doc/08 §3.1). Output uses LSP relative delta encoding.
"""

from __future__ import annotations

from typing import Any

from helixlang_lsp import _helix_contract as helix
from helixlang_lsp.analysis import Analysis
from helixlang_lsp.codons import decode_codon, opcode_family
from helixlang_lsp.protocol import TOKEN_MODIFIER_INDEX, TOKEN_TYPE_INDEX, SemanticTokens

_NUM_FIELDS = {
    "strength", "size", "ticks", "ops_per_tick", "react_steps",
    "init", "value", "strength0", "threshold",
    "concentration", "diffusion_um2_s", "kcat",
    "division_energy", "adder_volume_um3", "adder_noise_std", "volume_init_um3",
    "biomass_to_volume_pg_per_min", "cell_density_dry_pg_um3",
    "surface_exponent", "c_period_min", "d_period_min", "doubling_time_min",
    "energy_init", "maintenance_atp_per_min", "biomass_to_atp",
    "transcription_atp_per_nt", "translation_atp_per_aa", "protein_yield_per_mrna",
    "minutes_per_step", "enzyme_scale", "protein_mass_fraction",
    "frac_cotranslational_fold", "folding_atp_per_protein", "k_fold",
    "misfold_rate_per_min", "aggregation_rate_per_min", "degraded_rate_per_min",
    "protein_half_life_min", "population_size", "grid_width", "grid_height",
    "grid_depth", "division_threshold", "death_threshold", "signal_diffusion",
    "signal_threshold", "noise_seed", "dfba_dt_h", "dfba_energy_scale",
    "dfba_initial_biomass_gdw", "dfba_glucose_half_saturation_mm",
    "dfba_oxygen_max_uptake", "dfba_oxygen_half_saturation_mm",
    "fba_dt_h", "fba_glucose_mm", "fba_oxygen_max", "fba_steps",
}


def semantic_tokens(text: str, analysis: Analysis,
                    _params: dict[str, Any]) -> dict[str, Any]:
    """Handle ``textDocument/semanticTokens/full``."""
    tokens = analysis.tokens
    if not tokens:
        return SemanticTokens(data=[]).to_dict()

    abs_tokens: list[tuple[int, int, int, int, int]] = []
    for tok in tokens:
        kind = tok.kind
        if kind in ("NEWLINE", "EOF"):
            continue
        line = tok.line - 1
        col = tok.col - 1
        value = tok.value
        if kind == "ANNOT_START":
            _add(abs_tokens, line, col, len(value) + 1, "keyword", 0)
        elif kind == "ANNOT_END":
            _add(abs_tokens, line, col, len(value), "keyword", 0)
        elif kind == "ARROW":
            _add(abs_tokens, line, col, len(value), "arrow", 0)
        elif kind == "FIELD":
            _classify_field(abs_tokens, line, col, value, analysis)
        elif kind == "CODON":
            _classify_codon(abs_tokens, line, col, value, analysis.table_name)
        elif kind == "GENE_ID":
            _add(abs_tokens, line, col, len(value), "type",
                 TOKEN_MODIFIER_INDEX["declaration"])
        elif kind == "STRING":
            _add(abs_tokens, line, col, len(value), "string", 0)
        elif kind == "COMMENT":
            _add(abs_tokens, line, col, len(value), "comment", 0)

    encoded = _encode(abs_tokens)
    return SemanticTokens(data=encoded).to_dict()


def _classify_field(abs_tokens: list[tuple[int, int, int, int, int]],
                    line: int, col: int, value: str, analysis: Analysis) -> None:
    key, _, val = value.partition("=")
    if key == "name":
        # declaration modifier on the symbol name value
        sym = analysis.structure.symbols.get(val)
        t = "function" if sym and sym.kind == "gene" else "variable"
        _add(abs_tokens, line, col + len(key) + 1, len(val), t,
             TOKEN_MODIFIER_INDEX["declaration"])
        return
    if key in ("promoter", "call_target", "target", "source", "gene", "reaction"):
        _add(abs_tokens, line, col + len(key) + 1, len(val), "variable", 0)
        return
    if key in _NUM_FIELDS and _looks_numeric(val):
        _add(abs_tokens, line, col + len(key) + 1, len(val), "number", 0)
        return
    if val.startswith('"') or val.startswith("'"):
        _add(abs_tokens, line, col + len(key) + 1, len(val), "string", 0)
        return
    _add(abs_tokens, line, col, len(key), "keyword", 0)
    _add(abs_tokens, line, col + len(key) + 1, len(val), "string", 0)


def _classify_codon(abs_tokens: list[tuple[int, int, int, int, int]],
                    line: int, col: int, value: str, table_name: str) -> None:
    decoded = decode_codon(value, table_name)
    if decoded is None:
        _add(abs_tokens, line, col, 3, "string", 0)
        return
    op, _w = decoded
    if op is helix.Op.OP_START:
        _add(abs_tokens, line, col, 3, "opcodeStart",
             TOKEN_MODIFIER_INDEX["defaultLibrary"])
    elif op is helix.Op.OP_HALT:
        _add(abs_tokens, line, col, 3, "opcodeHalt", 0)
    else:
        _add(abs_tokens, line, col, 3,
             opcode_family(op) or "opcodeArithmetic", 0)


def _add(abs_tokens: list[tuple[int, int, int, int, int]], line: int, col: int,
         length: int, type_name: str, mods: int) -> None:
    abs_tokens.append((line, col, max(length, 1), TOKEN_TYPE_INDEX[type_name], mods))


def _looks_numeric(val: str) -> bool:
    if not val:
        return False
    try:
        float(val)
        return True
    except ValueError:
        return False


def _encode(abs_tokens: list[tuple[int, int, int, int, int]]) -> list[int]:
    """Relative delta encoding per LSP."""
    result: list[int] = []
    prev_line = 0
    prev_start = 0
    for line, start, length, type_idx, mods in abs_tokens:
        if line == prev_line:
            delta_line = 0
            delta_start = start - prev_start
        else:
            delta_line = line - prev_line
            delta_start = start
        result.extend([delta_line, delta_start, length, type_idx, mods])
        prev_line = line
        prev_start = start
    return result
