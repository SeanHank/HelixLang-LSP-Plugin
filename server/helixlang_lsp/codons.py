"""Shared codon data: amino-acid mapping and opcode families.

Built from the standard genetic code (NCBI table 1). Used by hover, inlay
hints, completion, and semantic-token classification.
"""

from __future__ import annotations

from helixlang_lsp import _helix_contract as helix

# codon -> (three-letter amino acid, one-letter code); "*" = stop
_AA = {
    "TTT": ("Phe", "F"), "TTC": ("Phe", "F"),
    "TTA": ("Leu", "L"), "TTG": ("Leu", "L"),
    "TCT": ("Ser", "S"), "TCC": ("Ser", "S"), "TCA": ("Ser", "S"), "TCG": ("Ser", "S"),
    "TAT": ("Tyr", "Y"), "TAC": ("Tyr", "Y"),
    "TAA": ("Stop", "*"), "TAG": ("Stop", "*"), "TGA": ("Stop", "*"),
    "TGT": ("Cys", "C"), "TGC": ("Cys", "C"),
    "TGG": ("Trp", "W"),
    "CTT": ("Leu", "L"), "CTC": ("Leu", "L"), "CTA": ("Leu", "L"), "CTG": ("Leu", "L"),
    "CCT": ("Pro", "P"), "CCC": ("Pro", "P"), "CCA": ("Pro", "P"), "CCG": ("Pro", "P"),
    "CAT": ("His", "H"), "CAC": ("His", "H"),
    "CAA": ("Gln", "Q"), "CAG": ("Gln", "Q"),
    "CGT": ("Arg", "R"), "CGC": ("Arg", "R"), "CGA": ("Arg", "R"), "CGG": ("Arg", "R"),
    "ATT": ("Ile", "I"), "ATC": ("Ile", "I"), "ATA": ("Ile", "I"),
    "ATG": ("Met", "M"),
    "ACT": ("Thr", "T"), "ACC": ("Thr", "T"), "ACA": ("Thr", "T"), "ACG": ("Thr", "T"),
    "AAT": ("Asn", "N"), "AAC": ("Asn", "N"),
    "AAA": ("Lys", "K"), "AAG": ("Lys", "K"),
    "AGT": ("Ser", "S"), "AGC": ("Ser", "S"), "AGA": ("Arg", "R"), "AGG": ("Arg", "R"),
    "GTT": ("Val", "V"), "GTC": ("Val", "V"), "GTA": ("Val", "V"), "GTG": ("Val", "V"),
    "GCT": ("Ala", "A"), "GCC": ("Ala", "A"), "GCA": ("Ala", "A"), "GCG": ("Ala", "A"),
    "GAT": ("Asp", "D"), "GAC": ("Asp", "D"),
    "GAA": ("Glu", "E"), "GAG": ("Glu", "E"),
    "GGT": ("Gly", "G"), "GGC": ("Gly", "G"), "GGA": ("Gly", "G"), "GGG": ("Gly", "G"),
}

AA_NAMES: dict[str, tuple[str, str]] = dict(_AA)


def amino_acid(codon: str) -> tuple[str, str] | None:
    """Return ``(three_letter, one_letter)`` for a codon, or ``None``."""
    return _AA.get(codon.upper())


_REVERSE_OP: dict[int, list[str]] = {}
for _name, _op in helix.STANDARD_TABLE.items():
    _REVERSE_OP.setdefault(int(_op), []).append(_name)
for _lst in _REVERSE_OP.values():
    _lst.sort()


def codon_family(op: helix.Op) -> list[str]:
    """All codons mapping to the same opcode (synonymous aliases)."""
    return list(_REVERSE_OP.get(int(op), []))


def codons_for_opcode(op: helix.Op) -> list[str]:
    """Sorted codon aliases for an opcode (empty if none encode it)."""
    return list(_REVERSE_OP.get(int(op), []))


def wobble_base(codon: str) -> str:
    return codon.upper()[2]


# Codon color families (doc/08 §3.1). Every ``Op`` maps to one family; codons
# that decode to the same opcode share a family (and therefore a color). The
# client mirrors this table for rendering-only offline fallback.
OPCODE_FAMILY: dict[int, str] = {
    int(helix.Op.OP_START): "opcodeStart",
    int(helix.Op.OP_HALT): "opcodeHalt",
    int(helix.Op.OP_PUSH_CONST): "opcodeStack",
    int(helix.Op.OP_POP): "opcodeStack",
    int(helix.Op.OP_DUP): "opcodeStack",
    int(helix.Op.OP_SWAP): "opcodeStack",
    int(helix.Op.OP_BUILD_PROTEIN): "opcodeSynthesis",
    int(helix.Op.OP_BUILD_MEMBRANE): "opcodeSynthesis",
    int(helix.Op.OP_BUILD_PIGMENT): "opcodeSynthesis",
    int(helix.Op.OP_MOVE): "opcodeBehavior",
    int(helix.Op.OP_SIGNAL): "opcodeBehavior",
    int(helix.Op.OP_DIVIDE): "opcodeBehavior",
    int(helix.Op.OP_DIE): "opcodeBehavior",
    int(helix.Op.OP_FEED): "opcodeBehavior",
    int(helix.Op.OP_GROW_LSYSTEM): "opcodeMorphology",
    int(helix.Op.OP_DIFFUSE): "opcodeMorphology",
    int(helix.Op.OP_REACT): "opcodeMorphology",
    int(helix.Op.OP_EMIT_MORPHOGEN): "opcodeMorphology",
    int(helix.Op.OP_READ_MEM): "opcodeRegulation",
    int(helix.Op.OP_WRITE_MEM): "opcodeRegulation",
    int(helix.Op.OP_MODIFY_STATE): "opcodeRegulation",
    int(helix.Op.OP_REGULATE): "opcodeRegulation",
    int(helix.Op.OP_BIND): "opcodeRegulation",
    int(helix.Op.OP_CALL_GENE): "opcodeCall",
    int(helix.Op.OP_ADD): "opcodeArithmetic",
    int(helix.Op.OP_SUB): "opcodeArithmetic",
    int(helix.Op.OP_MUL): "opcodeArithmetic",
    int(helix.Op.OP_LT): "opcodeArithmetic",
    int(helix.Op.OP_NOT): "opcodeArithmetic",
    int(helix.Op.OP_JUMP): "opcodeArithmetic",
    int(helix.Op.OP_JUMP_IF_ZERO): "opcodeArithmetic",
    int(helix.Op.OP_TICK): "opcodeArithmetic",
    int(helix.Op.OP_DEBUG): "opcodeArithmetic",
}

# Opcodes never produced by codon decode (compiler/VM-generated only).
_OP_RETURN = int(helix.Op.OP_RETURN)
_OP_NOP = int(helix.Op.OP_NOP)


def opcode_family(op: helix.Op) -> str | None:
    """Return the semantic-token family for an opcode (doc/08 §3.1)."""
    op_int = int(op)
    if op_int in (_OP_RETURN, _OP_NOP):
        return None
    return OPCODE_FAMILY.get(op_int)


def decode_codon(codon: str, table_name: str = "standard") -> tuple[helix.Op, int] | None:
    """Return ``(opcode, wobble_operand)`` for a codon under ``table_name``."""
    table = helix.get_table(table_name)
    op = table.get(codon.upper())
    if op is None:
        return None
    return op, helix.wobble(codon.upper())
