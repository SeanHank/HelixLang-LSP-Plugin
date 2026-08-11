"""Map ``helixlang`` errors and warnings to LSP ``Diagnostic`` objects.

Range selection follows doc/03 §6.2:

1. If ``line == 0`` and the message references a codon, use the codon's
   ``CODON`` token span (via the lexer tokens passed in).
2. Else if ``col > 0``, use a single-character range at ``(line-1, col-1)``.
3. Else use the first non-whitespace token on the line; fall back to the whole
   line.
4. ``ParseError`` for ORF handling ("no START codon", "ORF not terminated")
   spans the gene's ``#gene`` line to its ``#end`` line (or EOF).
"""

from __future__ import annotations

import re
from typing import Any

from helixlang_lsp import _helix_contract as helix
from helixlang_lsp import positions as pos
from helixlang_lsp.protocol import Diagnostic, DiagnosticRelatedInformation, Location, Range

SEVERITY_ERROR = 1
SEVERITY_WARNING = 2

_ORF_MARKERS = ("no START codon", "ORF not terminated", "not terminated")

# §8.1 error class -> (severity, code)
_CLASS_MAP: tuple[tuple[type, int, str], ...] = (
    (helix.LexError, SEVERITY_ERROR, "lex"),
    (helix.ParseError, SEVERITY_ERROR, "parse"),
    (helix.SemanticError, SEVERITY_ERROR, "semantic"),
    (helix.RegulationError, SEVERITY_ERROR, "regulation"),
    (helix.CompileError, SEVERITY_ERROR, "compile"),
    (helix.RuntimeHelixError, SEVERITY_ERROR, "runtime"),
    (helix.BioError, SEVERITY_ERROR, "bio"),
)


def error_class(exc: BaseException) -> tuple[type, int, str]:
    """Return the mapped ``(cls, severity, code)`` for an exception."""
    for cls, severity, code in _CLASS_MAP:
        if isinstance(exc, cls):
            return cls, severity, code
    return type(exc), SEVERITY_ERROR, "error"


def error_to_diagnostic(exc: BaseException, text: str,
                        tokens: list[helix.Token] | None) -> Diagnostic:
    """Convert a compiler ``HelixError`` into an LSP ``Diagnostic``."""
    cls, severity, code = error_class(exc)
    line = int(getattr(exc, "line", 0) or 0)
    col = int(getattr(exc, "col", 0) or 0)
    codon_index = int(getattr(exc, "codon_index", -1) or -1)
    msg = str(exc)

    rng = _resolve_range(text, tokens, line, col, codon_index, msg,
                         _is_orf_span(line, col, msg))

    data: dict[str, Any] = {"className": cls.__name__}
    if codon_index >= 0:
        data["codonIndex"] = codon_index

    diag = Diagnostic(
        range=rng,
        message=msg,
        severity=severity,
        code=code,
        source="helix",
        data=data,
    )

    related = _related_for_compile(exc, text, tokens)
    if related:
        diag.related_information = related
    return diag


def errors_to_diagnostics(exc: BaseException, text: str,
                          tokens: list[helix.Token] | None) -> list[Diagnostic]:
    """Map one or a collection of errors to diagnostics (doc/03 §12)."""
    if isinstance(exc, (list, tuple)):
        return [error_to_diagnostic(e, text, tokens) for e in exc]
    return [error_to_diagnostic(exc, text, tokens)]


def diagnostic_at_line(text: str, line0: int, message: str, *,
                       severity: int = SEVERITY_ERROR,
                       code: str | int | None = None,
                       data: dict[str, Any] | None = None,
                       source: str = "helix") -> Diagnostic:
    """Build a diagnostic positioned on ``line0`` (0-based)."""
    lines = text.split("\n")
    if 0 <= line0 < len(lines):
        stripped = lines[line0].lstrip()
        col0 = len(lines[line0]) - len(stripped)
        length = len(stripped) if stripped else len(lines[line0])
    else:
        col0, length = 0, 0
    return Diagnostic(
        range=pos.token_span_to_range(text, line0 + 1, col0 + 1, length),
        message=message,
        severity=severity,
        code=code,
        source=source,
        data=data,
    )


_WARNING_SYMBOL_RE = re.compile(r"['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]")


def warning_diagnostic(text: str, message: str) -> Diagnostic:
    """Turn a ``SemanticAnalyzer`` warning string into a Warning diagnostic."""
    line0 = 0
    m = _WARNING_SYMBOL_RE.search(message)
    if m:
        name = m.group(1)
        # find the first line mentioning the symbol
        lines = text.split("\n")
        for i, ln in enumerate(lines):
            if name in ln:
                line0 = i
                break
    return diagnostic_at_line(text, line0, message, severity=SEVERITY_WARNING,
                              code="warning")


def dedupe(diagnostics: list[Diagnostic]) -> list[Diagnostic]:
    """Remove duplicate diagnostics (same message+range+code), preserving order."""
    seen: set[tuple[str, str, str]] = set()
    out: list[Diagnostic] = []
    for d in diagnostics:
        key = (
            d.message,
            f"{d.range.start.line}:{d.range.start.character}",
            str(d.code),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(d)
    return out


# --------------------------------------------------------------------------
# Range resolution helpers
# --------------------------------------------------------------------------

def _resolve_range(text: str, tokens: list[helix.Token] | None, line: int,
                   col: int, codon_index: int, msg: str,
                   orf_span: bool) -> Range:
    if orf_span and tokens is not None:
        return _orf_range(text, tokens)
    if line <= 0 and tokens is not None:
        codon_rng = _codon_range_for_msg(tokens, text, msg)
        if codon_rng is not None:
            return codon_rng
        codon_rng = _codon_range_for_index(tokens, text, codon_index)
        if codon_rng is not None:
            return codon_rng
    if col > 0:
        return pos.token_span_to_range(text, max(line, 1), max(col, 1), 1)
    return _first_token_or_line(text, tokens, max(line - 1, 0))


def _is_orf_span(line: int, col: int, msg: str) -> bool:
    if line <= 0:
        return any(m in msg for m in _ORF_MARKERS)
    return False


def _orf_range(text: str, tokens: list[helix.Token]) -> Range:
    """Span from the nearest ``#gene`` line to its ``#end`` (or EOF)."""
    start_line0 = 0
    end_line0 = text.count("\n")
    for tok in tokens:
        if tok.kind == "ANNOT_START" and tok.value == "gene":
            start_line0 = tok.line - 1
        elif tok.kind == "ANNOT_END":
            end_line0 = tok.line - 1
    return Range(
        start=pos.linecol_to_position(text, start_line0 + 1, 1),
        end=pos.linecol_to_position(text, end_line0 + 1,
                                    1 + _line_length(text, end_line0)),
    )


def _line_length(text: str, line0: int) -> int:
    lines = text.split("\n")
    if 0 <= line0 < len(lines):
        return len(lines[line0])
    return 0


def _codon_range_for_msg(tokens: list[helix.Token], text: str,
                         msg: str) -> Range | None:
    """Find a CODON token whose bases appear in ``msg``."""
    m = re.search(r"\b([ATCG]{3})\b", msg)
    if not m:
        return None
    seq = m.group(1)
    for tok in tokens:
        if tok.kind == "CODON" and tok.value == seq:
            return pos.token_span_to_range(text, tok.line, tok.col, 3)
    return None


def _codon_range_for_index(tokens: list[helix.Token], text: str,
                           codon_index: int) -> Range | None:
    n = 0
    for tok in tokens:
        if tok.kind == "CODON":
            if n == codon_index:
                return pos.token_span_to_range(text, tok.line, tok.col, 3)
            n += 1
    return None


def _first_token_or_line(text: str, tokens: list[helix.Token] | None,
                         line0: int) -> Range:
    if tokens is not None:
        for tok in tokens:
            if tok.kind not in ("NEWLINE", "EOF") and tok.line - 1 >= line0:
                return pos.token_span_to_range(
                    text, tok.line, tok.col, max(len(tok.value), 1))
    return pos.whole_line_range(text, line0)


def _related_for_compile(
    exc: BaseException, text: str, tokens: list[helix.Token] | None
) -> list[DiagnosticRelatedInformation] | None:
    """CompileError about an undefined CALL_GENE target: link caller to target."""
    if not isinstance(exc, helix.CompileError) or tokens is None:
        return None
    m = re.search(r"[Cc][Aa][Ll][Ll]_[Gg][Ee][Nn][Ee].{0,30}['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]",
                  str(exc))
    if not m:
        return None
    name = m.group(1)
    for tok in tokens:
        if tok.kind == "FIELD" and f"name={name}" in tok.value:
            rng = pos.token_span_to_range(text, tok.line, tok.col, len(tok.value))
            return [DiagnosticRelatedInformation(
                location=Location(uri="", range=rng),
                message=f"target {name!r} defined here",
            )]
    return None
