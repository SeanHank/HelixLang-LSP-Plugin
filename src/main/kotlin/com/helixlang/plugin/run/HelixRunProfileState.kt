package com.helixlang.plugin.run

import com.intellij.execution.ExecutionException
import com.intellij.execution.Executor
import com.intellij.execution.configurations.CommandLineState
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.execution.configurations.RunConfigurationBase
import com.intellij.execution.process.OSProcessHandler
import com.intellij.execution.process.ProcessHandler
import com.intellij.execution.runners.ExecutionEnvironment
import com.helixlang.plugin.lsp.HelixServerDescriptor
import com.helixlang.plugin.settings.HelixSettings
import java.io.File

/**
 * Run configuration for a single `.helix` file (doc/04 §6.1). Field values map
 * to CLI arguments of `python -m helixlang <file>`.
 */
class HelixRunConfiguration(
    project: com.intellij.openapi.project.Project,
    factory: com.intellij.execution.configurations.ConfigurationFactory,
    name: String,
) : RunConfigurationBase<HelixRunProfileState>(project, factory, name) {

    var interpreter: String? = null
    var script: String = ""
    var table: String = "standard"
    var backend: String = "classic"
    var ticks: String = ""
    var output: String = "stdout"
    var disassembleFirst: Boolean = false

    override fun getConfigurationEditor(): com.intellij.openapi.options.SettingsEditor<out HelixRunConfiguration> =
        HelixRunSettingsEditor()

    override fun getState(executor: Executor, environment: ExecutionEnvironment): HelixRunProfileState =
        HelixRunProfileState(environment, this)
}

/**
 * Builds the `<python> -m helixlang <file> …` command line and streams the child
 * stdout/stderr into the run console via [OSProcessHandler].
 */
class HelixRunProfileState(
    environment: ExecutionEnvironment,
    private val configuration: HelixRunConfiguration,
) : CommandLineState(environment) {

    override fun startProcess(): ProcessHandler {
        val python = configuration.interpreter?.let(::File)
            ?: HelixServerDescriptor.resolveInterpreter(HelixSettings.getInstance())
            ?: throw ExecutionException(
                "No Python interpreter with helixlang found. " +
                    "Set it in Settings → HelixLang.")
        val commandLine = GeneralCommandLine().apply {
            exePath = python.absolutePath
            addParameters("-m", "helixlang", configuration.script)
            if (configuration.table != "standard") {
                addParameters("--table", configuration.table)
            }
            if (configuration.backend != "classic") {
                addParameters("--backend", configuration.backend)
            }
            if (configuration.ticks.isNotBlank()) {
                addParameters("--ticks", configuration.ticks)
            }
            when (configuration.output) {
                "csv" -> addParameters("--csv")
                "png" -> addParameters("--png", outputPrefix())
                "json" -> addParameters("--json")
                else -> Unit
            }
            if (configuration.disassembleFirst) {
                addParameters("--disassemble")
            }
            workDirectory = File(configuration.script).parentFile
                ?: File(System.getProperty("user.home"))
        }
        return OSProcessHandler(commandLine)
    }

    private fun outputPrefix(): String =
        File(configuration.script).nameWithoutExtension
}
