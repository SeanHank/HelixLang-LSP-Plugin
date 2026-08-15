package com.helixlang.plugin.syntax

import com.intellij.openapi.editor.DefaultLanguageHighlighterColors
import com.intellij.openapi.editor.colors.TextAttributesKey

/**
 * Codon opcode families (doc/08 §3.1). Each codon decodes to an opcode; the
 * opcode belongs to one family; every family maps to a configurable color.
 * `id` is the LSP semantic-token type name emitted by the server and the key
 * used for per-family color overrides in [com.helixlang.plugin.settings.HelixSettings].
 */
enum class CodonFamily(val id: String, val label: String) {
    START("opcodeStart", "Start (ATG)"),
    HALT("opcodeHalt", "Halt (TAA / TAG / TGA)"),
    STACK("opcodeStack", "Stack (PUSH_CONST / DUP)"),
    SYNTHESIS("opcodeSynthesis", "Synthesis (protein / membrane / pigment)"),
    BEHAVIOR("opcodeBehavior", "Behavior (move / signal / divide / die / feed)"),
    MORPHOLOGY("opcodeMorphology", "Morphology (grow / diffuse / react / morphogen)"),
    REGULATION("opcodeRegulation", "Regulation (memory / state / regulate / bind)"),
    CALL("opcodeCall", "Call (CALL_GENE)"),
    ARITHMETIC("opcodeArithmetic", "Arithmetic (add / sub / mul / lt / not)"),
}

/** The `HELIX_CODON_*` color keys, registered in the color scheme. */
object CodonColorKeys {

    val START: TextAttributesKey =
        TextAttributesKey.createTextAttributesKey("HELIX_CODON_START", DefaultLanguageHighlighterColors.KEYWORD)
    val HALT: TextAttributesKey =
        TextAttributesKey.createTextAttributesKey("HELIX_CODON_HALT", DefaultLanguageHighlighterColors.KEYWORD)
    val STACK: TextAttributesKey =
        TextAttributesKey.createTextAttributesKey("HELIX_CODON_STACK", DefaultLanguageHighlighterColors.CONSTANT)
    val SYNTHESIS: TextAttributesKey =
        TextAttributesKey.createTextAttributesKey("HELIX_CODON_SYNTHESIS", DefaultLanguageHighlighterColors.FUNCTION_DECLARATION)
    val BEHAVIOR: TextAttributesKey =
        TextAttributesKey.createTextAttributesKey("HELIX_CODON_BEHAVIOR", DefaultLanguageHighlighterColors.CONSTANT)
    val MORPHOLOGY: TextAttributesKey =
        TextAttributesKey.createTextAttributesKey("HELIX_CODON_MORPHOLOGY", DefaultLanguageHighlighterColors.CLASS_NAME)
    val REGULATION: TextAttributesKey =
        TextAttributesKey.createTextAttributesKey("HELIX_CODON_REGULATION", DefaultLanguageHighlighterColors.INSTANCE_FIELD)
    val CALL: TextAttributesKey =
        TextAttributesKey.createTextAttributesKey("HELIX_CODON_CALL", DefaultLanguageHighlighterColors.IDENTIFIER)
    val ARITHMETIC: TextAttributesKey =
        TextAttributesKey.createTextAttributesKey("HELIX_CODON_ARITHMETIC", DefaultLanguageHighlighterColors.OPERATION_SIGN)

    private val KEY_BY_FAMILY: Map<CodonFamily, TextAttributesKey> = mapOf(
        CodonFamily.START to START,
        CodonFamily.HALT to HALT,
        CodonFamily.STACK to STACK,
        CodonFamily.SYNTHESIS to SYNTHESIS,
        CodonFamily.BEHAVIOR to BEHAVIOR,
        CodonFamily.MORPHOLOGY to MORPHOLOGY,
        CodonFamily.REGULATION to REGULATION,
        CodonFamily.CALL to CALL,
        CodonFamily.ARITHMETIC to ARITHMETIC,
    )

    private val FAMILY_BY_TOKEN_TYPE: Map<String, CodonFamily> =
        CodonFamily.values().associateBy { it.id }

    fun keyForFamily(family: CodonFamily): TextAttributesKey =
        KEY_BY_FAMILY.getValue(family)

    /** Map an LSP semantic-token type name (e.g. "opcodeStart") to its family. */
    fun familyForTokenType(tokenType: String): CodonFamily? = FAMILY_BY_TOKEN_TYPE[tokenType]

    fun keyForTokenType(tokenType: String): TextAttributesKey? =
        familyForTokenType(tokenType)?.let(::keyForFamily)

    val families: List<CodonFamily> = CodonFamily.values().toList()

    /**
     * Parse "#RRGGBB" (leading `#` optional) to a color, or `null` on garbage.
     * Pure, so the settings UI and the annotator share one implementation.
     */
    fun parseHexColor(hex: String?): java.awt.Color? {
        if (hex == null) return null
        val s = hex.removePrefix("#")
        if (s.length != 6) return null
        return try {
            java.awt.Color(
                s.substring(0, 2).toInt(16),
                s.substring(2, 4).toInt(16),
                s.substring(4, 6).toInt(16),
            )
        } catch (_: NumberFormatException) {
            null
        }
    }

    /**
     * doc/08 §3.3.3 resolution step: the settings override color, or `null` to
     * fall through to the IDE Color Scheme. `null` when custom colors are off
     * or the stored hex is malformed.
     */
    fun effectiveOverrideColor(customEnabled: Boolean, overrideHex: String?): java.awt.Color? =
        if (customEnabled) overrideHex?.let(::parseHexColor) else null
}
