package com.helixlang.plugin.filetype

import com.helixlang.plugin.icons.HelixIcons
import com.intellij.openapi.fileTypes.LanguageFileType

class HelixFileType private constructor() : LanguageFileType(HelixLanguage) {
    override fun getName(): String = "Helix"
    override fun getDescription(): String = "HelixLang DSL file"
    override fun getDefaultExtension(): String = "helix"
    override fun getIcon(): javax.swing.Icon = HelixIcons.FILE

    companion object {
        @JvmField
        val INSTANCE: HelixFileType = HelixFileType()
    }
}
