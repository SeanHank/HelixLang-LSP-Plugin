"""``textDocument/codeAction`` — quick fixes.

Doc/03 §10.6: fix an unterminated ORF, a non-multiple-of-3 DNA length, or a
missing ``name=`` field. All edits returned as LSP ``WorkspaceEdit``s.
"""

from __future__ import annotations

import re
from typing import Any

from helixlang_lsp.analysis import Analysis
from helixlang_lsp.protocol import CodeAction, Position, Range, TextEdit, WorkspaceEdit

_FIX_ORF = "helix.fix.unterminatedOrf"
_FIX_LENGTH = "helix.fix.dnaLength"
_FIX_NAME = "helix.fix.addName"


def code_actions(text: str, analysis: Analysis,
                 params: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle ``textDocument/codeAction``."""
    context = params.get("context", {}) or {}
    only = context.get("only", []) or []
    diags = context.get("diagnostics", []) or []
    if only and "quickfix" not in only:
        return []

    out: list[CodeAction] = []
    for d in diags:
        code = d.get("code")
        message = d.get("message", "")
        rng = Range.from_dict(d.get("range", {"start": {"line": 0, "character": 0},
                                              "end": {"line": 0, "character": 0}}))
        if code == "parse" and "ORF not terminated" in message:
            action = _action_orf(text, rng, analysis.uri)
            if action:
                out.append(action)
        elif code == "lex" and "not multiple of 3" in message:
            action = _action_length(text, rng, analysis.uri)
            if action:
                out.append(action)
        elif code == "parse" and "missing name=" in message:
            action = _action_name(text, rng, analysis.uri)
            if action:
                out.append(action)
    return [a.to_dict() for a in out]


def _action_orf(text: str, rng: Range, uri: str) -> CodeAction | None:
    lines = text.split("\n")
    end_line = min(rng.end.line, len(lines) - 1)
    line_text = lines[end_line]
    edit = TextEdit(
        range=Range(start=Position(line=end_line, character=len(line_text)),
                    end=Position(line=end_line, character=len(line_text))),
        new_text="TAA",
    )
    return CodeAction(
        title="Append TAA to terminate ORF",
        kind="quickfix",
        edit=WorkspaceEdit(changes={uri: [edit]}),
    )


def _action_length(text: str, rng: Range, uri: str) -> CodeAction | None:
    lines = text.split("\n")
    line0 = min(rng.start.line, len(lines) - 1)
    groups = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r"[ATCG]{3,}", lines[line0])]
    if not groups:
        return None
    # the offending run is one whose length is not a multiple of 3
    target = next(((s, e, seq) for s, e, seq in groups if len(seq) % 3), groups[0])
    s, e, seq = target
    excess = len(seq) % 3
    start = s + len(seq) - excess
    edit = TextEdit(
        range=Range(start=Position(line=line0, character=start),
                    end=Position(line=line0, character=e)),
        new_text="",
    )
    return CodeAction(
        title=f"Remove trailing {excess} base(s) to make DNA length a multiple of 3",
        kind="quickfix",
        edit=WorkspaceEdit(changes={uri: [edit]}),
    )


def _action_name(text: str, rng: Range, uri: str) -> CodeAction | None:
    line0 = min(rng.start.line, text.count("\n"))
    edit = TextEdit(
        range=Range(start=Position(line=line0, character=0),
                    end=Position(line=line0, character=0)),
        new_text="name=UNNAMED ",
    )
    return CodeAction(
        title="Insert missing name= field",
        kind="quickfix",
        edit=WorkspaceEdit(changes={uri: [edit]}),
    )
