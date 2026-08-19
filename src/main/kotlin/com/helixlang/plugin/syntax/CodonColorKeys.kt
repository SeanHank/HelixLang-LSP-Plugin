package com.helixlang.plugin.syntax

import com.intellij.openapi.editor.DefaultLanguageHighlighterColors
import com.intellij.openapi.editor.colors.EditorColorsManager
import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.editor.markup.TextAttributes

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
     * Default foreground colors for each codon family (Darcula scheme).
     * Used as programmatic fallback when `additionalTextAttributes` XML
     * is not loaded — e.g. during dynamic plugin hot-reload, the XML is
     * not re-processed and `getAttributes(key)` returns only the parent
     * key's default (KEYWORD→CC7832, CONSTANT→9876AA, etc.).
     */
    private val DEFAULT_COLORS: Map<TextAttributesKey, java.awt.Color> = mapOf(
        START to java.awt.Color(0x6A8759),
        HALT to java.awt.Color(0xFF6B68),
        STACK to java.awt.Color(0x9876AA),
        SYNTHESIS to java.awt.Color(0x5B8DD6),
        BEHAVIOR to java.awt.Color(0xCC7832),
        MORPHOLOGY to java.awt.Color(0x45A3A3),
        REGULATION to java.awt.Color(0xC467E0),
        CALL to java.awt.Color(0x6897BB),
        ARITHMETIC to java.awt.Color(0xBBB529),
    )

    @Volatile
    private var registered = false

    /**
     * Programmatically register default foreground colors into the global
     * color scheme. Called once per plugin lifetime (cold start or hot-reload).
     *
     * On cold start, `additionalTextAttributes` XML already populated the
     * scheme with these values — calling again is harmless (same colors).
     * On hot-reload, the XML is NOT re-processed by the platform, so the
     * `HELIX_CODON_*` keys fall back to their parent keys (KEYWORD→CC7832,
     * CONSTANT→9876AA, etc.), producing wrong colors. This method injects
     * the correct foreground colors into the scheme, fixing hot-reload.
     */
    fun registerDefaultColorsIfNeeded() {
        if (registered) return
        val scheme = EditorColorsManager.getInstance().globalScheme
        for ((key, color) in DEFAULT_COLORS) {
            val attrs = TextAttributes()
            attrs.foregroundColor = color
            scheme.setAttributes(key, attrs)
        }
        registered = true
    }

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
