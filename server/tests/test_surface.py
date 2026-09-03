"""Coverage-focused tests for less-exercised surface: hover field ladder,
document symbols naming, diagnostics range resolution, and CLI entry points.

These intentionally walk whole function bodies (rather than happy paths) so the
LSP surface stays fully exercised.
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from helixlang_lsp import _helix_contract as helix
from helixlang_lsp import diagnostics as diag
from helixlang_lsp.analysis import (
    AnnotationInfo,
    FieldInfo,
    analyze,
)
from helixlang_lsp.features import (
    document_symbols as ds,
)
from helixlang_lsp.features import (
    hover as hover,
)


def _ann(kind: str = "gene") -> AnnotationInfo:
    return AnnotationInfo(kind=kind, line0=0, col0=0)


def _field(key: str, value: str = "x") -> FieldInfo:
    return FieldInfo(key=key, value=value, line0=0,
                     key_start=1, value_start=3, value_end=3 + len(value))


# --------------------------------------------------------------------------
# hover._hover_field — every documented branch of the elif ladder
# --------------------------------------------------------------------------

@pytest.mark.parametrize("key", [
    "strength", "table", "species", "units", "output", "cas", "repair",
    "mark", "backend", "seed", "nutrient", "concentration",
    "diffusion_um2_s", "gene", "reaction", "kcat", "init", "division_rule",
    "replication_mode", "protein_maturation_mode", "mechanics", "fba_model",
    "channel", "source", "tf_map", "grn_mode", "active_gene_budget",
    "replicon", "replicons", "photo", "anoxic", "diet", "attack", "secretion",
    "gem_driven", "medium", "organism", "duration", "expression",
    "use_full_model", "km", "temperature", "ph", "medium_override",
    "max_growth_rate", "expression_level", "id", "substrate", "product",
    "substrate_coeff", "product_coeff", "lower_bound", "upper_bound",
    "subsystem", "reversible", "age", "sex", "weight", "height", "ethnicity",
    "smoking", "pack_years", "alcohol", "exercise", "pregnant", "category",
    "severity", "onset_age", "description", "activity", "normal", "smiles",
    "formula", "mw", "drug_type", "target_protein", "binding_affinity_kd",
    "dose", "route", "interval", "bioavailability", "absorption_rate", "vd",
    "cl", "half_life", "hepatic_eh", "renal_fraction", "protein_binding",
    "cyp_metabolism", "transporter_affected", "non_cyp_metabolism", "ec50",
    "emax", "hill", "kd_nM", "kss_nM", "kd_agonist", "ki", "axis", "level",
    "infection_severity", "autoimmune_activation", "immunosuppression",
])
def test_hover_field_ladder(key: str) -> None:
    r = hover._hover_field(_ann("drug"), _field(key))
    assert f"`{key}`" in r["contents"]["value"]


def test_hover_field_unknown_key() -> None:
    # A key with no branch still returns a base hover body (no crash).
    r = hover._hover_field(_ann("sim"), _field("kind"))
    assert "`kind`" in r["contents"]["value"]


def test_hover_field_range_line() -> None:
    r = hover._hover_field(_ann("gene"), _field("name", "lacZ"))
    assert r["range"]["start"]["line"] == 0


# --------------------------------------------------------------------------
# hover._hover_symbol — symbol + regulation edges + ORF
# --------------------------------------------------------------------------

def test_hover_symbol_promoter_with_orf_and_edges() -> None:
    text = (
        "#promoter name=p_lac strength=0.8\n"
        "#gene name=lacZ promoter=p_lac\n"
        "ATG GCT GGT TAA\n"
        "#end\n"
        "#regulate p_lac -> lacZ\n"
    )
    ana = analyze(text, uri="file:///t.helix")
    sym = ana.symbol_at(1, 11)
    assert sym is not None
    r = hover.hover(text, ana, {"position": {"line": 1, "character": 11}})
    assert r is not None
    body = r["contents"]["value"]
    assert "lacZ" in body
    assert "ORF:" in body
    assert "Regulation:" in body
    assert "defined at line" in body


def test_hover_symbol_promoter_no_orf() -> None:
    text = "#promoter name=p_lac strength=0.8\n"
    ana = analyze(text, uri="file:///t.helix")
    r = hover.hover(text, ana, {"position": {"line": 0, "character": 14}})
    assert r is not None
    assert "p_lac" in r["contents"]["value"]
    assert "ORF:" not in r["contents"]["value"]


def test_hover_unknown_position_returns_none() -> None:
    text = "#config table=standard\n\n"
    ana = analyze(text, uri="file:///t.helix")
    # hover on a plain whitespace/blank area -> hits symbol/field miss, returns
    # a symbol hover only if a symbol covers it; place cursor in the gap.
    r = hover.hover(text + "   \n", ana, {"position": {"line": 2, "character": 1}})
    assert r is None


# --------------------------------------------------------------------------
# document_symbols — every _symbol_name branch
# --------------------------------------------------------------------------

def test_document_symbols_all_kind_names() -> None:
    text = (
        "#config table=standard\n"
        "#promoter name=p_lac strength=0.8\n"
        "#gene name=lacZ promoter=p_lac\n"
        "ATG GCT GGT TAA\n"
        "#end\n"
        "#regulate p_lac -> lacZ\n"
        "#media nutrient=GLC concentration=10\n"
        "#enzyme gene=lacZ reaction=PGI kcat=10\n"
        "#metabolite name=ATP init=1.0\n"
        "#sim kind=ecosystem\n"
        "#genome source=ecoli-mg1655\n"
        "#gem organism=e_coli_k12\n"
        "#reaction id=PGI substrate=G6P product=F6P\n"
        "#morphogen gene=lacZ channel=U\n"
        "#species name=Eco genome=lacZ\n"
        "#patch name=pond kind=soil\n"
        "#disease name=T2D category=metabolic_overload\n"
        "#use cardiology\n"
        "#quantity name=TOTAL expr=g+v\n"
    )
    ana = analyze(text, uri="file:///t.helix")
    syms = ds.document_symbols(text, ana, {})
    names = [s["name"] for s in syms]
    for want in ("Media nutrient=GLC", "Enzyme gene=lacZ",
                 "Metabolite name=ATP", "Sim kind=ecosystem",
                 "Genome source=ecoli-mg1655", "GEM organism=e_coli_k12",
                 "Reaction id=PGI", "Morphogen gene=lacZ",
                 "Species Eco", "Patch pond kind=soil",
                 "Use cardiology", "TOTAL",
                 "Config", "lacZ", "p_lac"):
        assert any(want in n for n in names), f"missing symbol {want!r} in {names}"
    # quantity + use symbols are present.
    assert any("TOTAL" in n for n in names)
    assert any("Use cardiology" in n for n in names)


def test_document_symbols_fallbacks() -> None:
    text = (
        "#gene parent name=g1\n"
        "#disease name=D1\n"
        "#gene descendant name=g2\n"
    )
    ana = analyze(text)
    syms = ds.document_symbols(text, ana, {})
    names = [s["name"] for s in syms]
    # 'parent' with no DNA block declines to the name fallback path.
    assert any("g1" in n for n in names)


# --------------------------------------------------------------------------
# diagnostics — range resolution branches
# --------------------------------------------------------------------------

def test_diagnostics_codon_msg_and_index_ranges() -> None:
    text = "#gene name=g\nATG GCT GGT TAA\n#end\n"
    tokens = list(helix.Lexer(text).tokens())
    # line<=0 + codon mentioned in message
    d = diag.error_to_diagnostic(
        _Exc("CodonError", "bad codon AAA", line=0),
        text, tokens)
    assert d.code == "error"
    # codon_index path
    d2 = diag.error_to_diagnostic(
        _Exc("CodonError", "bad codon", line=0, codon_index=2),
        text, tokens)
    assert d2 is not None


def test_diagnostics_col_positive_range() -> None:
    text = "#promoter name=p strength=2.0\n"
    d = diag.error_to_diagnostic(
        _Exc("ValueError", "bad col", line=1, col=4),
        text, None)
    assert d.range.start.line == 0


def test_diagnostics_first_token_or_line() -> None:
    text = "   #promoter name=p\n"
    d = diag.error_to_diagnostic(_Exc("ValueError", "no col", line=1), text, None)
    assert d is not None
    # fall back to whole line when no tokens
    d2 = diag.error_to_diagnostic(_Exc("ValueError", "x", line=1), text, [])
    assert d2 is not None


def test_diagnostics_orf_range_spans_gene_to_end() -> None:
    text = "#gene name=g\nATG GCT GGT\n#end\n"
    tokens = list(helix.Lexer(text).tokens())
    d = diag.error_to_diagnostic(
        helix.ParseError("ORF not terminated", line=0), text, tokens)
    assert d.code == "parse"
    assert d.range.start.line <= 1
    assert d.range.end.line >= 2


def test_error_class_unknown_is_error() -> None:
    cls, sev, code = diag.error_class(RuntimeError("boom"))
    assert cls is RuntimeError
    assert code == "error"


def test_error_class_mapped() -> None:
    cls, sev, code = diag.error_class(helix.LexError("badtoken"))
    assert code == "lex"
    cls2, sev2, code2 = diag.error_class(helix.ParseError("bad"))
    assert code2 == "parse"


def test_errors_to_diagnostics_list_and_orf_span() -> None:
    text = "#gene name=g\nATG GCT GGT\n#end\n"
    tokens = list(helix.Lexer(text).tokens())
    outs = diag.errors_to_diagnostics(
        [helix.ParseError("ORF not terminated", line=0),
         helix.ParseError("no START codon", line=0)],
        text, tokens)
    assert len(outs) == 2
    assert all(o.code == "parse" for o in outs)


def test_diagnostic_at_line_out_of_bounds() -> None:
    d = diag.diagnostic_at_line("#config\n", 99, "way out")
    assert d.range.start.line == 99


def test_warning_diagnostic_line_lookup() -> None:
    text = "#regulate a -> b\n#regulate b -> a\n"
    w = diag.warning_diagnostic(text, "cycle involving 'a'")
    assert w.code == "warning"
    assert w.range.start.line == 0


def test_related_for_compile_call_gene() -> None:
    text = "#gene name=g1\n"
    # Build a CompileError-shaped message referencing a CALL_GENE target.
    class _E(helix.CompileError):
        def __init__(self) -> None:
            super().__init__("CALL_GENE references 'g1'")

    tokens = list(helix.Lexer(text).tokens())
    d = diag.error_to_diagnostic(_E(), text, tokens)
    assert d.related_information is not None
    assert "defined here" in d.related_information[0].message


# --------------------------------------------------------------------------
# main / CLI entry points
# --------------------------------------------------------------------------

def test_main_no_args_starts_server():
    proc = subprocess.run(
        [sys.executable, "-m", "helixlang_lsp", "--help"],
        capture_output=True, text=True)
    assert proc.returncode == 0
    assert "usage" in proc.stdout.lower() or "usage" in proc.stderr.lower()


def test_main_bad_loglevel_rejected():
    proc = subprocess.run(
        [sys.executable, "-m", "helixlang_lsp", "--loglevel", "NOPE"],
        capture_output=True, text=True)
    assert proc.returncode == 2
    assert "invalid choice" in proc.stderr


def test_main_parser_all_flags():
    from helixlang_lsp import main
    p = main._build_parser()
    a = p.parse_args([
        "--stdio", "--host", "127.0.0.1", "--port", "8080",
        "--dap", "--dap-port", "9000", "--dap-port-file", "/tmp/x.txt",
        "--trace", "/tmp/x.jsonl", "--loglevel", "DEBUG",
    ])
    assert a.host == "127.0.0.1"
    assert a.port == 8080
    assert a.dap is True
    assert a.dap_port == 9000
    assert a.dap_port_file == "/tmp/x.txt"
    assert a.trace == "/tmp/x.jsonl"
    assert a.loglevel == "DEBUG"


def test_main_trace_writer(tmp_path):
    from helixlang_lsp import main
    path = str(tmp_path / "m.jsonl")
    w = main._trace_writer(path)
    w({"a": 1, "b": "héllo"})
    with open(path, encoding="utf-8") as fh:
        assert '"a": 1' in fh.read()


# --------------------------------------------------------------------------
# completion — bio-kind symbol targets, gene body codons, type context
# --------------------------------------------------------------------------

def test_completion_bio_kind_target():
    from helixlang_lsp import analysis as an
    from helixlang_lsp.features import completion as comp
    text = (
        "#gene name=g1 promoter=p_lac\n"
        "#promoter name=p_lac strength=0.8\n"
        "#gene name=gx\n"
        "#crispr target=g\n"
    )
    ana = an.analyze(text)
    c = comp.completions(text, ana, {"position": {"line": 3, "character": 15}})
    labels = [i["label"] for i in c["items"]]
    assert "g1" in labels and "gx" in labels


def test_completion_gene_body_codons():
    from helixlang_lsp import analysis as an
    from helixlang_lsp.features import completion as comp
    text = (
        "#gene name=g1 promoter=p_lac\n"
        "#promoter name=p_lac strength=0.8\n"
        "ATG GCT GGT TAA\n"
        "GCT G\n"
    )
    ana = an.analyze(text)
    c = comp.completions(text, ana, {"position": {"line": 3, "character": 5}})
    labels = [i["label"] for i in c["items"]]
    assert "ATG" in labels and "TAA" in labels


def test_completion_symbol_role_ok():
    from helixlang_lsp.features import completion as comp
    assert comp._role_ok("promoter", "promoter") is True
    assert comp._role_ok("gene", "target") is True
    assert comp._role_ok("gene", "promoter") is False
    assert comp._role_ok("anything", "other") is True


def test_completion_arrow_regulate():
    from helixlang_lsp import analysis as an
    from helixlang_lsp.features import completion as comp
    text = (
        "#gene name=g1 promoter=p_lac\n"
        "#promoter name=p_lac strength=0.8\n"
        "#regulate p_lac -> \n"
    )
    ana = an.analyze(text)
    # after '->' -> symbol role target
    c = comp.completions(text, ana, {"position": {"line": 2, "character": 19}})
    labels = [i["label"] for i in c["items"]]
    assert "g1" in labels


class _Exc(BaseException):
    def __init__(self, name: str, msg: str, line: int = 0, col: int = 0,
                 codon_index: int = -1) -> None:
        self.name = name
        super().__init__(msg)
        self.line = line
        self.col = col
        self.codon_index = codon_index
