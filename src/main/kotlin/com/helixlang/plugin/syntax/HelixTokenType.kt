package com.helixlang.plugin.syntax

import com.intellij.psi.tree.IElementType

/** Token element type produced by [HelixLexer]. */
class HelixTokenElement(debugName: String) : IElementType(debugName, com.helixlang.plugin.filetype.HelixLanguage)

object HelixTokenType {
    val ANNOTATION = HelixTokenElement("HELIX_ANNOTATION")
    val FIELD = HelixTokenElement("HELIX_FIELD")
    val OPERATOR = HelixTokenElement("HELIX_OPERATOR")
    val NUMBER = HelixTokenElement("HELIX_NUMBER")
    val STRING = HelixTokenElement("HELIX_STRING")
    val COMMENT = HelixTokenElement("HELIX_COMMENT")
    val BASE_A = HelixTokenElement("HELIX_BASE_A")
    val BASE_C = HelixTokenElement("HELIX_BASE_C")
    val BASE_G = HelixTokenElement("HELIX_BASE_G")
    val BASE_T = HelixTokenElement("HELIX_BASE_T")
    val BRACKET_L = HelixTokenElement("HELIX_BRACKET_L")
    val BRACKET_R = HelixTokenElement("HELIX_BRACKET_R")
    val SYMBOL = HelixTokenElement("HELIX_SYMBOL")
    val WHITE = HelixTokenElement("HELIX_WHITE")
    val BAD = HelixTokenElement("HELIX_BAD")
}
