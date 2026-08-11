package com.helixlang.plugin.lsp.handlers

import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.intellij.openapi.Disposable
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.editor.Inlay
import com.intellij.openapi.editor.event.DocumentListener
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.Disposer
import com.intellij.util.messages.MessageBusConnection
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.TimeUnit

/**
 * Inlay hints (doc/04 §5.9). Sends `textDocument/inlayHint` on editor open and
 * after each edit, and renders each hint as an inline element showing the
 * decoded opcode name. Stale inlays are disposed before each refresh.
 */
class HelixInlayHintsController(private val project: Project) : DocumentListener, Disposable {

    private data class EditorInlays(var stamp: Long = -1, val inlays: MutableList<Inlay<*>> = mutableListOf())

    private val byEditor = ConcurrentHashMap<Editor, EditorInlays>()

    fun attach(editor: Editor) {
        if (editor.project != null && editor.project != project) return
        val file = FileDocumentManager.getInstance().getFile(editor.document) ?: return
        if (file.fileType !is com.helixlang.plugin.filetype.HelixFileType) return
        byEditor.putIfAbsent(editor, EditorInlays())
        refresh(editor, force = true)
    }

    fun detach(editor: Editor) {
        disposeEditor(editor)
    }

    override fun beforeDocumentChange(event: com.intellij.openapi.editor.event.DocumentEvent) {
        // no-op; refresh happens after the change
    }

    override fun documentChanged(event: com.intellij.openapi.editor.event.DocumentEvent) {
        val editor = byEditor.keys.firstOrNull { it.document === event.document } ?: return
        refresh(editor, force = false)
    }

    override fun dispose() {
        byEditor.keys.toList().forEach { disposeEditor(it) }
        byEditor.clear()
    }

    private fun disposeEditor(editor: Editor) {
        byEditor.remove(editor)?.let { holder ->
            holder.inlays.forEach { Disposer.dispose(it) }
            holder.inlays.clear()
        }
    }

    private fun refresh(editor: Editor, force: Boolean) {
        val manager = project.getService(HelixLspServerManager::class.java) ?: return
        val holder = byEditor[editor] ?: return
        val document = editor.document
        if (!force && document.modificationStamp == holder.stamp) return
        holder.stamp = document.modificationStamp
        holder.inlays.forEach { Disposer.dispose(it) }
        holder.inlays.clear()
        if (!com.helixlang.plugin.settings.HelixSettings.getInstance().inlayHintsEnabled) return
        if (!manager.isReady) return
        val file = FileDocumentManager.getInstance().getFile(document) ?: return
        val uri = file.url
        try {
            val future = manager.request(
                LspConstants.INLAY_HINT,
                LspMessages.requestFull(LspConstants.INLAY_HINT, uri),
            )
            val response = future.get(1500, TimeUnit.MILLISECONDS)
            val hints = response.getAsJsonObject("result").getAsJsonArray()
            val max = document.textLength
            for (hint in hints) {
                if (!hint.isJsonObject) continue
                val obj = hint.asJsonObject
                val pos = obj.getAsJsonObject("position")
                val line = pos.get("line").asInt
                val character = pos.get("character").asInt
                val label = obj.get("label")?.asString ?: continue
                val offset = offsetAt(document, line, character) ?: continue
                if (offset < 0 || offset > max) continue
                val inlay = editor.inlayModel.addInlineElement(offset, true, LabelRenderer(label)) ?: continue
                holder.inlays.add(inlay)
            }
        } catch (_: Exception) {
            // server not reachable or timed out; drop hints quietly
        }
    }

    private fun offsetAt(document: Document, line: Int, character: Int): Int? {
        if (line < 0 || line >= document.lineCount) return null
        val lineStart = document.getLineStartOffset(line)
        val lineEnd = document.getLineEndOffset(line)
        return lineStart + character.coerceIn(0, lineEnd - lineStart)
    }

    companion object {
        @JvmStatic
        fun getInstance(project: Project): HelixInlayHintsController =
            project.getService(HelixInlayHintsController::class.java)
    }
}

/** Renders the inline "opcode" label for an inlay hint. */
class LabelRenderer(private val text: String) : com.intellij.openapi.editor.EditorCustomElementRenderer {
    override fun calcWidthInPixels(inlay: Inlay<*>): Int {
        val metrics = inlay.editor.contentComponent.getFontMetrics(inlay.editor.contentComponent.font)
        return metrics.stringWidth(text) + 8
    }

    override fun paint(inlay: Inlay<*>, g: java.awt.Graphics, targetRegion: java.awt.Rectangle,
                       textAttributes: com.intellij.openapi.editor.markup.TextAttributes) {
        g.color = textAttributes.foregroundColor ?: java.awt.Color(128, 128, 128)
        g.font = inlay.editor.contentComponent.font.deriveFont(java.awt.Font.ITALIC)
        val baseline = targetRegion.y + g.fontMetrics.ascent
        g.drawString(text, targetRegion.x + 2, baseline)
    }
}
