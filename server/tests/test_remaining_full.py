"""Tests for the final uncovered lines in diagnostics, completion, definitions.

Covers branch returns that require specific cursor positions or mock-free
error construction. No coverage exclusions.
"""

from __future__ import annotations

from unittest import mock

import helixlang_lsp._helix_contract as helix
from helixlang_lsp import diagnostics as diag
from helixlang_lsp.analysis import analyze
from helixlang_lsp.features import (
    completion as comp,
)
from helixlang_lsp.features import (
    definitions as defs,
)

# --------------------------------------------------------------------------
# diagnostics.py
# --------------------------------------------------------------------------

def _lex_error() -> helix.LexError:
    try:
        list(helix.Lexer("#gene name=g\nATG GGGG TAA\n").tokens())
    except helix.LexError as exc:
        return exc
    raise AssertionError("expected LexError")


def test_errors_to_diagnostics_singular() -> None:
    exc = _lex_error()
    out = diag.errors_to_diagnostics(exc, "x", None)
    assert len(out) == 1
    assert out[0].code in ("lex", "error")


def test_errors_to_diagnostics_list() -> None:
    exc = _lex_error()
    out = diag.errors_to_diagnostics([exc, exc], "x", None)
    assert len(out) == 2


def test_dedupe_skips_duplicate() -> None:
    d = diag.diagnostic_at_line("aa\n", 0, "dup")
    out = diag.dedupe([d, d])
    assert len(out) == 1


def test_resolve_range_codon_from_msg() -> None:
    tokens = list(helix.Lexer("ATG GCT\n").tokens())
    rng = diag._resolve_range("ATG GCT\n", tokens, line=0, col=0,
                              codon_index=-1, msg="error near ATG",
                              orf_span=False)
    assert rng.start.line == 0 and rng.end.character >= 3


def test_line_length_out_of_range() -> None:
    assert diag._line_length("hello", 99) == 0


def test_related_for_compile_no_call_gene() -> None:
    tokens = list(helix.Lexer("#gene name=g\nATG TAA\n#end\n").tokens())
    exc = helix.ParseError("some unrelated parse problem")
    assert diag._related_for_compile(exc, "x\n", tokens) is None


def test_related_for_compile_compile_error_no_match() -> None:
    tokens = list(helix.Lexer("#gene name=g\nATG TAA\n#end\n").tokens())
    exc = helix.CompileError("compile failed for another reason")
    assert diag._related_for_compile(exc, "x\n", tokens) is None


def test_codon_range_for_msg_matches_token() -> None:
    tokens = list(helix.Lexer("ATG GCT\n").tokens())
    rng = diag._codon_range_for_msg(tokens, "ATG GCT\n", "near ATG")
    assert rng is not None and rng.start.line == 0


# --------------------------------------------------------------------------
# completion.py – context-kind branches + item providers
# --------------------------------------------------------------------------

PATCH = [mock.patch("helixlang_lsp.features.completion._field_being_edited",
                    return_value=(None, "")),
         mock.patch("helixlang_lsp.features.completion._field_region",
                    return_value=False)]


def test_completion_context_partial_annotation() -> None:
    text = "#med"
    ana = analyze(text)
    ctx = comp._context(text, ana, 0, 3, "#med")
    assert ctx["kind"] == "annotation" and ctx["prefix"] == "med"


def test_completion_context_regulate_source() -> None:
    text = "#regulate p_lac \n"
    ana = analyze(text)
    ctx = comp._context(text, ana, 0, 14, "#regulate p_lac ")
    assert ctx["kind"] == "symbol" and ctx["role"] == "source"


def test_completion_context_bio_target() -> None:
    text = "#crispr name=c1\n#end\n"
    ana = analyze(text)
    with mock.patch("helixlang_lsp.features.completion._field_being_edited",
                    return_value=(None, "")), \
            mock.patch("helixlang_lsp.features.completion._field_region",
                       return_value=False):
        ctx = comp._context(text, ana, 0, 15, "#crispr name=c1")
    assert ctx["kind"] == "symbol" and ctx["role"] == "target"


def test_completion_context_gene_promoter() -> None:
    text = "#type name=t\n#end\n#gene name=g1\n#end\n"
    ana = analyze(text)
    with mock.patch("helixlang_lsp.features.completion._field_being_edited",
                    return_value=(None, "")), \
            mock.patch("helixlang_lsp.features.completion._field_region",
                       return_value=False):
        ctx = comp._context(text, ana, 2, 10, "#gene name=g1")
    assert ctx["kind"] == "symbol" and ctx["role"] == "promoter"


def test_completion_context_type() -> None:
    text = "#type name=t\n#end\n"
    ana = analyze(text)
    with mock.patch("helixlang_lsp.features.completion._field_being_edited",
                    return_value=(None, "")), \
            mock.patch("helixlang_lsp.features.completion._field_region",
                       return_value=False):
        ctx = comp._context(text, ana, 0, 11, "#type name=t")
    assert ctx["kind"] == "type"


def test_completion_context_fallback_annotation() -> None:
    text = "#config table=standard\n\n"
    ana = analyze(text)
    ctx = comp._context(text, ana, 1, 0, "")
    assert ctx["kind"] == "annotation" and ctx["prefix"] == ""


def test_items_for_context_type() -> None:
    ana = analyze("#type\n")
    items = comp._items_for_context({"kind": "type"}, ana)
    assert items and items[0].label == "Protein"


def test_items_for_context_unknown_kind() -> None:
    ana = analyze("#type\n")
    assert comp._items_for_context({"kind": "nope"}, ana) == []


def test_line_out_of_range() -> None:
    assert comp._line("x", 5) == ""


def test_in_body_annotation_header_above() -> None:
    assert comp._in_body("#config table=standard\nline\n", 1) is False


def test_in_body_loop_exhausted() -> None:
    assert comp._in_body("plain text only\n", 0) is False


def test_in_body_matches_codon_line() -> None:
    assert comp._in_body("ATG GCT\n", 0) is True


# --------------------------------------------------------------------------
# definitions.py – symbol-not-found guard
# --------------------------------------------------------------------------

def test_definitions_symbol_not_found_returns_none() -> None:
    text = "#gene name=g1 promoter=p_lac\n#promoter name=p_lac strength=1.0\n"
    ana = analyze(text)
    # position on the #promoter header line, at the '#' itself (not a symbol)
    assert defs.definitions(text, ana,
                            {"position": {"line": 1, "character": 0}}) is None
