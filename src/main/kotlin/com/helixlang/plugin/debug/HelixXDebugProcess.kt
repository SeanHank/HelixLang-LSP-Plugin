package com.helixlang.plugin.debug

import com.google.gson.JsonObject
import com.helixlang.plugin.filetype.HelixFileType
import com.helixlang.plugin.filetype.HelixLanguage
import com.intellij.execution.process.ProcessHandler
import com.intellij.lang.Language
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.LocalFileSystem
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.xdebugger.XDebugProcess
import com.intellij.xdebugger.XDebugSession
import com.intellij.xdebugger.XDebuggerManager
import com.intellij.xdebugger.breakpoints.XBreakpointHandler
import com.intellij.xdebugger.breakpoints.XLineBreakpoint
import com.intellij.xdebugger.evaluation.XDebuggerEditorsProvider

/**
 * Bridges a DAP session over [HelixDapClient] to the XDebugger UI
 * (doc/04 §8): line breakpoints, continue/step commands, and the
 * frames/variables tree surfaced via [HelixDapSuspendContext].
 */
class HelixXDebugProcess(
    session: XDebugSession,
    private val client: HelixDapClient,
    private val processHandler: ProcessHandler,
    private val project: Project,
    private val scriptFile: VirtualFile,
) : XDebugProcess(session) {

    private val log = Logger.getInstance(HelixXDebugProcess::class.java)
    private val breakpointHandler = HelixDapBreakpointHandler()

    /** 0-based breakpoint lines per script URL, in insertion order. */
    private val breakpointLines = mutableMapOf<String, LinkedHashSet<Int>>()

    /** DAP breakpoint id → XLineBreakpoint, filled from setBreakpoints responses. */
    private val breakpointsById = mutableMapOf<Int, XLineBreakpoint<*>>()

    init {
        client.setEventListener { onDapEvent(it) }
        session.setPauseActionSupported(true)
    }

    // ------------------------------------------------------------------
    // XDebugProcess overrides
    // ------------------------------------------------------------------

    override fun getBreakpointHandlers(): Array<out XBreakpointHandler<*>> =
        arrayOf(breakpointHandler)

    override fun getEditorsProvider(): XDebuggerEditorsProvider = HELIX_EDITORS_PROVIDER

    override fun doGetProcessHandler(): ProcessHandler = processHandler

    override fun resume() {
        client.request("continue", DapArgs.threadRequest())
    }

    override fun startStepOver() {
        client.request("next", DapArgs.threadRequest())
    }

    override fun startStepInto() {
        client.request("stepIn", DapArgs.threadRequest())
    }

    override fun startStepOut() {
        client.request("stepOut", DapArgs.threadRequest())
    }

    override fun startPausing() {
        client.request("pause", DapArgs.threadRequest())
    }

    override fun stop() {
        try {
            client.request("disconnect")
        } catch (_: Throwable) {
        }
        try {
            client.close()
        } catch (_: Throwable) {
        }
        super.stop()
    }

    // ------------------------------------------------------------------
    // DAP events
    // ------------------------------------------------------------------

    private fun onDapEvent(event: DapEvent) {
        when (event.name) {
            "stopped" -> onStopped(event.body)
            "continued" -> getSession().sessionResumed()
            "terminated", "exited" -> ApplicationManager.getApplication().invokeLater {
                getSession().stop()
            }
            else -> Unit
        }
    }

    private fun onStopped(body: JsonObject) {
        val threadId = body.get("threadId")?.asInt ?: 1
        client.request("stackTrace", JsonObject().apply {
            addProperty("threadId", threadId)
        }).whenComplete { result, error ->
            if (error != null) {
                log.warn("stackTrace failed: ${error.message}")
                return@whenComplete
            }
            val frames = HelixDapStackFrame.fromBody(result, scriptFile, project, client)
            val context = HelixDapSuspendContext(frames)
            val hitId = body.get("hitBreakpointIds")?.asJsonArray
                ?.firstOrNull()?.takeIf { it.isJsonPrimitive }?.asInt
            val breakpoint = synchronized(breakpointsById) {
                hitId?.let { breakpointsById[it] }
            }
            ApplicationManager.getApplication().invokeLater {
                if (breakpoint != null) {
                    getSession().breakpointReached(breakpoint, null, context)
                } else {
                    getSession().positionReached(context)
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // breakpoints
    // ------------------------------------------------------------------

    private fun resolveFile(breakpoint: XLineBreakpoint<*>): VirtualFile? {
        val path = breakpoint.getPresentableFilePath()
        return LocalFileSystem.getInstance().findFileByPath(path)
    }

    private fun applyBreakpoints() {
        if (breakpointLines.isEmpty()) {
            client.request("setBreakpoints", DapArgs.setBreakpoints(
                scriptFile.path, scriptFile.name, emptyList()))
            return
        }
        val lines = breakpointLines[scriptFile.url] ?: return
        val ordered = lines.sorted()
        client.request("setBreakpoints", DapArgs.setBreakpoints(
            scriptFile.path, scriptFile.name, ordered)).whenComplete { result, error ->
            if (error != null) {
                log.warn("setBreakpoints failed: ${error.message}")
                return@whenComplete
            }
            val responded = result.getAsJsonArray("breakpoints")
            synchronized(breakpointsById) {
                breakpointsById.clear()
                for (i in 0 until responded.size()) {
                    val id = responded[i].asJsonObject.get("id")?.asInt ?: continue
                    val line = ordered.getOrNull(i) ?: continue
                    val bp = findBreakpoint(line)
                    if (bp != null) breakpointsById[id] = bp
                }
            }
        }
    }

    private fun findBreakpoint(line: Int): XLineBreakpoint<*>? {
        val manager = XDebuggerManager.getInstance(project).breakpointManager
        for (bp in manager.allBreakpoints) {
            if (bp is XLineBreakpoint<*> &&
                resolveFile(bp) == scriptFile &&
                bp.getLine() == line
            ) {
                return bp
            }
        }
        return null
    }

    private inner class HelixDapBreakpointHandler :
        XBreakpointHandler<XLineBreakpoint<HelixXLineBreakpointType.Properties>>(
            HelixXLineBreakpointType::class.java) {

        override fun registerBreakpoint(breakpoint: XLineBreakpoint<HelixXLineBreakpointType.Properties>) {
            val file = resolveFile(breakpoint) ?: return
            if (file != scriptFile) return
            synchronized(breakpointLines) {
                breakpointLines.getOrPut(file.url) { LinkedHashSet() } += breakpoint.getLine()
            }
            applyBreakpoints()
        }

        override fun unregisterBreakpoint(
            breakpoint: XLineBreakpoint<HelixXLineBreakpointType.Properties>,
            temporary: Boolean,
        ) {
            val file = resolveFile(breakpoint) ?: return
            if (file != scriptFile) return
            synchronized(breakpointLines) {
                breakpointLines[file.url]?.remove(breakpoint.getLine())
                if (breakpointLines[file.url].isNullOrEmpty()) breakpointLines.remove(file.url)
            }
            applyBreakpoints()
        }
    }

    companion object {
        private val HELIX_EDITORS_PROVIDER: XDebuggerEditorsProvider =
            object : XDebuggerEditorsProvider() {
                override fun getFileType(): com.intellij.openapi.fileTypes.FileType =
                    HelixFileType.INSTANCE

                override fun getSupportedLanguages(project: Project, position: com.intellij.xdebugger.XSourcePosition?): Collection<Language> =
                    listOf(HelixLanguage)
            }
    }
}
