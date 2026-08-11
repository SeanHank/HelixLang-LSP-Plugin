package com.helixlang.plugin.psi

import com.intellij.openapi.util.TextRange

/**
 * Lightweight structural model of one `#annotation … #end` block and the
 * symbols/fields it declares (doc/02 §6). Built lazily and read-only; the
 * editor never reparses PSI on typing.
 */
class HelixAnnotation(
    val kind: String,
    val startLine: Int,            // 0-based
    val startOffset: Int,
    val endLine: Int,              // 0-based, last line of the block
    val fields: List<HelixField>,
    val symbols: List<HelixSymbol>,
) {
    val range: TextRange = TextRange.from(startOffset, 1)
}

class HelixField(
    val name: String,
    val value: String,
    val range: TextRange,
)

class HelixSymbol(
    val name: String,
    val kind: String,              // "gene" | "promoter" | "type" | ...
    val definitionRange: TextRange,
    val line: Int,                 // 0-based
)
