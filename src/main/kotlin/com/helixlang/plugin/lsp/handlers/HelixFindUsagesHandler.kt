package com.helixlang.plugin.lsp.handlers

import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.helixlang.plugin.psi.HelixFile
import com.intellij.find.findUsages.FindUsagesHandler
import com.intellij.find.findUsages.FindUsagesHandlerFactory
import com.intellij.find.findUsages.FindUsagesOptions
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiFile
import com.intellij.psi.PsiManager
import com.intellij.util.Processor
import com.intellij.usageView.UsageInfo
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Find-usages (doc/04 §5.6). The factory is registered for HelixLang; the
 * handler sends `textDocument/references` and maps the returned locations to
 * [UsageInfo]s, honoring `includeDeclaration`. Falls back to same-file string
 * matches when the server is offline.
 */
class HelixFindUsagesHandlerFactory : FindUsagesHandlerFactory() {

    override fun canFindUsages(element: PsiElement): Boolean = element.containingFile is HelixFile

    override fun createFindUsagesHandler(element: PsiElement, forHighlightUsages: Boolean): FindUsagesHandler =
        HelixReferencesHandler(element)
}

class HelixReferencesHandler(element: PsiElement) : FindUsagesHandler(element) {

    override fun processElementUsages(
        element: PsiElement,
        processor: Processor<in UsageInfo>,
        options: FindUsagesOptions,
    ): Boolean {
        val file = element.containingFile as? HelixFile ?: return true
        val project = file.project
        val offset = element.textOffset
        val uri = file.virtualFile?.url ?: return true
        val doc = file.viewProvider.document
        val line = if (doc == null || doc.textLength == 0) 0 else doc.getLineNumber(offset)
        val character = if (doc == null || doc.textLength == 0) 0 else offset - doc.getLineStartOffset(line)

        val manager = project.getService(HelixLspServerManager::class.java)
        if (manager != null && manager.isReady) {
            try {
                val params = LspMessages.requestPosition(LspConstants.REFERENCES, uri, line, character)
                val context = JsonObject()
                context.addProperty("includeDeclaration", options.isUsages)
                params.add("context", context)
                val response = manager.request(LspConstants.REFERENCES, params)
                    .get(2000, TimeUnit.MILLISECONDS)
                val locations = response.getAsJsonObject("result").getAsJsonArray()
                if (locations.size() > 0) {
                    return processLocations(locations, processor, options, project)
                }
            } catch (_: Exception) {
                // fall back to same-file search
            }
        }

        val name = wordAt(file, offset) ?: return true
        for (reference in file.referencesTo(name)) {
            val usage = UsageInfo(reference)
            if (!processor.process(usage)) return false
        }
        return true
    }

    private fun processLocations(
        locations: JsonArray,
        processor: Processor<in UsageInfo>,
        options: FindUsagesOptions,
        project: com.intellij.openapi.project.Project,
    ): Boolean {
        val psiManager = PsiManager.getInstance(project)
        for (element in locations) {
            if (!element.isJsonObject) continue
            val location = element.asJsonObject
            val uri = location.get("uri")?.asString ?: continue
            val file = fileForUri(psiManager, uri) ?: continue
            val scope = options.searchScope
            if (scope != null && !scope.contains(file.virtualFile)) continue
            val range = location.getAsJsonObject("range")
            val start = range.getAsJsonObject("start")
            val end = range.getAsJsonObject("end")
            val startOffset = offsetAt(file, start.get("line").asInt, start.get("character").asInt)
                ?: continue
            val endOffset = offsetAt(file, end.get("line").asInt, end.get("character").asInt)
                ?: continue
            val usage = UsageInfo(file, startOffset, endOffset)
            if (!processor.process(usage)) return false
        }
        return true
    }

    private fun fileForUri(psiManager: PsiManager, uri: String): PsiFile? {
        return try {
            if (!uri.startsWith("file:")) return null
            val path = java.net.URI(uri).path
            val virtualFile: VirtualFile? = LocalFileSystem.getInstance().findFileByIoFile(File(path))
            if (virtualFile == null) null else psiManager.findFile(virtualFile)
        } catch (_: Exception) {
            null
        }
    }

    private fun offsetAt(file: PsiFile, line: Int, character: Int): Int? {
        val doc = file.viewProvider.document ?: return null
        if (line < 0 || line >= doc.lineCount) return null
        val lineStart = doc.getLineStartOffset(line)
        val lineEnd = doc.getLineEndOffset(line)
        return lineStart + character.coerceIn(0, lineEnd - lineStart)
    }

    private fun wordAt(file: HelixFile, offset: Int): String? {
        val text = file.text
        if (offset < 0 || offset > text.length) return null
        var start = offset
        var end = offset
        while (start > 0 && isIdentifierChar(text[start - 1])) start--
        while (end < text.length && isIdentifierChar(text[end])) end++
        return if (end > start) text.substring(start, end) else null
    }

    private fun isIdentifierChar(c: Char): Boolean = c.isLetterOrDigit() || c == '_'
}
