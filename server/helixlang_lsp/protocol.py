"""LSP protocol types (subset used by the server).

Dataclasses with ``to_dict`` serialization to plain JSON. Only the shapes the
server produces/consumes are modelled.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------- Primitive types ----------

@dataclass(slots=True)
class Position:
    line: int  # 0-based
    character: int  # 0-based UTF-16 code units

    def to_dict(self) -> dict[str, int]:
        return {"line": self.line, "character": self.character}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Position:
        return cls(line=int(d["line"]), character=int(d["character"]))


@dataclass(slots=True)
class Range:
    start: Position
    end: Position

    def to_dict(self) -> dict[str, dict[str, int]]:
        return {"start": self.start.to_dict(), "end": self.end.to_dict()}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Range:
        return cls(start=Position.from_dict(d["start"]), end=Position.from_dict(d["end"]))


@dataclass(slots=True)
class Location:
    uri: str
    range: Range

    def to_dict(self) -> dict[str, Any]:
        return {"uri": self.uri, "range": self.range.to_dict()}


@dataclass(slots=True)
class MarkupContent:
    kind: str = "markdown"
    value: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"kind": self.kind, "value": self.value}


# ---------- Diagnostics ----------

@dataclass(slots=True)
class DiagnosticRelatedInformation:
    location: Location
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"location": self.location.to_dict(), "message": self.message}


@dataclass(slots=True)
class Diagnostic:
    range: Range
    message: str
    severity: int | None = None  # 1=Error 2=Warning 3=Information 4=Hint
    code: str | int | None = None
    source: str = "helix"
    related_information: list[DiagnosticRelatedInformation] | None = None
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "range": self.range.to_dict(),
            "message": self.message,
            "source": self.source,
        }
        if self.severity is not None:
            out["severity"] = self.severity
        if self.code is not None:
            out["code"] = self.code
        if self.related_information is not None:
            out["relatedInformation"] = [r.to_dict() for r in self.related_information]
        if self.data is not None:
            out["data"] = self.data
        return out


# ---------- Hover ----------

@dataclass(slots=True)
class Hover:
    contents: MarkupContent
    range: Range | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"contents": self.contents.to_dict()}
        if self.range is not None:
            out["range"] = self.range.to_dict()
        return out


# ---------- Completion ----------

@dataclass(slots=True)
class TextEdit:
    range: Range
    new_text: str

    def to_dict(self) -> dict[str, Any]:
        return {"range": self.range.to_dict(), "newText": self.new_text}


@dataclass(slots=True)
class CompletionItem:
    label: str
    kind: int | None = None
    detail: str | None = None
    documentation: str | MarkupContent | None = None
    insert_text: str | None = None
    sort_text: str | None = None
    text_edit: TextEdit | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"label": self.label}
        if self.kind is not None:
            out["kind"] = self.kind
        if self.detail is not None:
            out["detail"] = self.detail
        if self.documentation is not None:
            out["documentation"] = (
                self.documentation.to_dict()
                if isinstance(self.documentation, MarkupContent)
                else self.documentation
            )
        if self.insert_text is not None:
            out["insertText"] = self.insert_text
        if self.sort_text is not None:
            out["sortText"] = self.sort_text
        if self.text_edit is not None:
            out["textEdit"] = self.text_edit.to_dict()
        return out


@dataclass(slots=True)
class CompletionList:
    is_incomplete: bool
    items: list[CompletionItem]

    def to_dict(self) -> dict[str, Any]:
        return {"isIncomplete": self.is_incomplete, "items": [i.to_dict() for i in self.items]}


# Completion item kinds (LSP)
CompletionKind = {
    "text": 1, "method": 2, "function": 3, "constructor": 4, "field": 5,
    "variable": 6, "class": 7, "interface": 8, "module": 9, "property": 10,
    "unit": 11, "value": 12, "enum": 13, "keyword": 14, "snippet": 15,
    "color": 16, "file": 17, "reference": 18, "folder": 19, "enum_member": 20,
    "constant": 21, "struct": 22, "event": 23, "operator": 24, "type_parameter": 25,
}


# ---------- Symbols ----------

@dataclass(slots=True)
class DocumentSymbol:
    name: str
    detail: str | None
    kind: int
    range: Range
    selection_range: Range
    children: list[DocumentSymbol] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "range": self.range.to_dict(),
            "selectionRange": self.selection_range.to_dict(),
        }
        if self.detail is not None:
            out["detail"] = self.detail
        if self.children:
            out["children"] = [c.to_dict() for c in self.children]
        return out


@dataclass(slots=True)
class SymbolInformation:
    name: str
    kind: int
    location: Location
    container_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "location": self.location.to_dict(),
        }
        if self.container_name is not None:
            out["containerName"] = self.container_name
        return out


SymbolKind = {
    "file": 1, "module": 2, "namespace": 3, "package": 4, "class": 5,
    "method": 6, "property": 7, "field": 8, "constructor": 9, "enum": 10,
    "interface": 11, "function": 12, "variable": 13, "constant": 14,
    "string": 15, "number": 16, "boolean": 17, "array": 18, "object": 19,
    "key": 20, "null": 21, "enum_member": 22, "struct": 23, "event": 24,
    "operator": 25, "type_parameter": 26,
}


# ---------- Folding ----------

@dataclass(slots=True)
class FoldingRange:
    start_line: int  # 0-based
    end_line: int  # 0-based, inclusive
    start_character: int | None = None
    end_character: int | None = None
    kind: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"startLine": self.start_line, "endLine": self.end_line}
        if self.start_character is not None:
            out["startCharacter"] = self.start_character
        if self.end_character is not None:
            out["endCharacter"] = self.end_character
        if self.kind is not None:
            out["kind"] = self.kind
        return out


# ---------- Semantic tokens ----------

TOKEN_TYPES = ["keyword", "type", "function", "variable", "number", "string",
               "comment", "operator", "arrow"]
TOKEN_MODIFIERS = ["declaration", "defaultLibrary"]

TOKEN_TYPE_INDEX = {name: i for i, name in enumerate(TOKEN_TYPES)}
TOKEN_MODIFIER_INDEX = {name: i for i, name in enumerate(TOKEN_MODIFIERS)}


def encode_semantic_tokens(tokens: list[tuple[int, int, int, int, int]]) -> list[int]:
    """Encode absolute tokens to LSP relative delta form.

    Each token: (deltaLine, deltaStart, length, tokenType, tokenModifiersBits).
    """
    result: list[int] = []
    prev_line = 0
    prev_start = 0
    for line, start, length, type_idx, mods in tokens:
        if line == prev_line:
            delta_line = 0
            delta_start = start - prev_start
        else:
            delta_line = line - prev_line
            delta_start = start
        result.extend([delta_line, delta_start, length, type_idx, mods])
        prev_line = line
        prev_start = start
    return result


@dataclass(slots=True)
class SemanticTokens:
    data: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {"data": self.data}


# ---------- Code actions / edits ----------

@dataclass(slots=True)
class WorkspaceEdit:
    changes: dict[str, list[TextEdit]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"changes": {uri: [e.to_dict() for e in edits]
                            for uri, edits in self.changes.items()}}


@dataclass(slots=True)
class CodeAction:
    title: str
    kind: str | None = None
    edit: WorkspaceEdit | None = None
    command: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"title": self.title}
        if self.kind is not None:
            out["kind"] = self.kind
        if self.edit is not None:
            out["edit"] = self.edit.to_dict()
        if self.command is not None:
            out["command"] = self.command
        return out


# ---------- Inlay hints ----------

@dataclass(slots=True)
class InlayHint:
    position: Position
    label: str
    kind: int | None = None  # 1=Type 2=Parameter
    padding_right: bool | None = None
    tooltip: str | None = None
    data: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"position": self.position.to_dict(), "label": self.label}
        if self.kind is not None:
            out["kind"] = self.kind
        if self.padding_right is not None:
            out["paddingRight"] = self.padding_right
        if self.tooltip is not None:
            out["tooltip"] = self.tooltip
        if self.data is not None:
            out["data"] = self.data
        return out


# ---------- LocationLink ----------

@dataclass(slots=True)
class LocationLink:
    target_uri: str
    target_range: Range
    target_selection_range: Range
    origin_selection_range: Range | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "targetUri": self.target_uri,
            "targetRange": self.target_range.to_dict(),
            "targetSelectionRange": self.target_selection_range.to_dict(),
        }
        if self.origin_selection_range is not None:
            out["originSelectionRange"] = self.origin_selection_range.to_dict()
        return out
