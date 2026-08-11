package com.helixlang.plugin.lsp.protocol

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Test

class TextPositionsTest {

    @Test
    fun `ascii maps one unit per char`() {
        assertEquals(4, TextPositions.utf16Units("ATGT", 4))
        assertEquals(4, TextPositions.charAtUnits("ATGT", 4))
    }

    @Test
    fun `non-bmp char counts as two utf16 units`() {
        // U+1F600 (surrogate pair) counts as 2 code units
        val text = "A\uD83D\uDE00C"
        assertEquals(3, TextPositions.utf16Units(text, 2)) // A + surrogate pair
        assertEquals(2, TextPositions.charAtUnits(text, 3)) // back to 2 chars
    }

    @Test
    fun `round trips agree`() {
        val text = "AB\uD83D\uDE00CD"
        for (charOffset in 0..text.length) {
            val units = TextPositions.utf16Units(text, charOffset)
            assertEquals(charOffset, TextPositions.charAtUnits(text, units))
        }
    }
}
