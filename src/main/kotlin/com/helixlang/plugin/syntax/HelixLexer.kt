package com.helixlang.plugin.syntax

import com.intellij.lexer.Lexer
import com.intellij.lexer.LexerBase
import com.intellij.psi.tree.IElementType

/**
 * Simple line-based lexer for HelixLang. Recognizes `#annotation`, `key=value`
 * fields, numbers, quoted strings, `#` comments, and the four DNA bases.
 */
class HelixLexer : LexerBase() {

    private var text: CharSequence = ""
    private var start = 0
    private var end = 0
    private var state: IElementType = HelixTokenType.WHITE

    override fun start(buffer: CharSequence, startOffset: Int, endOffset: Int, initialState: Int) {
        text = buffer
        start = startOffset
        end = startOffset
        state = HelixTokenType.WHITE
        advanceInternal()
    }

    override fun getState(): Int = 0

    override fun getTokenType(): IElementType? = if (start < end) state else null

    override fun getTokenStart(): Int = start

    override fun getTokenEnd(): Int = end

    override fun advance() {
        if (end >= text.length) {
            start = text.length
            return
        }
        start = end
        advanceInternal()
    }

    override fun getBufferSequence(): CharSequence = text

    override fun getBufferEnd(): Int = text.length

    private fun advanceInternal() {
        if (start >= text.length) {
            end = start
            return
        }
        val c = text[start]
        when {
            c == '#' -> {
                lexAnnotationOrComment()
                return
            }
            c.isWhitespace() -> {
                end = lexRun { it.isWhitespace() }
                state = HelixTokenType.WHITE
            }
            c == '"' -> {
                lexString()
                return
            }
            c.isDigit() -> {
                end = lexRun { it.isDigit() }
                state = HelixTokenType.NUMBER
            }
            c in "ACGT" -> {
                end = lexRun { it in "ACGT" }
                state = baseType(c)
            }
            c == '=' || c in "->" -> {
                end = start + 1
                state = HelixTokenType.OPERATOR
            }
            c == '[' -> {
                end = start + 1
                state = HelixTokenType.BRACKET_L
            }
            c == ']' -> {
                end = start + 1
                state = HelixTokenType.BRACKET_R
            }
            c in "(),.'+*/%&|^~!?;:@" -> {
                end = start + 1
                state = HelixTokenType.SYMBOL
            }
            c == '_' || c.isLetter() -> {
                end = lexRun { it == '_' || it.isLetterOrDigit() }
                state = HelixTokenType.FIELD
            }
            else -> {
                end = start + 1
                state = HelixTokenType.BAD
            }
        }
    }

    private fun lexAnnotationOrComment(): Int {
        // "#" alone on a line, or followed by whitespace, is a comment that runs
        // to the end of the line; "#word" is an annotation.
        var i = start + 1
        if (i >= text.length || text[i] == '\n') {
            end = i
            state = HelixTokenType.COMMENT
            return end
        }
        if (text[i] == ' ' || text[i] == '\t') {
            while (i < text.length && text[i] != '\n') i++
            end = i
            state = HelixTokenType.COMMENT
            return end
        }
        while (i < text.length && (text[i] == '_' || text[i].isLetterOrDigit())) i++
        end = i
        state = HelixTokenType.ANNOTATION
        return end
    }

    private fun lexString(): Int {
        var i = start + 1
        while (i < text.length && text[i] != '"') {
            if (text[i] == '\\' && i + 1 < text.length) i++
            i++
        }
        if (i < text.length) i++ // closing quote
        end = i
        state = HelixTokenType.STRING
        return end
    }

    private fun lexRun(predicate: (Char) -> Boolean): Int {
        var i = start
        while (i < text.length && predicate(text[i])) i++
        return i
    }

    private fun baseType(c: Char): IElementType = when (c) {
        'A' -> HelixTokenType.BASE_A
        'C' -> HelixTokenType.BASE_C
        'G' -> HelixTokenType.BASE_G
        else -> HelixTokenType.BASE_T
    }
}
