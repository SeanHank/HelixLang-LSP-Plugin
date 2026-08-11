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


def decode_codon(codon: str, table_name: str = "standard") -> tuple[helix.Op, int] | None:
    """Return ``(opcode, wobble_operand)`` for a codon under ``table_name``."""
    table = helix.get_table(table_name)
    op = table.get(codon.upper())
    if op is None:
        return None
    return op, helix.wobble(codon.upper())
