package com.helixlang.plugin.syntax

import com.intellij.lang.BracePair
import com.intellij.lang.PairedBraceMatcher
import com.intellij.psi.PsiFile
import com.intellij.psi.tree.IElementType

/**
 * Brace matcher: pairs `#gene ↔ #end` annotation blocks, `[` `]` in L-system
 * rules, and `"` quotes (doc/04 §5.10).
 */
class HelixBraceMatcher : PairedBraceMatcher {

    override fun getPairs(): Array<BracePair> = arrayOf(
        BracePair(HelixTokenType.ANNOTATION, HelixTokenType.ANNOTATION, true),
        BracePair(HelixTokenType.BRACKET_L, HelixTokenType.BRACKET_R, false),
    )

    override fun isPairedBracesAllowedBeforeType(lbraceType: IElementType, contextType: IElementType?): Boolean = true

    override fun getCodeConstructStart(file: PsiFile, openingBraceOffset: Int): Int = openingBraceOffset
}
