package com.helixlang.plugin.psi

import com.intellij.lang.findUsages.FindUsagesProvider
import com.intellij.psi.PsiElement

/**
 * Find-usages entry point for `HelixSymbol` elements (doc/04 §5.6). The heavy
 * lifting is done server-side via `textDocument/references`; this provider only
 * supplies the display text and a same-file fallback.
 */
class HelixFindUsagesProvider : FindUsagesProvider {

    override fun getNodeText(element: PsiElement, useFullName: Boolean): String {
        val text = element.text?.trim() ?: ""
        return text.substring(0, minOf(text.length, 80))
    }

    override fun getHelpId(element: PsiElement): String? = null

    override fun getType(element: PsiElement): String = "symbol"

    override fun getDescriptiveName(element: PsiElement): String = element.text ?: ""

    override fun canFindUsagesFor(element: PsiElement): Boolean = true
}
