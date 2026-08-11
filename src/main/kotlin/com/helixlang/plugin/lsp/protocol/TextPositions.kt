package com.helixlang.plugin.lsp.protocol

/**
 * UTF-16 ↔ character offset helpers. IntelliJ [com.intellij.openapi.editor.Document]
 * offsets are UTF-16 code units, so character→code-unit conversion matters only
 * for non-BMP text (doc/06 §3.2).
 */
object TextPositions {

    /** UTF-16 code-unit offset of the given character offset in [text]. */
    fun utf16Units(text: CharSequence, charOffset: Int): Int {
        var units = 0
        for (i in 0 until charOffset) {
            val c = text[i]
            units += if (Character.isHighSurrogate(c)) 2 else 1
        }
        return units
    }

    /** Character offset corresponding to a UTF-16 code-unit offset in [text]. */
    fun charAtUnits(text: CharSequence, unitOffset: Int): Int {
        var units = 0
        var chars = 0
        while (units < unitOffset && chars < text.length) {
            val c = text[chars]
            units += if (Character.isHighSurrogate(c)) 2 else 1
            chars++
        }
        return chars
    }
}
