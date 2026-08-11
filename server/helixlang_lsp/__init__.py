"""helixlang_lsp: Language Server Protocol server for the HelixLang DSL.

A thin, testable wrapper that translates editor events (LSP) into calls to the
HelixLang compiler (``src/helixlang``) and compiler results into LSP messages.
It adds no language semantics of its own.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
