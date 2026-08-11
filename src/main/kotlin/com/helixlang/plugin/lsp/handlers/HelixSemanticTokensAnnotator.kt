package com.helixlang.plugin.lsp.handlers

import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.helixlang.plugin.settings.HelixSettings
import com.intellij.lang.annotation.AnnotationHolder
import com.intellij.lang.annotation.ExternalAnnotator
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.editor.DefaultLanguageHighlighterColors
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.project.ProjectLocator
import com.intellij.openapi.util.Computable
import com.intellij.openapi.util.TextRange
import com.intellij.openapi.vfs.VirtualFileManager
import com.intellij.psi.PsiFile

/**
 * Semantic-token highlighting (doc/04 §5.2 layer 2). Sends
 * `textDocument/semanticTokens/full` on a stale cache, decodes the relative
 * delta encoding, and layers the resulting ranges over the lexical pass.
 */
class HelixSemanticTokensAnnotator : ExternalAnnotator<String?, List<HelixSemanticRange>>(), DumbAware {

    override fun collectInformation(file: PsiFile): String? = file.virtualFile?.url

    override fun doAnnotate(uri: String?): List<HelixSemanticRange>? {
        if (uri == null || !HelixSettings.getInstance().semanticTokensEnabled) return null
        val ctx = ApplicationManager.getApplication().runReadAction(Computable {
            val virtualFile = VirtualFileManager.getInstance().findFileByUrl(uri) ?: return@Computable null
            val project = ProjectLocator.getInstance().guessProjectForFile(virtualFile) ?: return@Computable null
            val document = FileDocumentManager.getInstance().getDocument(virtualFile) ?: return@Computable null
            project to document
        }) ?: return null
        val (project, document) = ctx
        val manager = project.getService(HelixLspServerManager::class.java) ?: return null

        if (!manager.isReady) return null
        var cached: JsonObject? = manager.semanticTokensCache[uri]
        if (cached == null) {
            try {
                val future = manager.request(
                    LspConstants.SEMANTIC_TOKENS,
                    LspMessages.requestFull(LspConstants.SEMANTIC_TOKENS, uri),
                )
                val response = future.get(1500, java.util.concurrent.TimeUnit.MILLISECONDS) ?: return null
                val result: JsonObject = response.getAsJsonObject("result")
                cached = result
                manager.semanticTokensCache[uri] = result
            } catch (_: Exception) {
                return null
            }
        }
        return decode(cached, document)
    }

    override fun apply(file: PsiFile, annotationResult: List<HelixSemanticRange>?, holder: AnnotationHolder) {
        val result = annotationResult ?: return
        for (range in result) {
            val start = range.startOffset
            val end = (range.startOffset + range.length).coerceAtMost(file.textLength)
            if (start >= end) continue
            holder.newSilentAnnotation(com.intellij.lang.annotation.HighlightSeverity.INFORMATION)
                .range(TextRange(start, end))
                .textAttributes(range.attributesKey)
                .create()
        }
    }

    private fun decode(payload: JsonObject, document: Document): List<HelixSemanticRange> {
        val data = payload.getAsJsonArray("data") ?: return emptyList()
        val out = mutableListOf<HelixSemanticRange>()
        var prevLine = 0
        var prevStart = 0
        var i = 0
        while (i + 4 < data.size()) {
            val deltaLine = data[i].asInt
            val deltaStart = data[i + 1].asInt
            val length = data[i + 2].asInt
            val typeIndex = data[i + 3].asInt
            i += 5
            val line = prevLine + deltaLine
            val startChar = if (deltaLine == 0) prevStart + deltaStart else deltaStart
            prevLine = line
            prevStart = startChar
            val typeName = TOKEN_TYPE_NAMES.getOrNull(typeIndex) ?: continue
            val offset = offsetAt(document, line, startChar) ?: continue
            if (offset < 0 || offset >= document.textLength) continue
            out.add(HelixSemanticRange(offset, length, KEY_FOR_TYPE[typeName] ?: continue))
        }
        return out
    }

    private fun offsetAt(document: Document, line: Int, character: Int): Int? {
        if (line < 0 || line >= document.lineCount) return null
        val lineStart = document.getLineStartOffset(line)
        val lineEnd = document.getLineEndOffset(line)
        return lineStart + character.coerceIn(0, lineEnd - lineStart)
    }

    companion object {
        val TOKEN_TYPE_NAMES = listOf(
            "keyword", "type", "function", "variable", "number",
            "string", "comment", "operator")

        val KEY_FOR_TYPE: Map<String, TextAttributesKey> = mapOf(
            "keyword" to TextAttributesKey.createTextAttributesKey(
                "HELIX_SEMANTIC_KEYWORD", DefaultLanguageHighlighterColors.KEYWORD),
            "type" to TextAttributesKey.createTextAttributesKey(
                "HELIX_SEMANTIC_TYPE", DefaultLanguageHighlighterColors.CLASS_NAME),
            "function" to TextAttributesKey.createTextAttributesKey(
                "HELIX_SEMANTIC_FUNCTION", DefaultLanguageHighlighterColors.FUNCTION_DECLARATION),
            "variable" to TextAttributesKey.createTextAttributesKey(
                "HELIX_SEMANTIC_VARIABLE", DefaultLanguageHighlighterColors.INSTANCE_FIELD),
            "number" to TextAttributesKey.createTextAttributesKey(
                "HELIX_SEMANTIC_NUMBER", DefaultLanguageHighlighterColors.NUMBER),
            "string" to TextAttributesKey.createTextAttributesKey(
                "HELIX_SEMANTIC_STRING", DefaultLanguageHighlighterColors.STRING),
            "comment" to TextAttributesKey.createTextAttributesKey(
                "HELIX_SEMANTIC_COMMENT", DefaultLanguageHighlighterColors.LINE_COMMENT),
            "operator" to TextAttributesKey.createTextAttributesKey(
                "HELIX_SEMANTIC_OPERATOR", DefaultLanguageHighlighterColors.OPERATION_SIGN),
        )
    }
}

/** One decoded semantic-token range at absolute document offsets. */
data class HelixSemanticRange(
    val startOffset: Int,
    val length: Int,
    val attributesKey: TextAttributesKey,
)
