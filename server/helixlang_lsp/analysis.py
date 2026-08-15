"""Analysis pipeline: wrap the HelixLang compiler for the language server.

Provides:
- ``analyze()`` — full/lenient compilation of one document, producing LSP
  diagnostics plus a symbol/structure index.
- ``scan_structure()`` — token-based structure/symbol scan (navigation, symbols,
  folding, references).
- ``Workspace`` — cross-file symbol index for ``workspace/symbol``.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from helixlang_lsp import _helix_contract as helix
from helixlang_lsp import diagnostics as diag_mod
from helixlang_lsp.protocol import Diagnostic, Range

CONFIG_TABLE_RE = re.compile(r"#config[^\n]*\btable=([A-Za-z0-9_]+)")

ANNOTATION_KINDS = (
    "gene", "promoter", "regulate", "lsystem", "field", "config", "type",
    "crispr", "evolve", "methylate", "histone", "transcribe", "translate",
    "quorum", "media", "enzyme", "metabolite", "sim", "genome", "morphogen",
)
BIO_INSTRUCTION_KINDS = {
    "crispr", "evolve", "methylate", "histone",
    "transcribe", "translate", "quorum",
}
REQUIRED_FIELDS = {
    "promoter": ("name", "strength"),
    "gene": (),
    "config": (),
    "lsystem": (),
    "field": (),
    "type": (),
    "regulate": (),
    "media": ("nutrient", "concentration"),
    "enzyme": ("gene", "reaction"),
    "metabolite": ("name",),
    "sim": (),
    "genome": (),
    "morphogen": ("gene",),
}
VALID_TABLE_NAMES = tuple(helix.TABLES.keys())


# --------------------------------------------------------------------------
# Structure / symbol scan
# --------------------------------------------------------------------------

@dataclass(slots=True)
class FieldInfo:
    key: str
    value: str
    line0: int
    key_start: int  # UTF-16 column of the key
    value_start: int
    value_end: int


@dataclass(slots=True)
class CodonInfo:
    seq: str
    line0: int
    col0: int  # UTF-16 column
    opcode: str | None = None
    operand: int | None = None
    operand_display: str | None = None
    table: str = "standard"


@dataclass(slots=True)
class AnnotationInfo:
    kind: str
    line0: int
    col0: int  # column of '#'
    fields: list[FieldInfo] = field(default_factory=list)
    body_codons: list[CodonInfo] = field(default_factory=list)
    end_line0: int | None = None  # line of '#end' if present
    has_end: bool = False


@dataclass(slots=True)
class DnaBlock:
    start_line0: int
    end_line0: int
    codons: list[CodonInfo] = field(default_factory=list)


@dataclass(slots=True)
class SymbolInfo:
    name: str
    kind: str  # "gene" | "promoter"
    def_line0: int
    def_start: int  # UTF-16 column (value span of name=...)
    def_end: int
    usages: list[Range] = field(default_factory=list)

    def definition_range(self, text: str) -> Range:
        from helixlang_lsp.positions import token_span_to_range
        return token_span_to_range(text, self.def_line0 + 1, self.def_start + 1,
                                   self.def_end - self.def_start)


@dataclass(slots=True)
class ScanResult:
    annotations: list[AnnotationInfo] = field(default_factory=list)
    dna_blocks: list[DnaBlock] = field(default_factory=list)
    symbols: dict[str, SymbolInfo] = field(default_factory=dict)
    gene_names_ordered: list[str] = field(default_factory=list)
    codon_tokens: list[CodonInfo] = field(default_factory=list)
    references: list[tuple[str, Range]] = field(default_factory=list)


def _decode_codon(seq: str, table: dict[str, Any], names: list[str],
                  call_target: str | None) -> tuple[str | None, int | None, str | None]:
    op = table.get(seq)
    if op is None:
        return None, None, None
    opcode = op.name
    operand: int | None = None
    display: str | None = None
    nbytes = helix.OP_OPERAND_BYTES[op]
    if nbytes >= 1:
        w = helix.wobble(seq)
        operand = w
        if op == helix.Op.OP_CALL_GENE:
            target = call_target if call_target else (
                names[w % len(names)] if names else None)
            display = target
        else:
            display = str(w)
    return opcode, operand, display


def scan_structure(tokens: list[helix.Token], text: str,
                   table_name: str = "standard") -> ScanResult:
    """Build a symbol/structure index from lexer tokens (0-based spans)."""
    result = ScanResult()
    try:
        table = helix.get_table(table_name)
    except helix.HelixError:
        table = helix.get_table("standard")

    annotations: list[AnnotationInfo] = []
    dna_blocks: list[DnaBlock] = []
    current: AnnotationInfo | None = None
    open_dna: DnaBlock | None = None

    def flush_dna() -> None:
        nonlocal open_dna
        if open_dna is not None:
            dna_blocks.append(open_dna)
            open_dna = None

    for tok in tokens:
        if tok.kind == "NEWLINE":
            continue
        if tok.kind == "ANNOT_START":
            flush_dna()
            current = AnnotationInfo(kind=tok.value, line0=tok.line - 1,
                                     col0=tok.col - 1)
            annotations.append(current)
        elif tok.kind == "FIELD":
            key, _, val = tok.value.partition("=")
            base = tok.col - 1
            if current is not None:
                current.fields.append(FieldInfo(
                    key, val, tok.line - 1, base, base + len(key) + 1,
                    base + len(key) + 1 + len(val)))
        elif tok.kind == "ARROW":
            src, _, tgt = tok.value.partition("->")
            base = tok.col - 1
            if current is not None:
                current.fields.append(FieldInfo(
                    "__arrow_src", src, tok.line - 1, base, base, base + len(src)))
                current.fields.append(FieldInfo(
                    "__arrow_tgt", tgt, tok.line - 1, base + len(src) + 3,
                    base + len(src) + 3, base + len(src) + 3 + len(tgt)))
        elif tok.kind == "CODON":
            ci = CodonInfo(seq=tok.value, line0=tok.line - 1, col0=tok.col - 1,
                           table=table_name)
            if current is not None and current.kind == "gene":
                current.body_codons.append(ci)
            else:
                if open_dna is None:
                    open_dna = DnaBlock(start_line0=tok.line - 1,
                                        end_line0=tok.line - 1)
                open_dna.codons.append(ci)
                open_dna.end_line0 = tok.line - 1
            result.codon_tokens.append(ci)
        elif tok.kind == "ANNOT_END":
            if current is not None:
                current.end_line0 = tok.line - 1
                current.has_end = True
            flush_dna()
        elif tok.kind == "EOF":
            break
    flush_dna()

    # ---------- gene ordering + decode codon tokens ----------
    gene_names: list[str] = []
    for ann in annotations:
        name = _field(ann, "name")
        if ann.kind == "gene" and name:
            gene_names.append(name)
    result.gene_names_ordered = gene_names

    call_targets = {id(a): _field(a, "call_target") for a in annotations}
    for ann in annotations:
        for ci in ann.body_codons:
            _decode_into(ci, table, gene_names, call_targets.get(id(ann)))
    for block in dna_blocks:
        for ci in block.codons:
            _decode_into(ci, table, gene_names, None)

    result.annotations = annotations
    result.dna_blocks = dna_blocks
    _build_symbols(result, text)
    return result


def _decode_into(ci: CodonInfo, table: dict[str, Any], names: list[str],
                 call_target: str | None) -> None:
    opcode, operand, display = _decode_codon(ci.seq, table, names, call_target)
    ci.opcode = opcode
    ci.operand = operand
    ci.operand_display = display


def _field(ann: AnnotationInfo, key: str) -> str | None:
    for f in ann.fields:
        if f.key == key:
            return f.value
    return None


def _build_symbols(result: ScanResult, text: str) -> None:
    """Populate ``result.symbols`` and per-symbol usages from annotations."""
    # definitions
    for ann in result.annotations:
        if ann.kind in ("gene", "promoter"):
            name = _field(ann, "name")
            if not name:
                continue
            f = next((x for x in ann.fields if x.key == "name"), None)
            if f is None:
                continue
            result.symbols[name] = SymbolInfo(
                name=name, kind=ann.kind, def_line0=f.line0,
                def_start=f.value_start, def_end=f.value_end)
    # references
    for ann in result.annotations:
        for f in ann.fields:
            if f.key == "promoter" and f.value:
                _add_ref(result, text, f.value, f.line0, f.value_start, f.value_end)
            elif f.key == "call_target" and f.value:
                _add_ref(result, text, f.value, f.line0, f.value_start, f.value_end)
            elif f.key == "target" and ann.kind in BIO_INSTRUCTION_KINDS and f.value:
                _add_ref(result, text, f.value, f.line0, f.value_start, f.value_end)
            elif f.key == "__arrow_src" and f.value:
                _add_ref(result, text, f.value, f.line0, f.value_start, f.value_end)
            elif f.key == "__arrow_tgt" and f.value:
                _add_ref(result, text, f.value, f.line0, f.value_start, f.value_end)
            elif f.key not in ("__arrow_src", "__arrow_tgt", "name", "promoter",
                               "call_target", "target") and ann.kind == "type" and f.value:
                # #type <symbol>=<Type>: the key is the symbol reference
                _add_ref(result, text, f.key, f.line0, f.key_start, f.value_start)
    # definition is its own usage (includeDeclaration)
    for sym in result.symbols.values():
        rng = sym.definition_range(text)
        sym.usages.insert(0, rng)
        result.references.append((sym.name, rng))


def _add_ref(result: ScanResult, text: str, name: str, line0: int,
             start: int, end: int) -> None:
    from helixlang_lsp.positions import token_span_to_range
    rng = token_span_to_range(text, line0 + 1, start + 1, end - start)
    result.references.append((name, rng))
    sym = result.symbols.get(name)
    if sym is not None:
        sym.usages.append(rng)


# --------------------------------------------------------------------------
# Lenient structural checks (many squiggles at once)
# --------------------------------------------------------------------------

def _structural_check(tokens: list[helix.Token], text: str,
                      table_name: str) -> list[Diagnostic]:
    """Best-effort multi-error pass over annotation blocks."""
    out: list[Diagnostic] = []
    ann: AnnotationInfo | None = None

    def check(ann2: AnnotationInfo | None) -> None:
        if ann2 is None or ann2.kind in ("dna", "gene", "regulate"):
            return
        if ann2.kind not in ANNOTATION_KINDS:
            msg = f"unknown annotation #{ann2.kind}"
            out.append(diag_mod.diagnostic_at_line(
                text, ann2.line0, msg, severity=1, code="parse",
                data={"className": "ParseError"}))
            return
        for req in REQUIRED_FIELDS.get(ann2.kind, ()):
            if not any(f.key == req for f in ann2.fields):
                msg = f"#{ann2.kind} missing {req}= field"
                out.append(diag_mod.diagnostic_at_line(
                    text, ann2.line0, msg, severity=1, code="parse",
                    data={"className": "ParseError"}))
    for tok in tokens:
        if tok.kind == "NEWLINE":
            continue
        if tok.kind == "ANNOT_START":
            check(ann)
            ann = AnnotationInfo(kind=tok.value, line0=tok.line - 1,
                                  col0=tok.col - 1)
        elif tok.kind == "FIELD" and ann is not None:
            key, _, val = tok.value.partition("=")
            base = tok.col - 1
            ann.fields.append(FieldInfo(key, val, tok.line - 1, base,
                                        base + len(key) + 1,
                                        base + len(key) + 1 + len(val)))
        elif tok.kind == "ARROW" and ann is not None:
            src, _, tgt = tok.value.partition("->")
            base = tok.col - 1
            ann.fields.append(FieldInfo("__arrow_src", src, tok.line - 1,
                                        base, base, base + len(src)))
            ann.fields.append(FieldInfo("__arrow_tgt", tgt, tok.line - 1,
                                        base + len(src) + 3,
                                        base + len(src) + 3,
                                        base + len(src) + 3 + len(tgt)))
    check(ann)
    return out


# --------------------------------------------------------------------------
# The analysis result + analyze()
# --------------------------------------------------------------------------

@dataclass(slots=True)
class Analysis:
    uri: str
    text: str
    table_name: str
    tokens: list[helix.Token] | None
    program: helix.Program | None
    chunk: helix.Chunk | None
    diagnostics: list[Diagnostic]
    structure: ScanResult
    disassembly: str | None = None
    analysis_seconds: float = 0.0

    def symbol_at(self, line0: int, char0: int) -> SymbolInfo | None:
        """Return the symbol whose definition or a usage contains the position."""
        for _name, sym in self.structure.symbols.items():
            def_hit = (sym.def_line0 == line0 and sym.def_start <= char0 <= sym.def_end)
            if def_hit:
                return sym
            for r in sym.usages:
                if r.start.line == line0 and r.start.character <= char0 <= r.end.character:
                    return sym
        return None

    def reference_at(self, line0: int, char0: int) -> tuple[str, Range] | None:
        for name, rng in self.structure.references:
            if rng.start.line == line0 and rng.start.character <= char0 <= rng.end.character:
                return name, rng
        return None


def _detect_table(text: str) -> str | None:
    m = CONFIG_TABLE_RE.search(text)
    if m:
        return m.group(1)
    return None


def analyze(text: str, uri: str = "", *,
            include_compile: bool = True,
            table_hint: str | None = None) -> Analysis:
    """Run the compiler pipeline and produce a full Analysis."""
    import time


    t0 = time.perf_counter()
    table_name = _detect_table(text) or table_hint or "standard"
    diagnostics: list[Diagnostic] = []

    if table_name not in VALID_TABLE_NAMES:
        # diagnostic on the #config line
        m = CONFIG_TABLE_RE.search(text)
        line0 = text[:m.start()].count("\n") if m else 0
        diagnostics.append(diag_mod.diagnostic_at_line(
            text, line0,
            f"unknown translation table {table_name!r}; valid: {', '.join(VALID_TABLE_NAMES)}",
            severity=1, code="config", data={"className": "SemanticError"}))
        table_name = "standard"

    table = helix.get_table(table_name)
    stop = helix.stop_codons_from_table(table)

    tokens: list[helix.Token] | None = None
    program: helix.Program | None = None
    chunk: helix.Chunk | None = None

    try:
        tokens = list(helix.Lexer(text).tokens())
    except helix.LexError as exc:
        diagnostics.append(diag_mod.error_to_diagnostic(exc, text, tokens=None))
        structure = ScanResult()
        return Analysis(uri=uri, text=text, table_name=table_name, tokens=None,
                        program=None, chunk=None, diagnostics=diagnostics,
                        structure=structure,
                        analysis_seconds=time.perf_counter() - t0)

    # lenient structural checks (many squiggles)
    diagnostics.extend(_structural_check(tokens, text, table_name))

    try:
        program = helix.Parser(tokens, stop_codons=stop,
                               enable_type_check=True).parse()
    except (helix.ParseError, helix.LexError) as exc:
        diagnostics.append(diag_mod.error_to_diagnostic(exc, text, tokens))
        # retry without type-check to keep a partial program for navigation
        try:
            program = helix.Parser(tokens, stop_codons=stop,
                                   enable_type_check=False).parse()
        except (helix.ParseError, helix.LexError):
            program = None

    if program is not None:
        analyzer = helix.SemanticAnalyzer(program)
        try:
            analyzer.check()
        except (helix.SemanticError, helix.RegulationError) as exc:
            diagnostics.append(diag_mod.error_to_diagnostic(exc, text, tokens))
        for warn in analyzer.warnings:
            diagnostics.append(diag_mod.warning_diagnostic(text, warn))
        if include_compile:
            try:
                compiler = helix.Compiler(table)
                chunk = compiler.compile(program)
            except helix.CompileError as exc:
                diagnostics.append(diag_mod.error_to_diagnostic(exc, text, tokens))

    structure = scan_structure(tokens or [], text, table_name)
    diagnostics = diag_mod.dedupe(diagnostics)
    return Analysis(uri=uri, text=text, table_name=table_name, tokens=tokens,
                    program=program, chunk=chunk, diagnostics=diagnostics,
                    structure=structure,
                    analysis_seconds=time.perf_counter() - t0)


# --------------------------------------------------------------------------
# Workspace (cross-file symbol index)
# --------------------------------------------------------------------------

class Workspace:
    """Symbol index across ``.helix`` files under a root directory."""

    def __init__(self, root: str | None = None):
        self.root = root
        self._index: dict[str, dict[str, SymbolInfo]] = {}  # uri -> symbols

    def scan(self, root: str | None = None) -> None:
        root = root or self.root
        if not root:
            return
        self.root = root
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                if fn.endswith(".helix"):
                    self.index_file(os.path.join(dirpath, fn))

    def index_file(self, path: str) -> None:
        from helixlang_lsp import uri as uri_mod
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            return
        ana = analyze(text, uri=uri_mod.path_to_uri(path), include_compile=False)
        self._index[ana.uri] = ana.structure.symbols

    def query(self, query: str) -> list[tuple[str, str, SymbolInfo]]:
        """Return (uri, name, symbol) matching ``query`` (case-insensitive, wildcard)."""
        q = query.lower()
        pattern = q.replace("*", ".*")
        import re as _re
        rx = _re.compile(f"^{pattern}$") if "*" in q else None
        out: list[tuple[str, str, SymbolInfo]] = []
        for uri, syms in self._index.items():
            for name, sym in syms.items():
                if rx:
                    if rx.match(name.lower()):
                        out.append((uri, name, sym))
                elif q in name.lower():
                    out.append((uri, name, sym))
        return out


__all__ = [
    "Analysis", "AnalyzeResult", "AnnotationInfo", "CodonInfo", "DnaBlock",
    "FieldInfo", "ScanResult", "SymbolInfo", "Workspace", "analyze",
    "scan_structure",
]

# mypy alias (imported by some consumers)
AnalyzeResult = Analysis
