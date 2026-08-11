"""Pure LSP feature functions over ``(text, analysis, params)``.

Every handler is a pure function so it can be unit-tested without the
transport (doc/03 §12). The module name maps to the LSP method:
``hover`` -> ``textDocument/hover``, etc.
"""
