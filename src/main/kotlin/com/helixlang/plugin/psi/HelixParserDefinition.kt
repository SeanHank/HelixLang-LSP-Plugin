package com.helixlang.plugin.psi

import com.intellij.lang.ASTNode
import com.intellij.lang.ParserDefinition
import com.intellij.lang.PsiParser
import com.intellij.lexer.Lexer
import com.helixlang.plugin.syntax.HelixLexer
import com.intellij.openapi.project.Project
import com.intellij.psi.FileViewProvider
import com.intellij.psi.PsiElement
import com.intellij.psi.PsiFile
import com.intellij.psi.tree.IFileElementType
import com.intellij.psi.tree.TokenSet
import com.helixlang.plugin.filetype.HelixLanguage

/**
 * ParserDefinition for HelixLang. The mini-PSI model is lazy and read-only
 * (doc/02 §6): the AST is a single file node that folds every token from
 * [HelixLexer] into a flat tree, and [HelixFile] builds the structure on
 * demand from the raw text, so the editor never reparses PSI while typing.
 */
class HelixParserDefinition : ParserDefinition {

    override fun createLexer(project: Project?): Lexer = HelixLexer()

    override fun createParser(project: Project?): PsiParser = PsiParser { root, builder ->
        val marker = builder.mark()
        while (!builder.eof()) {
            builder.advanceLexer()
        }
        marker.done(root)
        builder.treeBuilt
    }

    override fun getFileNodeType(): IFileElementType = FILE

    override fun getCommentTokens(): TokenSet = TokenSet.EMPTY

    override fun getStringLiteralElements(): TokenSet = TokenSet.EMPTY

    override fun getWhitespaceTokens(): TokenSet = TokenSet.EMPTY

    override fun createElement(node: ASTNode): PsiElement = HelixLazyElement(node)

    override fun createFile(viewProvider: FileViewProvider): PsiFile = HelixFile(viewProvider)

    companion object {
        val FILE: IFileElementType = IFileElementType(HelixLanguage)
    }
}
