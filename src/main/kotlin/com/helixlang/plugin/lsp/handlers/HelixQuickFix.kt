package com.helixlang.plugin.lsp.handlers

import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.intellij.codeInsight.intention.IntentionAction
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.PsiFile
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Quick-fix (doc/04 §7). Sends `textDocument/codeAction` with the diagnostic
 * context and applies the first returned `WorkspaceEdit` in a write command.
 */
class HelixQuickFixPlaceholder(
    private val className: String,
    private val diagnostic: HelixDiagnostic,
) : IntentionAction {

    override fun getFamilyName(): String = "Helix fix: $className"

    override fun getText(): String = "Helix fix: $className"

    override fun isAvailable(project: Project, editor: Editor?, file: PsiFile?): Boolean = true

    override fun invoke(project: Project, editor: Editor?, file: PsiFile?) {
        val psiFile = file ?: return
        val uri = psiFile.virtualFile?.url ?: return
        val manager = project.getService(HelixLspServerManager::class.java) ?: return
        if (!manager.isReady) return

        val params = codeActionParams(uri, diagnostic)
        com.intellij.openapi.application.ApplicationManager.getApplication()
            .executeOnPooledThread {
                val edit = try {
                    val response = manager.request(LspConstants.CODE_ACTION, params)
                        .get(1500, TimeUnit.MILLISECONDS)
                    val actions = response.getAsJsonObject("result").getAsJsonArray()
                    var first: JsonObject? = null
                    for (action in actions) {
                        if (action.isJsonObject && action.asJsonObject.has("edit")) {
                            first = action.asJsonObject
                            break
                        }
                    }
                    first?.getAsJsonObject("edit")
                } catch (_: Exception) {
                    null
                }
                if (edit == null) return@executeOnPooledThread
                com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                    if (project.isDisposed) return@invokeLater
                    applyWorkspaceEdit(project, edit)
                }
            }
    }

    private fun codeActionParams(uri: String, d: HelixDiagnostic): JsonObject {
        val params = JsonObject()
        val textDocument = JsonObject()
        textDocument.addProperty("uri", uri)
        params.add("textDocument", textDocument)
        params.add("range", range(d))
        val diagnosticObj = JsonObject().apply {
            add("range", range(d))
            addProperty("message", d.message)
            if (d.code.isNotEmpty()) addProperty("code", d.code)
            addProperty("source", "helix")
        }
        params.add("context", JsonObject().apply {
            add("diagnostics", com.google.gson.JsonArray().apply { add(diagnosticObj) })
        })
        return params
    }

    private fun range(d: HelixDiagnostic): JsonObject = JsonObject().apply {
        add("start", pos(d.line, d.startChar))
        add("end", pos(d.endLine, d.endChar))
    }

    private fun pos(line: Int, character: Int): JsonObject = JsonObject().apply {
        addProperty("line", line)
        addProperty("character", character)
    }

    private fun applyWorkspaceEdit(project: Project, edit: JsonObject) {
        val changes = edit.getAsJsonObject("changes") ?: return
        com.intellij.openapi.command.WriteCommandAction.writeCommandAction(project)
            .withName("Helix code action")
            .run<RuntimeException> {
                for ((uri, edits) in changes.entrySet()) {
                    val virtualFile: VirtualFile? = uriToFile(uri)
                    val document: Document? = virtualFile?.let {
                        FileDocumentManager.getInstance().getDocument(it)
                    }
                    if (document == null) continue
                    val editsArray = edits.asJsonArray
                    // Apply from the end so earlier offsets stay valid.
                    val applied = mutableListOf<Triple<Int, Int, String>>()
                    for (entry in editsArray) {
                        if (!entry.isJsonObject) continue
                        val editObj = entry.asJsonObject
                        val range = editObj.getAsJsonObject("range")
                        val start = range.getAsJsonObject("start")
                        val end = range.getAsJsonObject("end")
                        val startOffset = offsetAt(document, start.get("line").asInt, start.get("character").asInt)
                            ?: continue
                        val endOffset = offsetAt(document, end.get("line").asInt, end.get("character").asInt)
                            ?: continue
                        applied.add(Triple(startOffset, endOffset, editObj.get("newText")?.asString ?: ""))
                    }
                    applied.sortedByDescending { it.first }.forEach { (start, end, text) ->
                        document.replaceString(start, end, text)
                    }
                }
            }
    }

    private fun uriToFile(uri: String): VirtualFile? {
        return try {
            if (!uri.startsWith("file:")) return null
            val path = java.net.URI(uri).path
            LocalFileSystem.getInstance().findFileByIoFile(File(path))
        } catch (_: Exception) {
            null
        }
    }

    private fun offsetAt(document: Document, line: Int, character: Int): Int? {
        if (line < 0 || line >= document.lineCount) return null
        val lineStart = document.getLineStartOffset(line)
        val lineEnd = document.getLineEndOffset(line)
        return lineStart + character.coerceIn(0, lineEnd - lineStart)
    }

    override fun startInWriteAction(): Boolean = false
}

/** Registers a quick fix for a diagnostic range (used by the annotator). */
object HelixQuickFixSupport {
    fun register(registrar: com.intellij.codeInsight.daemon.QuickFixActionRegistrar, fix: HelixQuickFixPlaceholder) {
        registrar.register(fix)
    }
}
