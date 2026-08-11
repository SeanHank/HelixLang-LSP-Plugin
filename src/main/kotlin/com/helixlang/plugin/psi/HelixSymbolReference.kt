package com.helixlang.plugin.psi

import com.intellij.psi.PsiElement
import com.intellij.psi.PsiReference

/** A use site of a symbol in a .helix file. */
class HelixSymbolReference(
    private val element: PsiElement,
    private val name: String,
) : PsiReference {

    override fun getElement(): PsiElement = element

    override fun getRangeInElement(): com.intellij.openapi.util.TextRange =
        TextRanges.textRangeOf(element, name)

    override fun resolve(): PsiElement? = null // server-first resolution

    override fun getCanonicalText(): String = name

    override fun handleElementRename(newElementName: String): PsiElement {
        // Mini-PSI is read-only; renames go through the server in a later milestone.
        return element
    }

    override fun bindToElement(element: PsiElement): PsiElement = this.element

    override fun isReferenceTo(element: PsiElement): Boolean = false

    override fun getVariants(): Array<Any> = emptyArray()

    override fun isSoft(): Boolean = true
}

internal object TextRanges {
    fun textRangeOf(element: PsiElement, text: String): com.intellij.openapi.util.TextRange {
        val offset = element.textOffset
        return com.intellij.openapi.util.TextRange.from(offset, text.length)
    }
}
