package com.helixlang.plugin.lsp.handlers

import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.intellij.codeInsight.hint.HintManager
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import java.awt.event.MouseEvent
import java.awt.event.MouseListener
import java.awt.event.MouseMotionListener
import java.util.concurrent.atomic.AtomicBoolean

/**
 * Hover tooltip (doc/04 §5.4). Sends `textDocument/hover` on a mouse move over
 * a `.helix` editor and shows the markdown answer via [HintManager]. At most one
 * in-flight request per editor; the hint is dismissed on the next event.
 */
class HelixHoverController(private val project: Project) : MouseMotionListener, MouseListener {

    private val inFlight = AtomicBoolean(false)

    override fun mouseMoved(e: MouseEvent) {
        val editor = editorOf(e) ?: return
        if (!inFlight.compareAndSet(false, true)) return
        val file = FileDocumentManager.getInstance().getFile(editor.document) ?: run {
            inFlight.set(false)
            return
        }
        if (file.fileType !is com.helixlang.plugin.filetype.HelixFileType) {
            inFlight.set(false)
            return
        }
        val document = editor.document
        val logical = editor.xyToLogicalPosition(e.point)
        val offset = editor.logicalPositionToOffset(logical)
        if (offset < 0 || offset > document.textLength) {
            inFlight.set(false)
            return
        }
        val line = document.getLineNumber(offset)
        val character = offset - document.getLineStartOffset(line)
        val manager = project.getService(HelixLspServerManager::class.java) ?: run {
            inFlight.set(false)
            return
        }
        if (!manager.isReady) {
            inFlight.set(false)
            return
        }
        manager.request(
            LspConstants.HOVER,
            LspMessages.requestPosition(LspConstants.HOVER, file.url, line, character),
        ).whenComplete { response: JsonObject?, throwable: Throwable? ->
            inFlight.set(false)
            if (throwable != null || response == null) return@whenComplete
            val result = try {
                response.getAsJsonObject("result")
            } catch (_: Exception) {
                null
            }
            val contents = result?.get("contents") ?: return@whenComplete
            val text = when {
                contents.isJsonObject && contents.asJsonObject.has("value") ->
                    contents.asJsonObject.get("value").asString
                contents.isJsonPrimitive -> contents.asString
                else -> return@whenComplete
            }
            com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                if (!editor.isDisposed) {
                    val flags = (HintManager.HIDE_BY_ANY_KEY or
                        HintManager.HIDE_BY_TEXT_CHANGE or
                        HintManager.HIDE_BY_OTHER_HINT or
                        HintManager.HIDE_IF_OUT_OF_EDITOR).toShort()
                    HintManager.getInstance().showInformationHint(
                        editor, markupToHtml(text), flags)
                }
            }
        }
    }

    override fun mouseExited(e: MouseEvent) {
        inFlight.set(false)
    }

    override fun mouseDragged(e: MouseEvent) {
        inFlight.set(false)
    }

    override fun mousePressed(e: MouseEvent) {
        inFlight.set(false)
    }

    override fun mouseReleased(e: MouseEvent) {}
    override fun mouseClicked(e: MouseEvent) {}
    override fun mouseEntered(e: MouseEvent) {}

    private fun editorOf(e: MouseEvent): Editor? {
        var component: java.awt.Component? = e.component
        while (component != null) {
            if (component is Editor) return component
            component = component.parent
        }
        return null
    }

    companion object {
        /** Minimal markdown→HTML used for tooltips (code, bold, line breaks). */
        fun markupToHtml(markdown: String): String {
            var html = markdown
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            html = html
                .replace(Regex("`([^`]+)`")) { "<code>${it.groupValues[1]}</code>" }
                .replace(Regex("\\*\\*(.+?)\\*\\*")) { "<b>${it.groupValues[1]}</b>" }
                .replace("\n", "<br>")
            return "<html>$html</html>"
        }
    }
}
