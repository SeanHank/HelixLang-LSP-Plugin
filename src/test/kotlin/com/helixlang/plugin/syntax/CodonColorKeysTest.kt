package com.helixlang.plugin.syntax

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.awt.Color

class CodonColorKeysTest {

    @Test
    fun `families are in documented order and have stable ids`() {
        assertEquals(
            listOf("opcodeStart", "opcodeHalt", "opcodeStack", "opcodeSynthesis",
                "opcodeBehavior", "opcodeMorphology", "opcodeRegulation",
                "opcodeCall", "opcodeArithmetic"),
            CodonColorKeys.families.map { it.id },
        )
        assertEquals(9, CodonColorKeys.families.size)
        assertEquals(CodonFamily.START, CodonColorKeys.families.first())
        assertEquals(CodonFamily.ARITHMETIC, CodonColorKeys.families.last())
    }

    @Test
    fun `every family has a unique HELIX_CODON color key`() {
        val keys = CodonColorKeys.families.map { CodonColorKeys.keyForFamily(it) }
        assertEquals(CodonColorKeys.families.size, keys.toSet().size)
        assertTrue(keys.all { it.externalName.startsWith("HELIX_CODON_") })
    }

    @Test
    fun `token type maps to family and back`() {
        assertEquals(CodonFamily.SYNTHESIS, CodonColorKeys.familyForTokenType("opcodeSynthesis"))
        assertEquals(
            CodonColorKeys.keyForFamily(CodonFamily.HALT),
            CodonColorKeys.keyForTokenType("opcodeHalt"),
        )
        assertNull(CodonColorKeys.familyForTokenType("keyword"))
        assertNull(CodonColorKeys.keyForTokenType("nonsense"))
    }

    @Test
    fun `parseHexColor accepts and rejects the expected forms`() {
        assertEquals(Color(255, 136, 0), CodonColorKeys.parseHexColor("#FF8800"))
        assertEquals(Color(255, 136, 0), CodonColorKeys.parseHexColor("ff8800"))
        assertEquals(Color(0, 0, 0), CodonColorKeys.parseHexColor("#000000"))
        assertNull(CodonColorKeys.parseHexColor("#ABC"))
        assertNull(CodonColorKeys.parseHexColor("#GGGGGG"))
        assertNull(CodonColorKeys.parseHexColor("garbage"))
        assertNull(CodonColorKeys.parseHexColor(null))
    }

    @Test
    fun `effectiveOverrideColor only applies when custom is on and hex is valid`() {
        assertEquals(Color(255, 0, 0), CodonColorKeys.effectiveOverrideColor(true, "#FF0000"))
        assertEquals(Color(255, 0, 0), CodonColorKeys.effectiveOverrideColor(true, "ff0000"))
        assertNull(CodonColorKeys.effectiveOverrideColor(false, "#FF0000"))
        assertNull(CodonColorKeys.effectiveOverrideColor(true, "not-a-color"))
        assertNull(CodonColorKeys.effectiveOverrideColor(true, null))
    }
}
