package com.helixlang.plugin.syntax

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class HelixCodonTableTest {

    @Test
    fun `standard table covers all 64 codons`() {
        assertEquals(64, HelixCodonTable.STANDARD_TABLE.size)
        for (a in "ACGT") for (b in "ACGT") for (c in "ACGT") {
            assertTrue(
                "$a$b$c" in HelixCodonTable.STANDARD_TABLE,
                "missing codon $a$b$c",
            )
        }
    }

    @Test
    fun `decode is case-insensitive and rejects unknowns`() {
        assertEquals(HelixCodonTable.OP_START, HelixCodonTable.decode("ATG"))
        assertEquals(HelixCodonTable.OP_START, HelixCodonTable.decode("atg"))
        assertEquals(HelixCodonTable.OP_HALT, HelixCodonTable.decode("TAA"))
        assertNull(HelixCodonTable.decode("NNN"))
        assertNull(HelixCodonTable.decode(""))
    }

    @Test
    fun `codons map to their families`() {
        assertEquals(CodonFamily.START, HelixCodonTable.familyForCodon("ATG"))
        assertEquals(CodonFamily.HALT, HelixCodonTable.familyForCodon("TGA"))
        assertEquals(CodonFamily.STACK, HelixCodonTable.familyForCodon("TTT"))
        assertEquals(CodonFamily.SYNTHESIS, HelixCodonTable.familyForCodon("GCT"))
        assertEquals(CodonFamily.BEHAVIOR, HelixCodonTable.familyForCodon("GTT"))
        assertEquals(CodonFamily.MORPHOLOGY, HelixCodonTable.familyForCodon("CTT"))
        assertEquals(CodonFamily.REGULATION, HelixCodonTable.familyForCodon("ATT"))
        assertEquals(CodonFamily.CALL, HelixCodonTable.familyForCodon("CGT"))
        assertNull(HelixCodonTable.familyForCodon("NNN"))
    }

    @Test
    fun `all opcode constants are assigned to a family`() {
        val constants = listOf(
            HelixCodonTable.OP_START, HelixCodonTable.OP_HALT,
            HelixCodonTable.OP_PUSH_CONST,
            HelixCodonTable.OP_BUILD_PROTEIN, HelixCodonTable.OP_BUILD_MEMBRANE,
            HelixCodonTable.OP_BUILD_PIGMENT,
            HelixCodonTable.OP_MOVE, HelixCodonTable.OP_SIGNAL,
            HelixCodonTable.OP_DIVIDE, HelixCodonTable.OP_DIE, HelixCodonTable.OP_FEED,
            HelixCodonTable.OP_GROW_LSYSTEM, HelixCodonTable.OP_DIFFUSE,
            HelixCodonTable.OP_REACT, HelixCodonTable.OP_EMIT_MORPHOGEN,
            HelixCodonTable.OP_READ_MEM, HelixCodonTable.OP_WRITE_MEM,
            HelixCodonTable.OP_MODIFY_STATE, HelixCodonTable.OP_REGULATE,
            HelixCodonTable.OP_BIND,
            HelixCodonTable.OP_CALL_GENE,
        )
        assertEquals(constants.size, constants.mapNotNull { HelixCodonTable.familyForOpcode(it) }.size)
    }

    @Test
    fun `codonSpans returns the documented preview colors`() {
        val spans = HelixCodonTable.codonSpans("ATG GCT GGT GTA TAA")
        assertEquals(
            listOf(
                0..2 to CodonFamily.START,
                4..6 to CodonFamily.SYNTHESIS,
                8..10 to CodonFamily.SYNTHESIS,
                12..14 to CodonFamily.BEHAVIOR,
                16..18 to CodonFamily.HALT,
            ),
            spans,
        )
    }

    @Test
    fun `codonSpans ignores non-dna and malformed lines`() {
        assertTrue(HelixCodonTable.codonSpans("GGN NNN ATG").isEmpty())
        assertTrue(HelixCodonTable.codonSpans("MOVE 123").isEmpty())
        assertTrue(HelixCodonTable.codonSpans("ATG # comment").isEmpty())
        assertTrue(HelixCodonTable.codonSpans("").isEmpty())
        assertEquals(
            listOf(0..2 to CodonFamily.START),
            HelixCodonTable.codonSpans("ATG AT"),
        )
    }

    @Test
    fun `lowercase dna still resolves families`() {
        assertEquals(
            listOf(0..2 to CodonFamily.START, 4..6 to CodonFamily.SYNTHESIS),
            HelixCodonTable.codonSpans("atg gct"),
        )
    }

    @Test
    fun `isDnaLine sanity`() {
        assertTrue(HelixCodonTable.isDnaLine("ATG GCT"))
        assertTrue(HelixCodonTable.isDnaLine("atg\tgct\n"))
        assertFalse(HelixCodonTable.isDnaLine("ATG NNN"))
        assertFalse(HelixCodonTable.isDnaLine("ATG # c"))
        assertFalse(HelixCodonTable.isDnaLine(""))
    }
}
