package com.helixlang.plugin.debug

import com.google.gson.JsonObject
import com.helixlang.plugin.icons.HelixIcons
import com.helixlang.plugin.lsp.HelixServerDescriptor
import com.helixlang.plugin.run.HelixRunConfiguration
import com.helixlang.plugin.settings.HelixSettings
import com.intellij.execution.ExecutionException
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.execution.configurations.RunProfile
import com.intellij.execution.configurations.RunnerSettings
import com.intellij.execution.executors.DefaultDebugExecutor
import com.intellij.execution.process.OSProcessHandler
import com.intellij.execution.process.ProcessHandler
import com.intellij.execution.runners.ExecutionEnvironment
import com.intellij.execution.runners.ProgramRunner
import com.intellij.execution.ui.ConsoleView
import com.intellij.execution.ui.ConsoleViewContentType
import com.intellij.execution.ui.RunContentDescriptor
import com.intellij.execution.filters.TextConsoleBuilderFactory
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.xdebugger.XDebugProcess
import com.intellij.xdebugger.XDebugProcessStarter
import com.intellij.xdebugger.XDebugSession
import com.intellij.xdebugger.XDebuggerManager
import com.intellij.xdebugger.breakpoints.XLineBreakpoint
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Program runner for the Debug executor (doc/04 §8). Starts the LSP server in
 * `--dap` mode, performs the initialize/launch/configurationDone handshake and
 * opens an XDebugger session bound to the DAP process.
 *
 * Registered `order="first"` so it wins over the generic debugger runner for
 * [HelixRunConfiguration] profiles; other configurations fall through to the
 * platform runner.
 */
class HelixDebuggerRunner : ProgramRunner<RunnerSettings> {

    private val log = Logger.getInstance(HelixDebuggerRunner::class.java)

    override fun getRunnerId(): String = DefaultDebugExecutor.EXECUTOR_ID

    override fun canRun(executorId: String, profile: RunProfile): Boolean =
        executorId == DefaultDebugExecutor.EXECUTOR_ID && profile is HelixRunConfiguration

    override fun execute(environment: ExecutionEnvironment) {
        val configuration = environment.runProfile as? HelixRunConfiguration ?: return
        val project = environment.project

        val python = configuration.interpreter?.let(::File)
            ?: HelixServerDescriptor.resolveInterpreter(HelixSettings.getInstance())
            ?: throw ExecutionException(
                "No Python interpreter with helixlang found. " +
                    "Set it in Settings → HelixLang.")

        val portFile = File.createTempFile("helixlang-dap", ".port")
        portFile.deleteOnExit()

        val commandLine = GeneralCommandLine().apply {
            exePath = python.absolutePath
            addParameters(
                "-m", "helixlang_lsp", "--dap",
                "--dap-port", "0",
                "--dap-port-file", portFile.absolutePath,
            )
            workDirectory = File(configuration.script).parentFile
                ?: File(System.getProperty("user.home"))
        }

        val processHandler = OSProcessHandler(commandLine)
        processHandler.startNotify()

        val console = TextConsoleBuilderFactory.getInstance()
            .createBuilder(project).console
        console.attachToProcess(processHandler)
        val descriptor = RunContentDescriptor(
            console,
            processHandler,
            console.component,
            configuration.name,
            HelixIcons.FILE)
        environment.callback?.processStarted(descriptor)

        startDebugSession(environment, configuration, processHandler, descriptor, portFile)
    }

    // ------------------------------------------------------------------
    // debug session bootstrap
    // ------------------------------------------------------------------

    private fun startDebugSession(
        environment: ExecutionEnvironment,
        configuration: HelixRunConfiguration,
        processHandler: ProcessHandler,
        descriptor: RunContentDescriptor,
        portFile: File,
    ) {
        val project = environment.project
        val scriptPath = configuration.script
        val scriptFile = LocalFileSystem.getInstance().findFileByPath(scriptPath)
            ?: LocalFileSystem.getInstance().findFileByIoFile(File(scriptPath))
        if (scriptFile == null) {
            log.warn("Debug: script file not found: $scriptPath")
            processHandler.destroyProcess()
            return
        }
        val initialBreakpoints = snapshotScriptBreakpoints(project, scriptFile)

        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                val port = awaitPortFile(portFile)
                val client = HelixDapClient.connect("127.0.0.1", port)
                handshake(client, configuration, initialBreakpoints)
                ApplicationManager.getApplication().invokeLater {
                    try {
                        XDebuggerManager.getInstance(project)
                            .startSessionAndShowTab(
                                "HelixLang",
                                descriptor,
                                object : XDebugProcessStarter() {
                                    override fun start(session: XDebugSession): XDebugProcess =
                                        HelixXDebugProcess(
                                            session, client, processHandler, project, scriptFile)
                                })
                    } catch (t: Throwable) {
                        log.warn("debug session start failed: ${t.message}")
                        try {
                            client.close()
                        } catch (_: Throwable) {
                        }
                        processHandler.destroyProcess()
                    }
                }
            } catch (t: Throwable) {
                log.warn("debug bootstrap failed: ${t.message}")
                processHandler.destroyProcess()
            }
        }
    }

    private fun handshake(
        client: HelixDapClient,
        configuration: HelixRunConfiguration,
        breakpoints: List<Pair<VirtualFile, Int>>,
    ) {
        client.request("initialize", JsonObject().apply {
            addProperty("adapterID", "helixlang")
            addProperty("clientID", "intellij")
        }).get(10, TimeUnit.SECONDS)

        val scriptPath = configuration.script
        client.request("launch", DapArgs.launch(
            scriptPath, File(scriptPath).parentFile?.absolutePath)).get(10, TimeUnit.SECONDS)

        val lines = breakpoints.map { it.second + 1 }
        client.request("setBreakpoints", DapArgs.setBreakpoints(
            scriptPath, File(scriptPath).name, lines)).get(10, TimeUnit.SECONDS)

        // Fire-and-forget: the server runs the program until the first
        // breakpoint or HALT, then emits `stopped`/`terminated`.
        client.request("configurationDone")
    }

    private fun awaitPortFile(portFile: File, timeoutMs: Long = 15_000): Int {
        val deadline = System.currentTimeMillis() + timeoutMs
        while (System.currentTimeMillis() < deadline) {
            val text = try {
                portFile.readText().trim()
            } catch (_: Throwable) {
                ""
            }
            if (text.isNotEmpty()) return text.toInt()
            Thread.sleep(50)
        }
        throw ExecutionException("DAP server did not report a port")
    }

    private fun snapshotScriptBreakpoints(
        project: Project,
        scriptFile: VirtualFile,
    ): List<Pair<VirtualFile, Int>> {
        val manager = XDebuggerManager.getInstance(project).breakpointManager
        val result = mutableListOf<Pair<VirtualFile, Int>>()
        for (bp in manager.allBreakpoints) {
            if (bp is XLineBreakpoint<*>) {
                val file = LocalFileSystem.getInstance()
                    .findFileByPath(bp.getPresentableFilePath())
                if (file == scriptFile) {
                    result += file to bp.getLine()
                }
            }
        }
        return result.sortedBy { it.second }
    }
}
