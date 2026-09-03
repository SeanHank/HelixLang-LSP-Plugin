"""Targeted tests that drive the last uncovered branches in the server.

These cover defensive/edge branches (bounds, unknown-table, program=None,
missing docs) that normal lexer/compiler flows cannot reach, by feeding
hand-built structures directly (no coverage exclusions).
"""

from __future__ import annotations

from unittest import mock

from helixlang_lsp import positions as pos
from helixlang_lsp.analysis import (
    Analysis,
    AnnotationInfo,
    CodonInfo,
    DnaBlock,
    ScanResult,
    analyze,
)
from helixlang_lsp.features import (
    code_actions as ca,
)
from helixlang_lsp.features import (
    definitions as defs,
)
from helixlang_lsp.features import (
    document_symbols as ds,
)
from helixlang_lsp.features import (
    folding as folding,
)
from helixlang_lsp.features import (
    formatting as fmt,
)
from helixlang_lsp.features import (
    hover as hover,
)
from helixlang_lsp.features import (
    inlay_hints as ih,
)
from helixlang_lsp.features import (
    references as refs,
)
from helixlang_lsp.protocol import Position


def _analysis_with(structure: ScanResult,
                   program: object = None) -> Analysis:
    return Analysis(
        uri="file:///f.helix", text="", table_name="standard",
        tokens=None, program=program, chunk=None, diagnostics=[],
        structure=structure,
    )


# --------------------------------------------------------------------------
# positions.py
# --------------------------------------------------------------------------

def test_position_to_linecol_beyond_lines() -> None:
    assert pos.position_to_linecol("hi", Position(line=5, character=0)) == (6, 1)


def test_whole_line_range_beyond_lines() -> None:
    r = pos.whole_line_range("hi", 9)
    assert r.start.line == 9 and r.end.line == 9
    assert r.end.character == 0


# --------------------------------------------------------------------------
# formatting.py – _end_position defensive base cases
# --------------------------------------------------------------------------

def test_formatting_end_position_empty_lines() -> None:
    fake = mock.Mock()
    fake.split.return_value = []
    assert fmt._end_position(fake) == Position(line=0, character=0)


def test_formatting_end_position_no_trailing_newline() -> None:
    assert fmt._end_position("a") == Position(line=0, character=1)


# --------------------------------------------------------------------------
# folding.py – multi-line DNA block (lexer never emits line>1 for codons)
# --------------------------------------------------------------------------

def test_folding_multiline_dna_block() -> None:
    blk = DnaBlock(start_line0=0, end_line0=2)
    structure = ScanResult(dna_blocks=[blk])
    analysis = _analysis_with(structure)
    out = folding.folding_ranges("x\n\n\n", analysis, {})
    assert any(r["kind"] == "region" and r["startLine"] == 0
               and r["endLine"] == 2 for r in out)


# --------------------------------------------------------------------------
# inlay_hints.py – body codon unknown to the table
# --------------------------------------------------------------------------

def test_inlay_hints_unknown_body_codon_skipped() -> None:
    ann = AnnotationInfo(kind="gene", line0=1, col0=0)
    ann.body_codons.append(CodonInfo(seq="XXX", line0=1, col0=1))
    structure = ScanResult(annotations=[ann])
    analysis = _analysis_with(structure)
    assert ih.inlay_hints("", analysis, {}) == []


# --------------------------------------------------------------------------
# hover.py – unknown codon, undocumented annotation, program=None
# --------------------------------------------------------------------------

def test_hover_unknown_codon() -> None:
    class FakeCodon:
        seq = "XXX"
        line0 = 0
        col0 = 0
    analysis = _analysis_with(ScanResult())
    out = hover._hover_codon(FakeCodon(), analysis)
    assert "unknown codon" in out["contents"]["value"]


def test_hover_undocumented_annotation() -> None:
    analysis = _analysis_with(ScanResult())
    out = hover._hover_annotation(AnnotationInfo(kind="zzz", line0=0, col0=0),
                                  analysis)
    assert "**#zzz**" in out["contents"]["value"]


def test_regulation_edges_program_none() -> None:
    analysis = _analysis_with(ScanResult(), program=None)
    assert hover._regulation_edges(analysis, "geneA") == []


# --------------------------------------------------------------------------
# jsonrpc.py – header-line UTF-8 decode fallback
# --------------------------------------------------------------------------

def test_jsonrpc_header_decode_fallback() -> None:
    from helixlang_lsp.jsonrpc import read_message_binary

    CONTENT = b"Content-Length: 16:"
    BODY = b'{"jsonrpc":"2.0"}'

    class WeirdLine(bytes):
        def decode(self, *args, **kwargs):
            if "utf-8" in kwargs.values() or "utf-8" in args:
                raise RuntimeError("boom")
            return "Content-Length: 16"

    class FakeStream:
        def __init__(self) -> None:
            self._n = 0

        def readline(self) -> bytes:
            self._n += 1
            if self._n == 1:
                return WeirdLine(CONTENT)
            return b"\r\n"

        def read(self, n: int) -> bytes:
            return BODY

    ret = read_message_binary(FakeStream())
    assert ret["jsonrpc"] == "2.0"


# --------------------------------------------------------------------------
# definitions.py / references.py – negative-line guard + symbol resolution
# --------------------------------------------------------------------------

def test_definitions_negative_line_returns_none() -> None:
    with mock.patch("helixlang_lsp.positions.position_at",
                    return_value=(0, 0)):
        assert defs.definitions("x", _analysis_with(ScanResult()),
                                {"position": {"line": 99, "character": 0}}) is None


def test_definitions_resolves_symbol() -> None:
    text = "#gene name=g1 promoter=p_lac\n#promoter name=p_lac strength=1.0\n"
    ana = analyze(text)
    out = defs.definitions(text, ana,
                           {"position": {"line": 0, "character": 11}})
    assert out is not None and out[0]["range"]["start"]["line"] == 0


def test_references_negative_line_returns_empty() -> None:
    with mock.patch("helixlang_lsp.positions.position_at",
                    return_value=(0, 0)):
        assert refs.references("x", _analysis_with(ScanResult()),
                               {"position": {"line": 99, "character": 0}}) == []


def test_references_with_declaration() -> None:
    text = ("#gene name=g1 promoter=p_lac\n"
            "#promoter name=p_lac strength=1.0\n"
            "#regulate p_lac ->\n")
    ana = analyze(text)
    out = refs.references(text, ana, {"position": {"line": 2, "character": 14},
                                      "context": {"includeDeclaration": True}})
    assert out, "expected at least one reference"


# --------------------------------------------------------------------------
# hover.py – negative-line guard (position_at clamps, so mock it)
# --------------------------------------------------------------------------

def test_hover_negative_line_returns_none() -> None:
    with mock.patch("helixlang_lsp.positions.position_at",
                    return_value=(0, 0)):
        assert hover.hover("x", _analysis_with(ScanResult()),
                           {"position": {"line": 99, "character": 0}}) is None


# --------------------------------------------------------------------------
# code_actions.py – only filter + _action_length no-codon-group return
# --------------------------------------------------------------------------

def test_code_actions_only_non_quickfix() -> None:
    ana = analyze("#gene name=g1\n")
    out = ca.code_actions("#gene name=g1\n", ana,
                          {"context": {"only": ["refactor.v1"],
                                       "diagnostics": [
                                           {"code": "parse",
                                            "message": "ORF not terminated",
                                            "range": {
                                                "start": {"line": 0,
                                                          "character": 0},
                                                "end": {"line": 0,
                                                        "character": 1}}}]}})
    assert out == []


def test_action_length_no_codon_groups() -> None:
    from helixlang_lsp.protocol import Range
    ana = analyze("#gene name=g1\n")
    rng = Range(start=Position(line=0, character=0),
                end=Position(line=0, character=1))
    assert ca._action_length("this line has no DNA triplets", rng,
                             ana.uri) is None


# --------------------------------------------------------------------------
# document_symbols.py – DNA block symbols + _symbol_name fallback
# --------------------------------------------------------------------------

def test_document_symbols_dna_block() -> None:
    blk = DnaBlock(start_line0=0, end_line0=1)
    struct = ScanResult(dna_blocks=[blk])
    ana = _analysis_with(struct)
    out = ds.document_symbols("GGG\nTTT\n", ana, {})
    assert any(s["name"] == "DNA" for s in out)


def test_symbol_name_fallback_capitalize() -> None:
    ann = AnnotationInfo(kind="gene", line0=0, col0=0)
    assert ds._symbol_name(ann) == "Gene"
