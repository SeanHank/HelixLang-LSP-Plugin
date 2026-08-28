"""HelixLang API contract — the exact subset of ``helixlang`` the server uses.

Kept in sync with ``HelixLang/src/helixlang``. The CI "import-check" imports
this module and reflects over each symbol to fail loudly when the compiler API
drifts (see doc/06 §5).

Grounding rule: if ``helixlang`` changes these signatures, the server is broken
and must be updated in lockstep.
"""

from helixlang.core.ast_nodes import (
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
from helixlang.core.bytecode import Chunk
from helixlang.core.codon_table import (
    OP_OPERAND_BYTES,
    STANDARD_TABLE,
    TABLES,
    Op,
    get_table,
    wobble,
)
from helixlang.core.compiler import Compiler
from helixlang.core.disassembler import disassemble
from helixlang.core.errors import (
    BioError,
    CompileError,
    HelixError,
    LexError,
    ParseError,
    RegulationError,
    RuntimeHelixError,
    SemanticError,
)
from helixlang.core.lexer import Lexer, Token
from helixlang.core.parser import Parser
from helixlang.core.semantic import SemanticAnalyzer
from helixlang.core.vm import CellVM
from helixlang.plugins.runtime.seq_utils import stop_codons_from_table

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
