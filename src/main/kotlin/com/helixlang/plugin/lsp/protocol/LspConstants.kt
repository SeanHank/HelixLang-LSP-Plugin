package com.helixlang.plugin.lsp.protocol

/** LSP JSON-RPC method names used by the client. */
object LspConstants {
    const val INITIALIZE = "initialize"
    const val INITIALIZED = "initialized"
    const val SHUTDOWN = "shutdown"
    const val EXIT = "exit"

    const val DID_OPEN = "textDocument/didOpen"
    const val DID_CHANGE = "textDocument/didChange"
    const val DID_SAVE = "textDocument/didSave"
    const val DID_CLOSE = "textDocument/didClose"

    const val HOVER = "textDocument/hover"
    const val COMPLETION = "textDocument/completion"
    const val DEFINITION = "textDocument/definition"
    const val REFERENCES = "textDocument/references"
    const val DOCUMENT_SYMBOL = "textDocument/documentSymbol"
    const val FOLDING_RANGE = "textDocument/foldingRange"
    const val SEMANTIC_TOKENS = "textDocument/semanticTokens/full"
    const val CODE_ACTION = "textDocument/codeAction"
    const val INLAY_HINT = "textDocument/inlayHint"
    const val FORMATTING = "textDocument/formatting"

    const val PUBLISH_DIAGNOSTICS = "textDocument/publishDiagnostics"
    const val WORKSPACE_SYMBOL = "workspace/symbol"
    const val WORKSPACE_EXECUTE_COMMAND = "workspace/executeCommand"
    const val WINDOW_LOG_MESSAGE = "window/logMessage"
    const val CANCEL_REQUEST = "\$/cancelRequest"

    const val HELIX_DISASSEMBLE = "helix.disassemble"
}
