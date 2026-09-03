"""Coverage-focused tests for semantic-token encoding edge cases, codon/analysis
decoding, structure scanning, and workspace index error paths."""

from __future__ import annotations

from unittest import mock

import pytest
from helixlang_lsp import _helix_contract as helix
from helixlang_lsp.analysis import (
    Analysis,
    AnnotationInfo,
    ScanResult,
    Workspace,
    _build_symbols,
    _structural_check,
    analyze,
    scan_structure,
)
from helixlang_lsp.codons import codons_for_opcode, decode_codon, opcode_family
from helixlang_lsp.features.semantic_tokens import (
    _build_codon_positions,
    _looks_numeric,
    _looks_smiles,
    semantic_tokens,
)


def _analysis(tokens: list[helix.Token], text: str,
              table_name: str = "standard") -> Analysis:
    return Analysis(
        uri="", text=text, table_name=table_name, tokens=tokens,
        program=None, chunk=None, diagnostics=[],
        structure=scan_structure(tokens, text, table_name),
    )


# --------------------------------------------------------------------------
# semantic_tokens — uncovered token-kind, field, and codon branches
# --------------------------------------------------------------------------

def test_semantic_tokens_extra_codons_fallback_line():
    full = "#gene name=g\nATG GGT TAA\n#end\n"
    ana = analyze(full, uri="file:///t.helix")
    truncated = "#gene name=g\nATG\n#end\n"
    data = semantic_tokens(truncated, ana, {})["data"]
    assert data


def test_semantic_tokens_gene_id_string_comment_kinds():
    toks = [
        helix.Token(kind="GENE_ID", value="lacZ", line=1, col=1),
        helix.Token(kind="STRING", value="hello", line=1, col=6),
        helix.Token(kind="COMMENT", value="#hi", line=1, col=13),
        helix.Token(kind="NEWLINE", value="", line=1, col=17),
        helix.Token(kind="EOF", value="", line=2, col=1),
    ]
    data = semantic_tokens("", _analysis(toks, ""), {})["data"]
    assert len(data) % 5 == 0
    # GENE_ID -> type index 1 with declaration modifier
    assert data[3] == 1
    assert data[4] == 0


def test_semantic_tokens_field_smiles():
    text = "#drug smiles=CC(=O)Oc1ccccc1C(=O)O\n"
    toks = [
        helix.Token(kind="ANNOT_START", value="drug", line=1, col=1),
        helix.Token(kind="FIELD", value="smiles=CC(=O)Oc1ccccc1C(=O)O", line=1, col=8),
        helix.Token(kind="EOF", value="", line=2, col=1),
    ]
    data = semantic_tokens(text, _analysis(toks, text), {})["data"]
    types = [data[i + 3] for i in range(0, len(data), 5)]
    assert 19 in types  # smiles


def test_semantic_tokens_field_quoted_value_is_string():
    text = '#trait description="hello world"\n'
    toks = [
        helix.Token(kind="ANNOT_START", value="trait", line=1, col=1),
        helix.Token(kind="FIELD", value='description="hello world"', line=1, col=7),
        helix.Token(kind="EOF", value="", line=2, col=1),
    ]
    data = semantic_tokens(text, _analysis(toks, text), {})["data"]
    types = [data[i + 3] for i in range(0, len(data), 5)]
    assert 5 in types  # string


def test_semantic_tokens_codon_not_in_table_is_string():
    toks = [
        helix.Token(kind="ANNOT_START", value="gene", line=1, col=1),
        helix.Token(kind="FIELD", value="name=g", line=1, col=7),
        helix.Token(kind="CODON", value="XYZ", line=2, col=1),
    ]
    text = "#gene name=g\nXYZ\n"
    data = semantic_tokens(text, _analysis(toks, text), {})["data"]
    types = [data[i + 3] for i in range(0, len(data), 5)]
    assert 5 in types  # string


def test_build_codon_positions_skips_comments():
    text = "#gene name=g\n# DNA MOTIF\nATG GGT TAA\n#end\n"
    pos = _build_codon_positions(text)
    assert pos == [(2, 0), (2, 4), (2, 8)]


def test_looks_smiles_branches():
    assert _looks_smiles("CC") is False
    assert _looks_smiles("cnXX") is False
    assert _looks_smiles("cnosXX") is True


def test_looks_numeric_branches():
    assert _looks_numeric("") is False
    assert _looks_numeric("3.14") is True
    assert _looks_numeric("abc") is False


def test_semantic_tokens_opcode_families_and_stop():
    text = "#gene name=hello\nATA AGA AGG TGA\n#end\n"
    standard = analyze(text)
    mito = analyze(text, table_hint="mito_vertebrate")
    std = semantic_tokens(text, standard, {})["data"]
    mit = semantic_tokens(text, mito, {})["data"]
    assert 16 in {std[i + 3] for i in range(0, len(std), 5)}  # opcodeCall
    assert 9 in {mit[i + 3] for i in range(0, len(mit), 5)}  # opcodeStart


# --------------------------------------------------------------------------
# codons — reverse-opcode and unknown-table handling
# --------------------------------------------------------------------------

def test_codons_for_opcode_unknown_returns_empty():
    assert codons_for_opcode(helix.Op.OP_RETURN) == []
    assert codons_for_opcode(helix.Op.OP_START) == ["ATG"]


def test_opcode_family_compiler_only_returns_none():
    assert opcode_family(helix.Op.OP_RETURN) is None
    assert opcode_family(helix.Op.OP_NOP) is None


def test_decode_codon_unknown_returns_none():
    assert decode_codon("XYZ") is None
    assert decode_codon("ATG") == (helix.Op.OP_START, 2)


def test_decode_codon_unknown_table_raises():
    with pytest.raises(helix.HelixError):
        decode_codon("ATG", "bogus_table")


# --------------------------------------------------------------------------
# analysis — structure scan + decode edge cases
# --------------------------------------------------------------------------

def test_scan_structure_unknown_codon_opcode_is_none():
    toks = [
        helix.Token(kind="ANNOT_START", value="gene", line=1, col=1),
        helix.Token(kind="FIELD", value="name=testgene", line=1, col=7),
        helix.Token(kind="CODON", value="ZZZ", line=2, col=1),
        helix.Token(kind="ANNOT_END", value="#end", line=3, col=1),
    ]
    text = "#gene name=testgene\nZZZ\n#end\n"
    result = scan_structure(toks, text, "standard")
    ci = result.codon_tokens[0]
    assert ci.opcode is None
    assert ci.operand is None
    assert ci.operand_display is None


def test_scan_structure_codon_col_out_of_bounds():
    toks = [helix.Token(kind="CODON", value="ATG", line=99, col=1)]
    result = scan_structure(toks, "", "standard")
    assert result.codon_tokens[0].col0 == 0


def test_scan_structure_unknown_table_falls_back():
    toks = [helix.Token(kind="CODON", value="ATG", line=1, col=1)]
    result = scan_structure(toks, "ATG", "bogus_table")
    assert result.codon_tokens[0].opcode == "OP_START"


def test_structural_check_unknown_annotation_kind():
    toks = [
        helix.Token(kind="ANNOT_START", value="quant", line=1, col=1),
        helix.Token(kind="NEWLINE", value="", line=1, col=7),
    ]
    diags = _structural_check(toks, "#quant\n", "standard")
    assert any("unknown annotation #quant" in d.message for d in diags)


def test_build_symbols_field_missing_after_name_lookup():
    ann = AnnotationInfo(kind="gene", line0=0, col0=0)
    res = ScanResult(annotations=[ann])
    with mock.patch("helixlang_lsp.analysis._field",
                    side_effect=lambda _a, k: "marker_name" if k == "name" else None):
        _build_symbols(res, "#gene\n")
    assert res.symbols == {}


def test_reference_at_hit_and_miss():
    text = "#promoter name=p_lac strength=0.8\n#gene name=g promoter=p_lac\n"
    ana = analyze(text)
    assert ana.reference_at(0, 17) is not None
    assert ana.reference_at(99, 0) is None


def test_analysis_symbol_at_and_reference_at_empty():
    ana = analyze("#config table=standard\n")
    assert ana.symbol_at(0, 0) is None
    assert ana.reference_at(0, 0) is None


# --------------------------------------------------------------------------
# Workspace — scan without root + unreadable file
# --------------------------------------------------------------------------

def test_workspace_scan_without_root_returns():
    ws = Workspace()
    ws.scan()
    assert ws._index == {}


def test_workspace_index_file_unreadable():
    ws = Workspace(root="/nonexistent_root")
    ws.scan("/nonexistent_root")
    ws.index_file("/nonexistent/file.helix")
    assert ws._index == {}
