package com.helixlang.plugin.psi

import com.intellij.openapi.util.TextRange

/**
 * Regex/tokenizer pass that builds the mini-PSI structure from source text
 * (doc/02 §6). Recognizes `#<kind> name=…`, `#regulate src -> tgt`, field
 * `key=value` pairs and `#end` terminators.
 *
 * Deliberately not the compiler: it may be wrong about edge cases; it exists
 * only to make navigation instant and available offline. The server's symbol
 * index is authoritative.
 */
object HelixPsiParser {

    private val ANNOTATION_RE = Regex("""^#([a-zA-Z_][a-zA-Z0-9_]*)\b(.*)$""")
    private val FIELD_RE = Regex("""([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*([^\s#]+)""")
    private val END_RE = Regex("""^\s*#end\b.*$""")

    fun parse(text: String): List<HelixAnnotation> {
        val lines = text.split("\n")
        val annotations = mutableListOf<HelixAnnotation>()
        var index = 0
        var startLine = -1
        var startOffset = -1
        var kind: String? = null
        val fields = mutableListOf<HelixField>()
        val symbols = mutableListOf<HelixSymbol>()

        fun closeAnnotation(endLine: Int) {
            val k = kind ?: return
            annotations.add(
                HelixAnnotation(
                    kind = k,
                    startLine = startLine,
                    startOffset = startOffset,
                    endLine = endLine,
                    fields = fields.toList(),
                    symbols = symbols.toList(),
                ))
            kind = null
            fields.clear()
            symbols.clear()
        }

        var offset = 0
        for ((i, line) in lines.withIndex()) {
            val trimmed = line.trimStart()
            val indent = line.length - trimmed.length
            val lineStart = offset + indent

            if (trimmed.isEmpty()) {
                offset += line.length + 1
                continue
            }

            if (END_RE.matches(trimmed)) {
                if (kind != null) closeAnnotation(i)
                offset += line.length + 1
                continue
            }

            val m = ANNOTATION_RE.find(trimmed)
            if (m != null) {
                if (kind != null) closeAnnotation(i - 1)
                kind = m.groupValues[1]
                startLine = i
                startOffset = lineStart
                val rest = m.groupValues[2]
                val newSymbols = parseSymbols(kind!!, rest, lineStart)
                symbols += newSymbols
                val newFields = parseFields(rest, lineStart)
                fields += newFields
                offset += line.length + 1
                continue
            }

            offset += line.length + 1
        }
        if (kind != null) closeAnnotation(lines.size - 1)
        return annotations
    }

    private fun parseSymbols(kind: String, rest: String, lineStart: Int): List<HelixSymbol> {
        val name = FIELD_RE.find(rest)?.takeIf { it.groups[1]?.value == "name" }
            ?.groups?.get(2)?.value ?: return emptyList()
        val nameOffset = rest.indexOf("name=")
        val rel = if (nameOffset >= 0) nameOffset else 0
        return listOf(
            HelixSymbol(
                name = name,
                kind = kind,
                definitionRange = TextRange.from(lineStart + rel + 5, name.length),
                line = 0,
            ))
    }

    private fun parseFields(rest: String, lineStart: Int): List<HelixField> {
        return FIELD_RE.findAll(rest).map { m ->
            HelixField(
                name = m.groups[1]!!.value,
                value = m.groups[2]!!.value,
                range = TextRange.from(lineStart + m.range.first, m.range.last - m.range.first + 1),
            )
        }.toList()
    }

    /** Look up every symbol name declared in the text (for fallback find-usages). */
    fun symbolNames(text: String): List<String> =
        parse(text).flatMap { it.symbols }.map { it.name }.distinct()
}
