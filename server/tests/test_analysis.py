"""Unit tests for the analysis pipeline, structure scan, and workspace index."""

from __future__ import annotations

import tempfile
from pathlib import Path

from helixlang_lsp.analysis import Workspace, analyze


def _sample() -> str:
    return (
        "#config table=standard\n"
        "#promoter name=p_lac strength=0.8\n"
        "#gene name=lacZ promoter=p_lac call_target=helper\n"
        "ATG GCT CGT TAA\n"
        "#end\n"
        "#gene name=helper\n"
        "ATG GGT TAA\n"
        "#end\n"
    )


def test_analyze_basic():
    ana = analyze(_sample(), uri="file:///t.helix")
    assert ana.diagnostics == []
    assert ana.program is not None
    assert ana.table_name == "standard"
    assert ana.tokens is not None


def test_symbol_index():
    ana = analyze(_sample())
    symbols = ana.structure.symbols
    assert set(symbols) == {"p_lac", "lacZ", "helper"}
    assert symbols["p_lac"].kind == "promoter"
    assert symbols["lacZ"].kind == "gene"


def test_symbol_at():
    ana = analyze(_sample())
    # promoter reference in #gene header (line 2)
    sym = ana.symbol_at(2, 25)
    assert sym is not None and sym.name == "p_lac"
    # gene definition
    sym = ana.symbol_at(2, 12)
    assert sym is not None and sym.name == "lacZ"


def test_codon_decode():
    ana = analyze(_sample())
    codons = ana.structure.codon_tokens
    by_seq = {c.seq: c for c in codons}
    assert by_seq["ATG"].opcode == "OP_START"
    assert by_seq["GCT"].opcode == "OP_BUILD_PROTEIN"
    assert by_seq["TAA"].opcode == "OP_HALT"
    assert by_seq["CGT"].opcode == "OP_CALL_GENE"
    # wobble of GCT (third base T) = 3
    assert by_seq["GCT"].operand == 3


def test_codon_call_target_display():
    ana = analyze(_sample())
    cgt = next(c for c in ana.structure.codon_tokens if c.seq == "CGT")
    assert cgt.operand_display == "helper"


def test_gene_body_codons_assigned():
    ana = analyze(_sample())
    gene = next(a for a in ana.structure.annotations if a.kind == "gene"
                and a.body_codons and a.body_codons[0].seq == "ATG")
    assert len(gene.body_codons) == 4  # ATG GCT CGT TAA
    assert gene.body_codons[-1].seq == "TAA"  # stop codon included


def test_table_detection():
    ana = analyze("#config table=ciliate\n#gene name=g\nATG GGT TAA\n#end\n")
    assert ana.table_name == "ciliate"


def test_bad_table_falls_back():
    ana = analyze("#config table=wat\n#gene name=g\nATG GGT TAA\n#end\n")
    assert ana.table_name == "standard"
    assert any(d.code == "config" for d in ana.diagnostics)


def test_lex_error_returns_empty_structure():
    ana = analyze("#gene name=g\nATG GGGG TAA\n#end\n")
    assert ana.tokens is None
    assert any(d.code == "lex" for d in ana.diagnostics)


def test_workspace_index():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "a.helix").write_text(_sample(), encoding="utf-8")
        (root / "b.helix").write_text(
            "#promoter name=p_x strength=0.5\n", encoding="utf-8")
        ws = Workspace()
        ws.scan(str(root))
        assert len(ws._index) == 2
        found = ws.query("lacZ")
        assert any(name == "lacZ" for _uri, name, _sym in found)
        assert ws.query("p_*")  # wildcard


def test_analysis_seconds_recorded():
    ana = analyze(_sample())
    assert ana.analysis_seconds >= 0
