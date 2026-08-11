"""Contract tests: reflect over the ``helixlang`` symbols the server depends on.

Fails loudly when the upstream compiler API drifts (doc/06 §5).
"""

from __future__ import annotations

import inspect

from helixlang_lsp import _helix_contract as helix


def test_required_symbols_exist():
    required = [
        "Op", "STANDARD_TABLE", "TABLES", "OP_OPERAND_BYTES",
        "get_table", "wobble", "Lexer", "Token", "Parser",
        "SemanticAnalyzer", "Compiler", "disassemble", "Chunk", "CellVM",
        "stop_codons_from_table", "HelixError", "LexError", "ParseError",
        "SemanticError", "RegulationError", "CompileError",
        "RuntimeHelixError", "BioError", "Program", "Promoter", "Gene",
        "Codon", "Regulation", "Config", "LSystemDecl", "FieldDecl",
        "BioInstruction",
    ]
    for name in required:
        assert hasattr(helix, name), f"missing helixlang symbol: {name}"


def test_standard_table_has_64_codons():
    assert len(helix.STANDARD_TABLE) == 64


def test_tables_names():
    assert set(helix.TABLES) == {"standard", "mito_vertebrate", "ciliate"}


def test_errors_are_helix_errors():
    for cls in [helix.LexError, helix.ParseError, helix.SemanticError,
                helix.RegulationError, helix.CompileError,
                helix.RuntimeHelixError, helix.BioError]:
        assert issubclass(cls, helix.HelixError)


def test_callables_have_expected_signatures():
    sig = inspect.signature(helix.Parser.__init__)
    assert "enable_type_check" in sig.parameters or any(
        p.name == "enable_type_check" for p in sig.parameters.values())
    assert inspect.isfunction(helix.get_table)
    assert inspect.isfunction(helix.wobble)
    assert inspect.isfunction(helix.stop_codons_from_table)
    assert inspect.isfunction(helix.disassemble)


def test_contract_map_classes():
    for name, cls in helix._CONTRACT.items():
        assert inspect.isclass(cls), f"{name} not a class"
