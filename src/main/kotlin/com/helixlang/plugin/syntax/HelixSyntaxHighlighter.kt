package com.helixlang.plugin.syntax

import com.intellij.lexer.Lexer
import com.intellij.openapi.editor.DefaultLanguageHighlighterColors
import com.intellij.openapi.editor.HighlighterColors
import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.fileTypes.SyntaxHighlighterBase
import com.intellij.psi.tree.IElementType

/**
 * Instant, offline lexical highlighter: annotation keywords, field names,
 * numbers, strings, comments, and the four DNA bases (doc/04 §5.2 layer 1).
 * Semantic tokens from the server layer on top and return `null` where they do
 * not classify, letting the lexical colors show through.
 */
class HelixSyntaxHighlighter : SyntaxHighlighterBase() {

    override fun getHighlightingLexer(): Lexer = HelixLexer()

    override fun getTokenHighlights(tokenType: IElementType?): Array<TextAttributesKey> {
        val key = TOKENS[tokenType] ?: return EMPTY
        return arrayOf(key)
    }

    companion object {
        val ANNOTATION: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_ANNOTATION", DefaultLanguageHighlighterColors.KEYWORD)
        val FIELD: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_FIELD", DefaultLanguageHighlighterColors.INSTANCE_FIELD)
        val OPERATOR: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_OPERATOR", DefaultLanguageHighlighterColors.IDENTIFIER)
        val NUMBER: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_NUMBER", DefaultLanguageHighlighterColors.NUMBER)
        val STRING: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_STRING", DefaultLanguageHighlighterColors.STRING)
        val COMMENT: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_COMMENT", DefaultLanguageHighlighterColors.LINE_COMMENT)
        val BASE_A: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_BASE_A", DefaultLanguageHighlighterColors.CONSTANT)
        val BASE_C: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_BASE_C", DefaultLanguageHighlighterColors.CONSTANT)
        val BASE_G: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_BASE_G", DefaultLanguageHighlighterColors.CONSTANT)
        val BASE_T: TextAttributesKey = TextAttributesKey.createTextAttributesKey(
            "HELIX_BASE_T", DefaultLanguageHighlighterColors.CONSTANT)
        val SYMBOL: TextAttributesKey = TextAttributesKey.createTextAttributesKey("HELIX_SYMBOL")
        val BAD_CHAR: TextAttributesKey = HighlighterColors.BAD_CHARACTER

        private val TOKENS: Map<IElementType?, TextAttributesKey> =
            mapOf(
                HelixTokenType.ANNOTATION to ANNOTATION,
                HelixTokenType.FIELD to FIELD,
                HelixTokenType.OPERATOR to OPERATOR,
                HelixTokenType.NUMBER to NUMBER,
                HelixTokenType.STRING to STRING,
                HelixTokenType.COMMENT to COMMENT,
                HelixTokenType.BASE_A to BASE_A,
                HelixTokenType.BASE_C to BASE_C,
                HelixTokenType.BASE_G to BASE_G,
                HelixTokenType.BASE_T to BASE_T,
                HelixTokenType.BRACKET_L to SYMBOL,
                HelixTokenType.BRACKET_R to SYMBOL,
                HelixTokenType.SYMBOL to SYMBOL,
                HelixTokenType.BAD to BAD_CHAR,
            )
    }
}
