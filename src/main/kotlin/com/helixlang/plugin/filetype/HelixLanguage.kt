package com.helixlang.plugin.filetype

import com.intellij.lang.Language

/**
 * The HelixLang DSL language. A singleton [Language] with the id used by the
 * platform to bind file types, PSI, highlighters and every `language="Helix"`
 * extension in plugin.xml.
 */
object HelixLanguage : Language("Helix")
