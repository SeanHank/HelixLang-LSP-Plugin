package com.helixlang.plugin.lsp

import com.google.gson.JsonObject
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.transport.LspTransport
import com.helixlang.plugin.lsp.transport.StdioTransport
import com.helixlang.plugin.lsp.transport.TcpTransport
import com.helixlang.plugin.settings.HelixSettings
import com.helixlang.plugin.syntax.CodonColorKeys
import com.intellij.openapi.Disposable
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.diagnostic.Logger
import com.intellij.codeInsight.daemon.DaemonCodeAnalyzer
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.project.Project
import java.util.concurrent.CompletableFuture
import java.util.concurrent.atomic.AtomicInteger

/**
 * Project-level manager for the language server process (doc/04 §4.4).
 *
 * Lifecycle: lazy start on first request; `initialize` + `initialized`; restart
 * with exponential backoff on unexpected exit; shutdown + dispose on project
 * close. All wire activity happens on pooled threads; UI mutations via
 * `invokeLater`.
 */
class HelixLspServerManager(private val project: Project) : Disposable {

    private val log = Logger.getInstance(HelixLspServerManager::class.java)

    enum class Status { STOPPED, STARTING, READY, RESTARTING }

    private val settings = HelixSettings.getInstance()
    private var transport: LspTransport? = null
    private var dispatcher: LspDispatcher? = null
    private val restartCount = AtomicInteger(0)
    private var lastRestartAt = 0L
    private var disposed = false

    @Volatile
    var status: Status = Status.STOPPED
        private set

    val isReady: Boolean get() = status == Status.READY

    /** Server version + pid, once initialized (for the settings readout). */
    @Volatile var serverInfo: String? = null
        private set

    fun start() {
        if (disposed) {
            log.warn("[Helix] start() called but manager is disposed")
            return
        }
        if (status != Status.STOPPED) {
            log.warn("[Helix] start() called but status=$status (not STOPPED)")
            return
        }
        log.info("[Helix] start() proceeding; status=STOPPED → STARTING")
        status = Status.STARTING
        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                doStart()
            } catch (t: Throwable) {
                log.warn("[Helix] server start failed: ${t.message}", t)
                status = Status.STOPPED
                scheduleRestart()
            }
        }
    }

    private fun doStart() {
        log.info("[Helix] doStart() invoked; transport=${settings.transport}")
        val localTransport: LspTransport = if (settings.transport == "tcp") {
            TcpTransport(settings.tcpHost, settings.tcpPort)
        } else {
            log.info("[Helix] doStart() resolving interpreter and building command...")
            StdioTransport(HelixServerDescriptor.serverCommand(settings))
        }
        val localDispatcher = LspDispatcher { message -> localTransport.send(message) }
        localTransport.setMessageConsumer { message ->
            localDispatcher.dispatch(message)
            onNotification(message)
        }
        localTransport.start()
        transport = localTransport
        dispatcher = localDispatcher

        val initialize = localDispatcher.request(
            LspConstants.INITIALIZE,
            com.helixlang.plugin.lsp.protocol.LspMessages.initialize(rootUriOf(project)),
            10_000,
        )
        initialize.whenComplete { result, error ->
            if (disposed) return@whenComplete
            if (error != null) {
                log.warn("server initialize failed: ${error.message}")
                val deadTransport = localTransport
                ApplicationManager.getApplication().executeOnPooledThread {
                    try {
                        deadTransport.dispose()
                    } catch (_: Throwable) {
                    }
                }
                status = Status.STOPPED
                scheduleRestart()
                return@whenComplete
            }
            serverInfo = runCatching {
                val info = result.getAsJsonObject("result").getAsJsonObject("serverInfo")
                val name = info.get("name")?.asString ?: "helixlang-lsp"
                val version = info.get("version")?.asString ?: "?"
                "$name $version"
            }.getOrNull()
            localDispatcher.notify(LspConstants.INITIALIZED, null)
            status = Status.READY
            log.info("[Helix] server READY: $serverInfo")
            ApplicationManager.getApplication().invokeLater {
                if (project.isDisposed) return@invokeLater
                CodonColorKeys.registerDefaultColorsIfNeeded()
                val fem = FileEditorManager.getInstance(project)
                for (editor in fem.allEditors) {
                    val vFile = editor.file ?: continue
                    if (vFile.fileType !is com.helixlang.plugin.filetype.HelixFileType) continue
                    val doc = FileDocumentManager.getInstance().getDocument(vFile) ?: continue
                    log.info("[Helix] re-sending didOpen for ${vFile.name} (${doc.textLength} chars)")
                    localDispatcher.notify(
                        LspConstants.DID_OPEN,
                        com.helixlang.plugin.lsp.protocol.LspMessages.didOpen(
                            vFile.url, doc.text, 1,
                        ),
                    )
                }
                DaemonCodeAnalyzer.getInstance(project).restart()
            }
        }
    }

    private fun onNotification(message: JsonObject) {
        val method = message.get("method")?.asString ?: return
        when (method) {
            LspConstants.PUBLISH_DIAGNOSTICS -> {
                val params = message.get("params")?.asJsonObject ?: return
                val uri = params.get("uri")?.asString ?: return
                diagnosticsCache[uri] = params.getAsJsonArray("diagnostics")
                ApplicationManager.getApplication().invokeLater {
                    project.messageBus.syncPublisher(HelixDiagnosticsListener.TOPIC)
                        .diagnosticsUpdated(uri)
                }
            }
            else -> Unit
        }
    }

    /** Cache of the latest `publishDiagnostics` payload per URI, for the annotator. */
    val diagnosticsCache: MutableMap<String, com.google.gson.JsonArray> = mutableMapOf()

    /** Cache of the latest semantic-token payload per URI, for the annotator. */
    val semanticTokensCache: MutableMap<String, com.google.gson.JsonObject> = mutableMapOf()

    /** Drop cached semantic tokens for [uri] after an edit; the annotator refetches. */
    fun invalidateSemanticTokens(uri: String) {
        semanticTokensCache.remove(uri)
    }

    private fun rootUriOf(project: Project): String {
        val basePath = project.basePath ?: return "file:///"
        return java.io.File(basePath).toURI().toString()
    }

    fun request(method: String, params: JsonObject?, timeoutMs: Long = 5000): CompletableFuture<JsonObject> {
        ensureStarted()
        val d = dispatcher ?: return CompletableFuture.failedFuture(
            IllegalStateException("server not available"))
        return d.request(method, params, timeoutMs)
    }

    fun notify(method: String, params: JsonObject?) {
        ensureStarted()
        dispatcher?.notify(method, params)
    }

    private fun ensureStarted() {
        if (status == Status.STOPPED || status == Status.RESTARTING) {
            start()
        }
    }

    private fun scheduleRestart() {
        if (disposed) return
        val now = System.currentTimeMillis()
        if (now - lastRestartAt > 10 * 60 * 1000) {
            restartCount.set(0)
        }
        lastRestartAt = now
        if (restartCount.incrementAndGet() > 5) {
            log.warn("too many server restarts; giving up until project reopen")
            status = Status.STOPPED
            return
        }
        val delayMs = (100L shl (restartCount.get() - 1)).coerceAtMost(10 * 60 * 1000L)
        status = Status.RESTARTING
        ApplicationManager.getApplication().executeOnPooledThread {
            try {
                Thread.sleep(delayMs)
            } catch (_: InterruptedException) {
            }
            if (!disposed) {
                status = Status.STOPPED
                start()
            }
        }
    }

    override fun dispose() {
        disposed = true
        try {
            dispatcher?.notify(LspConstants.SHUTDOWN, null)
            dispatcher?.notify(LspConstants.EXIT, null)
        } catch (_: Throwable) {
        }
        try {
            transport?.dispose()
        } catch (_: Throwable) {
        }
        transport = null
        dispatcher = null
        status = Status.STOPPED
    }

    companion object {
        @JvmStatic
        fun getInstance(project: Project): HelixLspServerManager =
            project.getService(HelixLspServerManager::class.java)
    }
}

/** Topic notified when a new publishDiagnostics payload arrives for a URI. */
object HelixDiagnosticsListener {
    val TOPIC: com.intellij.util.messages.Topic<Listener> =
        com.intellij.util.messages.Topic.create(
            "helixlang.diagnostics", Listener::class.java)

    interface Listener {
        fun diagnosticsUpdated(uri: String)
    }
}
