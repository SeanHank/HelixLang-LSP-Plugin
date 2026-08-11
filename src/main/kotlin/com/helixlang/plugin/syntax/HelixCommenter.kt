package com.helixlang.plugin.syntax

import com.intellij.lang.Commenter

/**
 * Commenter for HelixLang: `#` line comments (doc/04 §5.10). Block comments
 * via `#begin`/`#end` are a P1 follow-up.
 */
class HelixCommenter : Commenter {
    override fun getLineCommentPrefix(): String = "#"
    override fun getBlockCommentPrefix(): String? = null
    override fun getBlockCommentSuffix(): String? = null
    override fun getCommentedBlockCommentPrefix(): String? = null
    override fun getCommentedBlockCommentSuffix(): String? = null
}
