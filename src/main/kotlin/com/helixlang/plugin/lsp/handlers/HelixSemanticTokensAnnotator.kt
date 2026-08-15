package com.helixlang.plugin.lsp.handlers

import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.helixlang.plugin.settings.HelixSettings
import com.helixlang.plugin.syntax.CodonColorKeys
import com.helixlang.plugin.syntax.CodonFamily
import com.helixlang.plugin.syntax.HelixCodonTable
import com.helixlang.plugin.syntax.HelixSyntaxHighlighter
import com.intellij.lang.annotation.AnnotationHolder
import com.intellij.lang.annotation.ExternalAnnotator
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.editor.DefaultLanguageHighlighterColors
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.colors.EditorColorsManager
import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.editor.markup.TextAttributes
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.project.ProjectLocator
import com.intellij.openapi.util.Computable
import com.intellij.openapi.util.TextRange
import com.intellij.openapi.vfs.VirtualFileManager
import com.intellij.psi.PsiFile

/**
 * Semantic-token highlighting (doc/04 §5.2 layer 2, doc/08 §3.3). Sends
 * `textDocument/semanticTokens/full` on a stale cache, decodes the relative
 * delta encoding, and layers the resulting ranges over the lexical pass.
 * Codons are colored by their opcode family (`HELIX_CODON_*`), with per-family
 * color overrides from [HelixSettings] applied on top of the IDE Color Scheme.
 * When the server is offline, a local fallback decodes DNA lines against the
 * bundled standard table (doc/08 §3.6) so colors still display.
 */
class HelixSemanticTokensAnnotator : ExternalAnnotator<String?, List<HelixSemanticRange>>(), DumbAware {

    private data class Ctx(val project: com.intellij.openapi.project.Project, val document: Document)

    override fun collectInformation(file: PsiFile): String? = file.virtualFile?.url

    override fun doAnnotate(uri: String?): List<HelixSemanticRange>? {
        if (uri == null || !HelixSettings.getInstance().semanticTokensEnabled) return null
        val ctx = ApplicationManager.getApplication().runReadAction(Computable {
            val virtualFile = VirtualFileManager.getInstance().findFileByUrl(uri) ?: return@Computable null
            val project = ProjectLocator.getInstance().guessProjectForFile(virtualFile) ?: return@Computable null
            val document = FileDocumentManager.getInstance().getDocument(virtualFile) ?: return@Computable null
            Ctx(project, document)
        }) ?: return null

        val manager = ctx.project.getService(HelixLspServerManager::class.java) ?: return null
        if (!manager.isReady) return fallbackRanges(ctx.document)

        var cached: JsonObject? = manager.semanticTokensCache[uri]
        if (cached == null) {
            try {
                val future = manager.request(
                    LspConstants.SEMANTIC_TOKENS,
                    LspMessages.requestFull(LspConstants.SEMANTIC_TOKENS, uri),
                )
                val response = future.get(1500, java.util.concurrent.TimeUnit.MILLISECONDS) ?: return fallbackRanges(ctx.document)
                val result: JsonObject = response.getAsJsonObject("result")
                cached = result
                manager.semanticTokensCache[uri] = result
            } catch (_: Exception) {
                return fallbackRanges(ctx.document)
            }
        }
        return decode(cached, ctx.document)
    }

    override fun apply(file: PsiFile, annotationResult: List<HelixSemanticRange>?, holder: AnnotationHolder) {
        val result = annotationResult ?: return
        val settings = HelixSettings.getInstance()
        for (range in result) {
            val start = range.startOffset
            val end = (range.startOffset + range.length).coerceAtMost(file.textLength)
            if (start >= end) continue
            holder.newSilentAnnotation(com.intellij.lang.annotation.HighlightSeverity.INFORMATION)
                .range(TextRange(start, end))
                .enforcedTextAttributes(effectiveAttributes(range, settings))
                .create()
        }
    }

    /**
     * Effective color for a codon family: settings override > IDE Color Scheme
     * value > built-in fallback (doc/08 §3.3.3). Non-codon ranges use the
     * scheme key directly.
     */
    private fun effectiveAttributes(range: HelixSemanticRange, settings: HelixSettings): TextAttributes {
        val schemeAttrs = EditorColorsManager.getInstance().globalScheme.getAttributes(range.attributesKey)
        val base = schemeAttrs ?: TextAttributes()
        val family = range.family ?: return base
        val color = CodonColorKeys.effectiveOverrideColor(
            settings.codonColorCustom,
            settings.codonColorOverrides[family.id],
        ) ?: return base
        val copy = TextAttributes()
        copy.copyFrom(base)
        copy.foregroundColor = color
        return copy
    }

    /**
     * Offline fallback (doc/08 §3.6): decode pure-DNA lines against the bundled
     * standard table and map each codon to its family.
     */
    private fun fallbackRanges(document: Document): List<HelixSemanticRange> {
        val out = mutableListOf<HelixSemanticRange>()
        val text = document.text
        val lines = text.split("\n")
        var offset = 0
        for (line in lines) {
            for ((range, family) in HelixCodonTable.codonSpans(line)) {
                val start = offset + range.first
                out.add(HelixSemanticRange(start, 3, CodonColorKeys.keyForFamily(family), family))
            }
            offset += line.length + 1
        }
        return out
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
            val key = KEY_FOR_TYPE[typeName] ?: continue
            out.add(HelixSemanticRange(offset, length, key, CodonColorKeys.familyForTokenType(typeName)))
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
            "string", "comment", "operator", "arrow",
            "opcodeStart", "opcodeHalt", "opcodeStack", "opcodeSynthesis",
            "opcodeBehavior", "opcodeMorphology", "opcodeRegulation",
            "opcodeCall", "opcodeArithmetic")

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
            "arrow" to HelixSyntaxHighlighter.OPERATOR,
        ).plus(CodonColorKeys.families.associate { it.id to CodonColorKeys.keyForFamily(it) })
    }
}

/** One decoded semantic-token range at absolute document offsets. */
data class HelixSemanticRange(
    val startOffset: Int,
    val length: Int,
    val attributesKey: TextAttributesKey,
    val family: CodonFamily? = null,
)
