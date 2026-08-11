package com.helixlang.plugin.run

import com.intellij.execution.RunConfigurationProducerService
import com.intellij.execution.RunManager
import com.intellij.execution.actions.ConfigurationContext
import com.intellij.execution.actions.RunConfigurationProducer
import com.intellij.openapi.util.Ref
import com.intellij.psi.PsiFile

/**
 * Creates a "HelixLang" run configuration from the active `.helix` file
 * (context menu / gutter, doc/04 §6.1).
 */
class HelixRunConfigurationProducer :
    RunConfigurationProducer<HelixRunConfiguration>(HelixRunConfigurationType.getInstance()) {

    override fun setupConfigurationFromContext(
        configuration: HelixRunConfiguration,
        context: ConfigurationContext,
        sourceElement: Ref<com.intellij.psi.PsiElement>,
    ): Boolean {
        val file: PsiFile = context.psiLocation?.containingFile ?: return false
        if (file.fileType !is com.helixlang.plugin.filetype.HelixFileType) return false
        configuration.script = file.virtualFile?.path ?: return false
        configuration.name = "Run ${file.virtualFile?.name}"
        return true
    }

    override fun isConfigurationFromContext(
        configuration: HelixRunConfiguration,
        context: ConfigurationContext,
    ): Boolean {
        val file = context.psiLocation?.containingFile?.virtualFile ?: return false
        return file.path == configuration.script
    }
}
