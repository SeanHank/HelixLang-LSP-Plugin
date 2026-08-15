package com.helixlang.plugin.syntax

import com.helixlang.plugin.icons.HelixIcons
import com.intellij.openapi.editor.colors.TextAttributesKey
import com.intellij.openapi.fileTypes.SyntaxHighlighter
import com.intellij.openapi.options.colors.AttributesDescriptor
import com.intellij.openapi.options.colors.ColorDescriptor
import com.intellij.openapi.options.colors.ColorSettingsPage
import javax.swing.Icon

/**
 * Editor → Color Scheme → HelixLang (doc/08 §3.4). Exposes the base HelixLang
 * tokens plus the nine `HELIX_CODON_*` opcode-family colors so users can
 * restyle codons per opcode family with full light/dark theme awareness.
 */
class HelixColorSettingsPage : ColorSettingsPage {

    override fun getDisplayName(): String = "HelixLang"

    override fun getIcon(): Icon? = HelixIcons.FILE

    override fun getAttributeDescriptors(): Array<AttributesDescriptor> {
        val base = arrayOf(
            AttributesDescriptor("Annotation (#gene, #end)", HelixSyntaxHighlighter.ANNOTATION),
            AttributesDescriptor("Field name", HelixSyntaxHighlighter.FIELD),
            AttributesDescriptor("Number", HelixSyntaxHighlighter.NUMBER),
            AttributesDescriptor("String", HelixSyntaxHighlighter.STRING),
            AttributesDescriptor("Comment", HelixSyntaxHighlighter.COMMENT),
            AttributesDescriptor("DNA base", HelixSyntaxHighlighter.BASE_A),
        )
        val codon = CodonColorKeys.families.map { family ->
            AttributesDescriptor("Codon · ${family.label}", CodonColorKeys.keyForFamily(family))
        }
        return base + codon
    }

    override fun getColorDescriptors(): Array<ColorDescriptor> = ColorDescriptor.EMPTY_ARRAY

    override fun getHighlighter(): SyntaxHighlighter = HelixSyntaxHighlighter()

    override fun getDemoText(): String =
        "#gene name=hello\n" +
            "<START>ATG</START> <SYNTHESIS>GCT</SYNTHESIS> <SYNTHESIS>GGT</SYNTHESIS> " +
            "<BEHAVIOR>GTA</BEHAVIOR> <HALT>TAA</HALT>\n" +
            "#regulate p_lac -> lacZ\n" +
            "#end\n"

    override fun getAdditionalHighlightingTagToDescriptorMap(): MutableMap<String, TextAttributesKey> =
        hashMapOf(
            "START" to CodonColorKeys.keyForFamily(CodonFamily.START),
            "HALT" to CodonColorKeys.keyForFamily(CodonFamily.HALT),
            "SYNTHESIS" to CodonColorKeys.keyForFamily(CodonFamily.SYNTHESIS),
            "BEHAVIOR" to CodonColorKeys.keyForFamily(CodonFamily.BEHAVIOR),
        )
}
