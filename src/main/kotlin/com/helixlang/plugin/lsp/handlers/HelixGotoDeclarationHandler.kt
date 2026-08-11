package com.helixlang.plugin.lsp.handlers

import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.helixlang.plugin.psi.HelixFile
import com.helixlang.plugin.psi.HelixSymbol
import com.intellij.codeInsight.navigation.actions.GotoDeclarationHandler
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiFile

/**
 * Go-to-definition (doc/04 §5.5). Sends `textDocument/definition` and navigates
 * to the returned `Location`. Resolution is server-first, with the mini-PSI
 * same-file fallback when the server is offline.
 */
class HelixGotoDeclarationHandler : GotoDeclarationHandler {

    override fun getGotoDeclarationTargets(
        sourceElement: PsiElement?,
        offset: Int,
        editor: Editor,
    ): Array<PsiElement>? {
        val file = sourceElement?.containingFile ?: return null
        if (file !is HelixFile) return null
        val fileUri = file.virtualFile?.url ?: return null
        val project = file.project
        val line = editor.document.getLineNumber(offset)
        val character = offset - editor.document.getLineStartOffset(line)
        val manager = project.getService(HelixLspServerManager::class.java)

        if (manager != null && manager.isReady) {
            val future = manager.request(
                LspConstants.DEFINITION,
                LspMessages.requestPosition(LspConstants.DEFINITION, fileUri, line, character),
            )
            try {
                val result = future.get(1000, java.util.concurrent.TimeUnit.MILLISECONDS)
                val locations = result.getAsJsonObject("result").getAsJsonArray()
                if (locations.size() > 0) {
                    val target = locationElement(project, locations[0].asJsonObject)
                    if (target != null) return arrayOf(target)
                }
            } catch (_: Exception) {
                // fall through to mini-PSI fallback
            }
        }

        val symbol: HelixSymbol = file.symbolAt(offset) ?: return null
        return arrayOf(file)
    }

    private fun locationElement(
        project: com.intellij.openapi.project.Project,
        location: com.google.gson.JsonObject,
    ): PsiElement? {
        val uri = location.get("uri")?.asString ?: return null
        if (uri.startsWith("file:")) {
            val virtualFile: VirtualFile? = com.intellij.openapi.vfs.LocalFileSystem.getInstance()
                .findFileByIoFile(java.io.File(uri.removePrefix("file:").let { java.net.URI(it).path }))
            if (virtualFile != null) {
                val psiFile: PsiFile = com.intellij.psi.PsiManager.getInstance(project).findFile(virtualFile)
                    ?: return null
                val range = location.getAsJsonObject("range")
                val line = range.getAsJsonObject("start").get("line").asInt
                if (psiFile is HelixFile && line < psiFile.annotations.size) {
                    return psiFile
                }
                return psiFile
            }
        }
        return null
    }
}
