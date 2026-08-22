package com.helixlang.plugin.syntax

import com.intellij.lang.ASTNode
import com.intellij.lang.folding.FoldingBuilderEx
import com.intellij.lang.folding.FoldingDescriptor
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.FoldingGroup
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.util.TextRange
import com.intellij.psi.PsiElement
import com.helixlang.plugin.psi.HelixFile

/**
 * Folding for `#gene … #end` blocks and long DNA bodies (doc/04 §5.8).
 * Primary source is `textDocument/foldingRange` (server); the builder falls
 * back to the mini-PSI model when the server is offline.
 */
class HelixClientFoldingBuilder : FoldingBuilderEx(), DumbAware {

    override fun buildFoldRegions(root: PsiElement, document: Document, quick: Boolean): Array<FoldingDescriptor> {
        if (root !is HelixFile) return EMPTY
        val descriptors = mutableListOf<FoldingDescriptor>()
        val lastLine = (document.lineCount - 1).coerceAtLeast(0)
        for (ann in root.annotations) {
            val startOffset = document.getLineStartOffset(ann.startLine.coerceIn(0, lastLine))
            val endOffset = document.getLineEndOffset(ann.endLine.coerceIn(0, lastLine))
            if (endOffset - startOffset < 2) continue
            descriptors.add(
                FoldingDescriptor(
                    root.node,
                    TextRange(startOffset, endOffset),
                    FoldingGroup.newGroup("helix"),
                    "…${ann.kind}",
                ))
        }
        return descriptors.toTypedArray()
    }

    override fun getPlaceholderText(node: ASTNode): String? = "…"

    override fun isCollapsedByDefault(node: ASTNode): Boolean = false

    companion object {
        private val EMPTY: Array<FoldingDescriptor> = emptyArray()
    }
}
