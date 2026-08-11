package com.helixlang.plugin.psi

import com.helixlang.plugin.filetype.HelixLanguage
import com.intellij.extapi.psi.PsiFileBase
import com.intellij.openapi.fileTypes.FileType
import com.intellij.psi.FileViewProvider
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiReference
import com.intellij.psi.tree.IFileElementType

/**
 * The `.helix` PSI file. The mini-PSI model is built lazily on demand by
 * [HelixPsiParser] and is read-only (doc/02 §6).
 */
class HelixFile(viewProvider: FileViewProvider) : PsiFileBase(viewProvider, HelixLanguage) {

    private val structure: List<HelixAnnotation> by lazy {
        HelixPsiParser.parse(text)
    }

    val annotations: List<HelixAnnotation> get() = structure

    val symbols: List<HelixSymbol>
        get() = structure.flatMap { it.symbols }

    override fun getFileType(): FileType =
        com.helixlang.plugin.filetype.HelixFileType.INSTANCE

    override fun getFileElementType(): IFileElementType? =
        HelixParserDefinition.FILE

    /** Symbols whose definition range contains [offset] (fallback navigation). */
    fun symbolAt(offset: Int): HelixSymbol? =
        symbols.firstOrNull { it.definitionRange.contains(offset) }

    /** Fallback same-file references for find-usages when the server is offline. */
    fun referencesTo(name: String): List<PsiReference> {
        val out = mutableListOf<PsiReference>()
        val text = this.text
        var from = 0
        while (true) {
            val idx = text.indexOf(name, from)
            if (idx < 0) break
            val element: PsiElement = this
            out.add(HelixSymbolReference(element, name))
            from = idx + name.length
        }
        return out
    }

    override fun toString(): String = "HelixFile:${name ?: ""}"
}
