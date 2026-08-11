package com.helixlang.plugin.run

import com.helixlang.plugin.filetype.HelixFileType
import com.helixlang.plugin.icons.HelixIcons
import com.intellij.execution.configurations.ConfigurationFactory
import com.intellij.execution.configurations.ConfigurationTypeBase
import com.intellij.execution.configurations.RunConfiguration
import com.intellij.openapi.project.Project

/**
 * "HelixLang" run configuration type (doc/04 §6.1). Runs
 * `<python> -m helixlang <file>` with optional table/ticks/output/disassemble
 * overrides.
 */
class HelixRunConfigurationType : ConfigurationTypeBase(
    "HelixRunConfiguration",
    "HelixLang",
    "Run a HelixLang .helix file",
    HelixIcons.FILE,
) {

    private val factory: ConfigurationFactory = object : ConfigurationFactory(this) {
        override fun getId(): String = "Helix"

        override fun createTemplateConfiguration(project: Project): RunConfiguration =
            HelixRunConfiguration(project, this, "HelixLang")
    }

    init {
        addFactory(factory)
    }

    companion object {
        @JvmStatic
        fun getInstance(): HelixRunConfigurationType =
            com.intellij.execution.configurations.ConfigurationTypeUtil
                .findConfigurationType(HelixRunConfigurationType::class.java)
    }
}
