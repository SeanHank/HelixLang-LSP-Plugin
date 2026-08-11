package com.helixlang.plugin.lsp.handlers

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.HelixLspServerManager
import com.intellij.lang.annotation.AnnotationHolder
import com.intellij.lang.annotation.ExternalAnnotator
import com.intellij.lang.annotation.HighlightSeverity
import com.intellij.openapi.editor.Document
import com.intellij.openapi.project.Project
import com.intellij.openapi.util.TextRange
import com.intellij.psi.PsiFile

/** One cached server diagnostic, decoded from the publishDiagnostics payload. */
data class HelixDiagnostic(
    val line: Int,
    val startChar: Int,
    val endLine: Int,
    val endChar: Int,
    val severity: HighlightSeverity,
    val message: String,
    val code: String,
    val className: String?,
)

/**
 * Diagnostics annotator (doc/04 §5.1). Reads the client-side diagnostics cache
 * populated from `textDocument/publishDiagnostics`; never calls the server
 * during a highlight pass. When the server is offline no annotations are
 * produced (graceful degradation).
 */
class HelixDiagnosticsAnnotator : ExternalAnnotator<String?, List<HelixDiagnostic>>() {

    override fun collectInformation(file: PsiFile): String? = file.virtualFile?.url

    override fun doAnnotate(uri: String?): List<HelixDiagnostic>? {
        if (uri == null) return null
        val virtualFile = com.intellij.openapi.vfs.VirtualFileManager.getInstance()
            .findFileByUrl(uri) ?: return null
        val project = com.intellij.openapi.project.ProjectLocator.getInstance()
            .guessProjectForFile(virtualFile) ?: return null
        val manager = project.getService(HelixLspServerManager::class.java) ?: return null
        val array: JsonArray = manager.diagnosticsCache[uri] ?: return emptyList()
        return decode(array)
    }

    override fun apply(file: PsiFile, annotationResult: List<HelixDiagnostic>?, holder: AnnotationHolder) {
        val result = annotationResult ?: return
        val document: Document = com.intellij.openapi.fileEditor.FileDocumentManager
            .getInstance().getDocument(file.virtualFile) ?: return
        for (d in result) {
            val startOffset = offsetAt(document, d.line, d.startChar)
            val endOffset = offsetAt(document, d.endLine, d.endChar)
            val range = TextRange(startOffset, endOffset.coerceAtLeast(startOffset + 1))
            val annotation = holder
                .newAnnotation(d.severity, d.message)
                .range(range)
                .tooltip(message(d))
            d.className?.let { annotation.withFix(HelixQuickFixPlaceholder(it, d)) }
            annotation.create()
        }
    }

    private fun decode(array: JsonArray): List<HelixDiagnostic> {
        val out = mutableListOf<HelixDiagnostic>()
        for (element in array) {
            if (!element.isJsonObject) continue
            val obj = element.asJsonObject
            val range = obj.getAsJsonObject("range")
            val start = range.getAsJsonObject("start")
            val end = range.getAsJsonObject("end")
            val severity = severityOf(obj.get("severity")?.asInt ?: 1)
            val dataClass = runCatching {
                obj.getAsJsonObject("data")?.get("className")?.asString
            }.getOrNull()
            out.add(
                HelixDiagnostic(
                    line = start.get("line").asInt,
                    startChar = start.get("character").asInt,
                    endLine = end.get("line").asInt,
                    endChar = end.get("character").asInt,
                    severity = severity,
                    message = obj.get("message")?.asString ?: "",
                    code = obj.get("code")?.asString ?: "",
                    className = dataClass,
                ))
        }
        return out
    }

    private fun severityOf(severity: Int): HighlightSeverity = when (severity) {
        1 -> HighlightSeverity.ERROR
        2 -> HighlightSeverity.WARNING
        else -> HighlightSeverity.INFO
    }

    private fun message(d: HelixDiagnostic): String {
        val codePart = if (d.code.isNotEmpty()) " [${d.code}]" else ""
        return d.message + codePart
    }

    private fun offsetAt(document: Document, line: Int, character: Int): Int {
        if (line >= document.lineCount) return document.textLength
        val lineStart = document.getLineStartOffset(line)
        return lineStart + character.coerceAtMost(document.getLineEndOffset(line) - lineStart)
    }
}
