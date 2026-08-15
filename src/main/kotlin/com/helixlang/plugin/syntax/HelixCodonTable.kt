package com.helixlang.plugin.syntax

/**
 * Rendering-only codon decoder used for the offline highlighting fallback
 * (doc/08 §3.6). Mirrors `helixlang/src/helixlang/codon_table.py` for the
 * standard table; it is deliberately non-authoritative (the server owns all
 * semantics). The inlay-hint and semantic-token fallbacks share this table.
 */
object HelixCodonTable {

    // Opcode values, mirroring helixlang.bytecode.Op (rendering only).
    const val OP_START = 0x10
    const val OP_HALT = 0x11
    const val OP_PUSH_CONST = 0x20
    const val OP_BUILD_PROTEIN = 0x30
    const val OP_BUILD_MEMBRANE = 0x31
    const val OP_BUILD_PIGMENT = 0x32
    const val OP_MOVE = 0x40
    const val OP_SIGNAL = 0x41
    const val OP_DIVIDE = 0x42
    const val OP_DIE = 0x43
    const val OP_FEED = 0x44
    const val OP_GROW_LSYSTEM = 0x50
    const val OP_DIFFUSE = 0x51
    const val OP_REACT = 0x52
    const val OP_EMIT_MORPHOGEN = 0x53
    const val OP_READ_MEM = 0x60
    const val OP_WRITE_MEM = 0x61
    const val OP_MODIFY_STATE = 0x62
    const val OP_REGULATE = 0x63
    const val OP_BIND = 0x64
    const val OP_CALL_GENE = 0x70

    /** Standard translation table (NCBI table 1): codon -> opcode. */
    val STANDARD_TABLE: Map<String, Int> = mapOf(
        "ATG" to OP_START,
        "TAA" to OP_HALT, "TAG" to OP_HALT, "TGA" to OP_HALT,
        "TTT" to OP_PUSH_CONST, "TTC" to OP_PUSH_CONST,
        "CTT" to OP_GROW_LSYSTEM, "CTC" to OP_GROW_LSYSTEM,
        "CTA" to OP_GROW_LSYSTEM, "CTG" to OP_GROW_LSYSTEM,
        "TTA" to OP_GROW_LSYSTEM, "TTG" to OP_GROW_LSYSTEM,
        "ATT" to OP_READ_MEM, "ATC" to OP_READ_MEM, "ATA" to OP_READ_MEM,
        "GTT" to OP_MOVE, "GTC" to OP_MOVE, "GTA" to OP_MOVE, "GTG" to OP_MOVE,
        "TCT" to OP_SIGNAL, "TCC" to OP_SIGNAL, "TCA" to OP_SIGNAL, "TCG" to OP_SIGNAL,
        "AGT" to OP_SIGNAL, "AGC" to OP_SIGNAL,
        "CCT" to OP_MODIFY_STATE, "CCC" to OP_MODIFY_STATE,
        "CCA" to OP_MODIFY_STATE, "CCG" to OP_MODIFY_STATE,
        "ACT" to OP_DIFFUSE, "ACC" to OP_DIFFUSE,
        "ACA" to OP_DIFFUSE, "ACG" to OP_DIFFUSE,
        "GCT" to OP_BUILD_PROTEIN, "GCC" to OP_BUILD_PROTEIN,
        "GCA" to OP_BUILD_PROTEIN, "GCG" to OP_BUILD_PROTEIN,
        "TAT" to OP_WRITE_MEM, "TAC" to OP_WRITE_MEM,
        "CAT" to OP_REGULATE, "CAC" to OP_REGULATE,
        "CAA" to OP_EMIT_MORPHOGEN, "CAG" to OP_EMIT_MORPHOGEN,
        "AAT" to OP_DIVIDE, "AAC" to OP_DIVIDE,
        "AAA" to OP_DIE, "AAG" to OP_DIE,
        "GAT" to OP_REACT, "GAC" to OP_REACT,
        "GAA" to OP_FEED, "GAG" to OP_FEED,
        "TGT" to OP_BIND, "TGC" to OP_BIND,
        "TGG" to OP_BUILD_PIGMENT,
        "CGT" to OP_CALL_GENE, "CGC" to OP_CALL_GENE,
        "CGA" to OP_CALL_GENE, "CGG" to OP_CALL_GENE,
        "AGA" to OP_CALL_GENE, "AGG" to OP_CALL_GENE,
        "GGT" to OP_BUILD_MEMBRANE, "GGC" to OP_BUILD_MEMBRANE,
        "GGA" to OP_BUILD_MEMBRANE, "GGG" to OP_BUILD_MEMBRANE,
    )

    private val OPCODE_FAMILY: Map<Int, CodonFamily> = mapOf(
        OP_START to CodonFamily.START,
        OP_HALT to CodonFamily.HALT,
        OP_PUSH_CONST to CodonFamily.STACK,
        OP_BUILD_PROTEIN to CodonFamily.SYNTHESIS,
        OP_BUILD_MEMBRANE to CodonFamily.SYNTHESIS,
        OP_BUILD_PIGMENT to CodonFamily.SYNTHESIS,
        OP_MOVE to CodonFamily.BEHAVIOR,
        OP_SIGNAL to CodonFamily.BEHAVIOR,
        OP_DIVIDE to CodonFamily.BEHAVIOR,
        OP_DIE to CodonFamily.BEHAVIOR,
        OP_FEED to CodonFamily.BEHAVIOR,
        OP_GROW_LSYSTEM to CodonFamily.MORPHOLOGY,
        OP_DIFFUSE to CodonFamily.MORPHOLOGY,
        OP_REACT to CodonFamily.MORPHOLOGY,
        OP_EMIT_MORPHOGEN to CodonFamily.MORPHOLOGY,
        OP_READ_MEM to CodonFamily.REGULATION,
        OP_WRITE_MEM to CodonFamily.REGULATION,
        OP_MODIFY_STATE to CodonFamily.REGULATION,
        OP_REGULATE to CodonFamily.REGULATION,
        OP_BIND to CodonFamily.REGULATION,
        OP_CALL_GENE to CodonFamily.CALL,
    )

    fun decode(codon: String): Int? = STANDARD_TABLE[codon.uppercase()]

    /** Family of a codon under the standard table, or `null` if unknown. */
    fun familyForCodon(codon: String): CodonFamily? =
        decode(codon)?.let { OPCODE_FAMILY[it] }

    /** Family of an opcode value, or `null` if unknown. */
    fun familyForOpcode(opcode: Int): CodonFamily? = OPCODE_FAMILY[opcode]

    /**
     * Pure scan used by the offline fallback (doc/08 §3.6): returns the 3-base
     * codon spans on a line together with their families. Non-DNA lines yield
     * nothing.
     */
    fun codonSpans(line: String): List<Pair<IntRange, CodonFamily>> {
        if (!isDnaLine(line)) return emptyList()
        return CODEN_RE.findAll(line)
            .filter { it.value.length == 3 }
            .mapNotNull { token -> familyForCodon(token.value)?.let { token.range to it } }
            .toList()
    }

    /** True if the line consists only of DNA bases and whitespace. */
    fun isDnaLine(line: String): Boolean =
        line.isNotEmpty() && line.all { it.isWhitespace() || it in "ACGTacgt" }

    private val CODEN_RE = Regex("\\S+")
}
