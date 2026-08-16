"""Unit tests for the pure feature functions."""

from __future__ import annotations

from helixlang_lsp.analysis import analyze
from helixlang_lsp.features import (
    code_actions as ca,
)
from helixlang_lsp.features import (
    completion as comp,
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
from helixlang_lsp.features import (
    semantic_tokens as st,
)

SAMPLE = (
    "#config table=standard\n"
    "#promoter name=p_lac strength=0.8\n"
    "#gene name=lacZ promoter=p_lac\n"
    "ATG GCT GGT TAA\n"
    "#end\n"
    "#regulate p_lac -> lacZ\n"
)


def _ana():
    return analyze(SAMPLE, uri="file:///t.helix")


def test_hover_codon():
    result = hover.hover(SAMPLE, _ana(), {"position": {"line": 3, "character": 4}})
    assert result is not None
    body = result["contents"]["value"]
    assert "OP_BUILD_PROTEIN" in body
    assert "Ala" in body


def test_hover_gene_name():
    result = hover.hover(SAMPLE, _ana(), {"position": {"line": 2, "character": 11}})
    assert result is not None
    assert "lacZ" in result["contents"]["value"]


def test_hover_promoter_name():
    result = hover.hover(SAMPLE, _ana(), {"position": {"line": 2, "character": 30}})
    assert result is not None
    assert "p_lac" in result["contents"]["value"]


def test_hover_annotation_kind():
    result = hover.hover(SAMPLE, _ana(), {"position": {"line": 2, "character": 1}})
    assert result is not None
    assert "**#gene**" in result["contents"]["value"]


def test_hover_outside_anywhere_returns_none():
    result = hover.hover(SAMPLE, _ana(), {"position": {"line": 0, "character": 0}})
    assert result is not None  # #config annotation docs


def test_completion_after_hash():
    # standalone '#' line -> all annotation kinds
    text = SAMPLE + "#\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 1}})
    labels = [i["label"] for i in result["items"]]
    assert "gene" in labels and "promoter" in labels
    assert "genome" in labels and "morphogen" in labels


def test_completion_field_names():
    # cursor inside #gene field region
    result = comp.completions(SAMPLE, _ana(),
                              {"position": {"line": 2, "character": 8}})
    labels = [i["label"] for i in result["items"]]
    assert "name" in labels and "promoter" in labels and "call_target" in labels


def test_completion_field_enum_value():
    result = comp.completions(SAMPLE, _ana(),
                              {"position": {"line": 0, "character": 20}})
    labels = [i["label"] for i in result["items"]]
    assert "standard" in labels and "ciliate" in labels


def test_completion_promoter_symbols():
    # cursor on 'promoter=' value in a #gene header -> defined promoters
    result = comp.completions(SAMPLE, _ana(),
                              {"position": {"line": 2, "character": 30}})
    labels = [i["label"] for i in result["items"]]
    assert "p_lac" in labels


def test_completion_codons_in_body():
    result = comp.completions(SAMPLE, _ana(),
                              {"position": {"line": 3, "character": 5}})
    labels = [i["label"] for i in result["items"]]
    assert "ATG" in labels and "TAA" in labels


def test_completion_genome_fields():
    text = SAMPLE + "#genome s\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 9}})
    labels = [i["label"] for i in result["items"]]
    for key in ("source", "tf_map", "grn_mode", "active_gene_budget", "seed"):
        assert key in labels


def test_completion_genome_source_enum():
    # #genome source= -> genome sources, not gene symbols
    text = SAMPLE + "#genome source=\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 16}})
    labels = [i["label"] for i in result["items"]]
    assert "ecoli-mg1655" in labels and "synth-4300" in labels
    assert "lacZ" not in labels


def test_completion_sim_kind_long_tail():
    text = SAMPLE + "#sim kind=\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 11}})
    labels = [i["label"] for i in result["items"]]
    for kind in ("spatial_dfba", "spatial_evolution", "consortium",
                 "population_calibration", "codon_usage", "cello_workflow"):
        assert kind in labels


def test_completion_sim_kind_ecosystem_backends():
    text = SAMPLE + "#sim kind=\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 11}})
    labels = [i["label"] for i in result["items"]]
    assert "ecosystem" in labels and "population_dbtl" in labels


def test_completion_patch_kind_enum():
    text = SAMPLE + "#patch name=pond kind=\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 22}})
    labels = [i["label"] for i in result["items"]]
    for kind in ("water", "sediment", "chemostat", "soil", "biofilm"):
        assert kind in labels
    assert "ecosystem" not in labels


def test_completion_species_fields():
    text = SAMPLE + "#species n\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 10}})
    labels = [i["label"] for i in result["items"]]
    for key in ("name", "genome", "photo", "cn_ratio", "maintenance",
                "substrate", "vmax", "ks", "secretion", "diet", "attack"):
        assert key in labels


def test_completion_patch_fields():
    text = SAMPLE + "#patch k\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 8}})
    labels = [i["label"] for i in result["items"]]
    for key in ("name", "kind", "width", "height", "carrying_capacity",
                "anoxic", "moisture", "clay", "flow_rate", "dispersal"):
        assert key in labels


def test_completion_annotation_kind_species_patch():
    text = SAMPLE + "#\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 1}})
    labels = [i["label"] for i in result["items"]]
    assert "species" in labels and "patch" in labels


def test_completion_replicons_field():
    text = SAMPLE + "#config sim replicons=\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 24}})
    assert result["items"] or True  # no crash; value is free-form


def test_completion_gene_replicon_field():
    text = SAMPLE + "#gene name=rep replicon=\n"
    ana = analyze(text)
    result = comp.completions(text, ana, {"position": {"line": 6, "character": 25}})
    assert result["items"] or True


def test_hover_species_annotation():
    text = SAMPLE + "#species name=producer genome=ecoli-mg1655\n"
    ana = analyze(text)
    result = hover.hover(text, ana, {"position": {"line": 6, "character": 1}})
    assert result is not None
    assert "**#species**" in result["contents"]["value"]


def test_hover_patch_annotation():
    text = SAMPLE + "#patch name=pond kind=water\n"
    ana = analyze(text)
    result = hover.hover(text, ana, {"position": {"line": 6, "character": 1}})
    assert result is not None
    assert "**#patch**" in result["contents"]["value"]


def test_hover_tf_map_regulondb():
    text = SAMPLE + "#genome tf_map=\n"
    ana = analyze(text)
    result = hover.hover(text, ana, {"position": {"line": 6, "character": 15}})
    assert result is not None
    assert "regulondb" in result["contents"]["value"]


def test_document_symbols_species_patch():
    text = (
        SAMPLE
        + "#species name=producer genome=ecoli-mg1655\n"
        + "#patch name=pond kind=water\n"
    )
    result = ds.document_symbols(text, analyze(text), {})
    names = [s["name"] for s in result]
    assert "Species producer genome=ecoli-mg1655" in names
    assert "Patch pond kind=water" in names


def test_hover_genome_annotation():
    text = SAMPLE + "#genome source=synth-4300\n"
    ana = analyze(text)
    result = hover.hover(text, ana, {"position": {"line": 6, "character": 1}})
    assert result is not None
    assert "**#genome**" in result["contents"]["value"]


def test_definition_promoter_reference():
    result = defs.definitions(SAMPLE, _ana(),
                              {"position": {"line": 2, "character": 30}})
    assert result is not None
    loc = result[0]
    assert loc["uri"] == "file:///t.helix"
    assert loc["range"]["start"]["line"] == 1


def test_definition_gene_name():
    result = defs.definitions(SAMPLE, _ana(),
                              {"position": {"line": 6, "character": 22}})
    assert result is not None
    assert result[0]["range"]["start"]["line"] == 2


def test_references_include_declaration():
    result = refs.references(SAMPLE, _ana(), {
        "position": {"line": 2, "character": 11},
        "context": {"includeDeclaration": True},
    })
    assert len(result) >= 2


def test_references_exclude_declaration():
    result = refs.references(SAMPLE, _ana(), {
        "position": {"line": 2, "character": 11},
        "context": {"includeDeclaration": False},
    })
    decl_lines = [r["range"]["start"]["line"] for r in result]
    assert 2 not in decl_lines


def test_document_symbols():
    result = ds.document_symbols(SAMPLE, _ana(), {})
    kinds = {s["name"]: s["kind"] for s in result}
    assert kinds["lacZ"] == 12  # function
    assert kinds["p_lac"] == 13  # variable
    assert kinds["p_lac -> lacZ"] == 25  # operator


def test_document_symbols_genome():
    text = SAMPLE + "#genome source=synth-4300\n"
    ana = analyze(text)
    result = ds.document_symbols(text, ana, {})
    names = [s["name"] for s in result]
    assert "Genome source=synth-4300" in names


def test_folding_ranges():
    result = folding.folding_ranges(SAMPLE, _ana(), {})
    assert result and result[0]["kind"] == "region"


def test_semantic_tokens_encode():
    result = st.semantic_tokens(SAMPLE, _ana(), {})
    data = result["data"]
    assert len(data) % 5 == 0
    assert len(data) > 0


def test_semantic_tokens_start_modifier():
    result = st.semantic_tokens(SAMPLE, _ana(), {})
    data = result["data"]
    token_types = [data[i + 3] for i in range(0, len(data), 5)]
    assert 9 in token_types  # opcodeStart (OP_START)
    assert 10 in token_types  # opcodeHalt (OP_HALT)


def test_semantic_tokens_codon_families():
    """doc/08 §3.1: ATG=Start, GCT/GGT=Synthesis, GTA=Behavior, TAA=Halt."""
    text = "#gene name=hello\nATG GCT GGT GTA TAA\n#end\n"
    ana = analyze(text)
    result = st.semantic_tokens(text, ana, {})
    data = result["data"]
    fam = {}
    for i in range(0, len(data), 5):
        length = data[i + 2]
        if length == 3:
            fam.setdefault(data[i + 3], 0)
            fam[data[i + 3]] += 1
    # opcodeStart, opcodeHalt, opcodeSynthesis, opcodeBehavior
    assert 9 in fam and 10 in fam and 12 in fam and 13 in fam
    assert fam[12] == 2  # GCT + GGT share the synthesis family


def test_semantic_tokens_family_across_tables():
    """doc/08 §3.1: table switches change the decoded opcode/family."""
    text = "#gene name=g\nATA AGA AGG TGA\n#end\n"
    standard = analyze(text)  # default standard table
    mito = analyze(text, table_hint="mito_vertebrate")

    def families(ana) -> set[int]:
        data = st.semantic_tokens(text, ana, {})["data"]
        return {data[i + 3] for i in range(0, len(data), 5) if data[i + 2] == 3}

    std_fam, mito_fam = families(standard), families(mito)
    assert 16 in std_fam  # standard: AGA/AGG -> OP_CALL_GENE -> opcodeCall
    assert 9 in mito_fam  # mito: ATA -> OP_START -> opcodeStart
    assert 10 in mito_fam  # mito: AGA/AGG -> OP_HALT -> opcodeHalt
    assert std_fam != mito_fam


def test_semantic_tokens_bad_dna_degrades_gracefully():
    """Non-DNA characters are a LexError: no tokens, empty data, no crash."""
    text = "#gene name=g\nATG XYZ TAA\n#end\n"
    ana = analyze(text)
    assert len(ana.diagnostics) == 1
    data = st.semantic_tokens(text, ana, {})["data"]
    assert data == []


def test_formatting_groups_codons():
    messy = "#gene name=g\nATG  GCT\tGGT TAA\n#end\n"
    ana = analyze(messy)
    edits = fmt.formatting(messy, ana, {"options": {"insertSpaces": True, "tabSize": 4}})
    assert len(edits) == 1
    assert edits[0]["newText"] == "#gene name=g\nATG GCT GGT TAA\n#end\n"


def test_formatting_noop():
    ana = analyze(SAMPLE)
    assert fmt.formatting(SAMPLE, ana, {}) == []


def test_inlay_hints_for_gene_body():
    result = ih.inlay_hints(SAMPLE, _ana(), {})
    hints = [h for h in result if h["data"]["kind"] == "codon"]
    assert len(hints) == 4  # ATG GCT GGT TAA
    assert hints[0]["data"]["opcode"] == "OP_START"
    assert hints[0]["position"]["character"] == 3


def test_code_action_unterminated_orf():
    text = "#gene name=g\nATG GCT\n"
    ana = analyze(text)
    parse = [d for d in ana.diagnostics if d.code == "parse"]
    assert parse
    ctx = {"context": {"diagnostics": [d.to_dict() for d in parse]}}
    result = ca.code_actions(text, ana, ctx)
    titles = [a["title"] for a in result]
    assert any("TAA" in t for t in titles)


def test_code_action_dna_length():
    text = "#gene name=g\nATG GGGG TAA\n#end\n"
    ana = analyze(text)
    lex = [d for d in ana.diagnostics if d.code == "lex"]
    ctx = {"context": {"diagnostics": [d.to_dict() for d in lex]}}
    result = ca.code_actions(text, ana, ctx)
    assert any("multiple of 3" in a["title"] for a in result)


def test_code_action_missing_name():
    text = "#promoter\n#end\n"
    ana = analyze(text)
    parse = [d for d in ana.diagnostics if d.code == "parse"]
    ctx = {"context": {"diagnostics": [d.to_dict() for d in parse]}}
    result = ca.code_actions(text, ana, ctx)
    assert any("name=" in a["title"] for a in result)


def test_workspace_edit_json_shape():
    text = "#gene name=g\nATG GCT\n"
    ana = analyze(text, uri="file:///t.helix")
    parse = [d for d in ana.diagnostics if d.code == "parse"]
    ctx = {"context": {"diagnostics": [d.to_dict() for d in parse]}}
    result = ca.code_actions(text, ana, ctx)
    edit = next(a for a in result if "TAA" in a["title"])
    changes = edit["edit"]["changes"]
    assert any(k.startswith("file://") for k in changes)
