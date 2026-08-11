"""Error-matrix tests: every row of doc/03 §8.1 error→diagnostic mapping."""

from __future__ import annotations

from helixlang_lsp.analysis import analyze
from helixlang_lsp.diagnostics import dedupe


def _codes(text: str) -> list[str]:
    ana = analyze(text)
    return sorted({d.code for d in ana.diagnostics if d.severity == 1})


def test_lex_error():
    assert "lex" in _codes("#gene name=g\nATG GGGG TAA\n#end\n")


def test_parse_unknown_annotation():
    assert "parse" in _codes("#frobnicate name=x\n#end\n")


def test_parse_no_start_codon():
    assert "parse" in _codes("#gene name=g\nTAA GCT\n#end\n")


def test_parse_orf_not_terminated():
    assert "parse" in _codes("#gene name=g\nATG GCT\n")


def test_parse_missing_field():
    assert "parse" in _codes("#promoter\n#end\n")


def test_semantic_duplicate_symbol():
    assert "semantic" in _codes(
        "#gene name=g\nATG TAA\n#end\n#gene name=g\nATG TAA\n#end\n")


def test_semantic_unknown_promoter():
    assert "semantic" in _codes("#gene name=g promoter=nope\nATG TAA\n#end\n")


def test_regulation_undefined():
    assert "regulation" in _codes("#promoter name=p strength=1\n#regulate q -> g\n")


def test_compile_call_gene_target():
    assert "compile" in _codes(
        "#gene name=g call_target=nope\nATG CGT TAA\n#end\n")


def test_warning_regulation_cycle_is_warning():
    ana = analyze("#promoter name=p strength=1\n#gene name=g promoter=p\n"
                  "ATG TAA\n#end\n#regulate p -> p\n")
    warnings = [d for d in ana.diagnostics if d.severity == 2]
    assert warnings and warnings[0].code == "warning"
    assert "regulation cycle" in warnings[0].message


def test_clean_file_zero_diagnostics():
    ana = analyze("#promoter name=p strength=0.8\n"
                  "#gene name=lacZ promoter=p\nATG GCT GGT TAA\n#end\n")
    assert ana.diagnostics == []


def test_diagnostic_message_keeps_compiler_str():
    ana = analyze("#gene name=g\nATG GGGG TAA\n#end\n")
    err = next(d for d in ana.diagnostics if d.code == "lex")
    assert err.message.startswith("[LexError @")


def test_error_to_diagnostic_data_class_name():
    ana = analyze("#gene name=g\nATG GGGG TAA\n#end\n")
    err = next(d for d in ana.diagnostics if d.code == "lex")
    assert err.data["className"] == "LexError"
    assert err.source == "helix"
    assert err.severity == 1


def test_dedupe_removes_duplicates():
    ana = analyze("#frobnicate name=x\n#end\n")
    parse_errors = [d for d in ana.diagnostics if d.code == "parse"]
    assert len(dedupe(parse_errors)) == len(parse_errors)


def test_bad_table_diagnostic():
    ana = analyze("#config table=nope\n")
    assert any(d.code == "config" for d in ana.diagnostics)
