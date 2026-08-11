"""HelixLang API contract — the exact subset of ``helixlang`` the server uses.

Kept in sync with ``HelixLang/src/helixlang``. The CI "import-check" imports
this module and reflects over each symbol to fail loudly when the compiler API
drifts (see doc/06 §5).

Grounding rule: if ``helixlang`` changes these signatures, the server is broken
and must be updated in lockstep.
"""

from helixlang.ast_nodes import (
    BioInstruction,
    Codon,
    Config,
    FieldDecl,
    Gene,
    LSystemDecl,
    Program,
    Promoter,
    Regulation,
)
from helixlang.bytecode import Chunk
from helixlang.codon_table import (
    OP_OPERAND_BYTES,
    STANDARD_TABLE,
    TABLES,
    Op,
    get_table,
    wobble,
)
from helixlang.compiler import Compiler
from helixlang.disassembler import disassemble
from helixlang.errors import (
    BioError,
    CompileError,
    HelixError,
    LexError,
    ParseError,
    RegulationError,
    RuntimeHelixError,
    SemanticError,
)
from helixlang.lexer import Lexer, Token
from helixlang.parser import Parser
from helixlang.semantic import SemanticAnalyzer
from helixlang.seq_utils import stop_codons_from_table
from helixlang.vm import CellVM

# The symbols above must satisfy this signature contract.
# Each entry is (symbol, callable?) checked by _helix_contract tests.
_CONTRACT: dict[str, type] = {
    "Lexer": Lexer,
    "Parser": Parser,
    "SemanticAnalyzer": SemanticAnalyzer,
    "Compiler": Compiler,
    "CellVM": CellVM,
}

__all__ = [
    "Op",
    "STANDARD_TABLE",
    "TABLES",
    "OP_OPERAND_BYTES",
    "get_table",
    "wobble",
    "Lexer",
    "Token",
    "Parser",
    "SemanticAnalyzer",
    "Compiler",
    "disassemble",
    "Chunk",
    "CellVM",
    "stop_codons_from_table",
    "HelixError",
    "LexError",
    "ParseError",
    "SemanticError",
    "RegulationError",
    "CompileError",
    "RuntimeHelixError",
    "BioError",
    "Program",
    "Promoter",
    "Gene",
    "Codon",
    "Regulation",
    "Config",
    "LSystemDecl",
    "FieldDecl",
    "BioInstruction",
]
