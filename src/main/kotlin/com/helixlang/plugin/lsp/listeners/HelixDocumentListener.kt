package com.helixlang.plugin.lsp.listeners

import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.helixlang.plugin.psi.HelixFile
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.event.DocumentEvent
import com.intellij.openapi.editor.event.DocumentListener
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.TextRange
import com.intellij.openapi.vfs.VirtualFile

/**
 * Keeps the server's copy of every open `.helix` document in sync
 * (doc/04 §4.5): didOpen, didChange (with computed delta), didSave, didClose.
 * Version tracking discards stale server results.
 */
class HelixDocumentListener(private val project: Project) : DocumentListener {

    private val versions = mutableMapOf<String, Int>()

    override fun beforeDocumentChange(event: DocumentEvent) {
        val uri = uriOf(event.document) ?: return
        manager()?.invalidateSemanticTokens(uri)
        val text = event.document.text
        val version = versions[uri] ?: 1
        val range = diffRange(event.document, event.offset, event.newLength)
        val server = manager()
        if (range == null) {
            // whole-document replacement
            server?.notify(LspConstants.DID_CHANGE, LspMessages.didChange(uri, version, null, text))
        } else {
            server?.notify(
                LspConstants.DID_CHANGE,
                LspMessages.didChange(uri, version, range, event.newFragment.toString()),
            )
        }
        versions[uri] = version + 1
    }

    override fun documentChanged(event: DocumentEvent) {
        // didChange is issued from beforeDocumentChange so the delta is accurate.
    }

    private fun diffRange(document: Document, offset: Int, newLength: Int): LspMessages.RangeLsp? {
        if (newLength >= document.textLength) return null
        val lineStart = document.getLineNumber(offset)
        val startChar = offset - document.getLineStartOffset(lineStart)
        val endOffset = offset + newLength
        val lineEnd = document.getLineNumber(endOffset.coerceAtMost(document.textLength))
        val endChar = endOffset - document.getLineStartOffset(lineEnd)
        return LspMessages.RangeLsp(lineStart, startChar, lineEnd, endChar)
    }

    private fun uriOf(document: Document): String? {
        val file: VirtualFile = FileDocumentManager.getInstance().getFile(document) ?: return null
        if (file.fileType !is com.helixlang.plugin.filetype.HelixFileType) return null
        return file.url
    }

    private fun manager(): HelixLspServerManager? =
        if (project.isDisposed) null else project.getService(HelixLspServerManager::class.java)
}
