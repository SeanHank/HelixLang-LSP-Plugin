package com.helixlang.plugin.settings

import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.Service
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.util.xmlb.annotations.OptionTag

/**
 * Application-level persisted settings (doc/04 §11). Stored in
 * `helixlang-ide.xml`; per-project overrides are a P1 follow-up.
 */
@Service
@State(name = "HelixLangSettings", storages = [Storage("helixlang-ide.xml")])
class HelixSettings : PersistentStateComponent<HelixSettings.State> {

    data class State(
        @OptionTag("interpreterPath") var interpreterPath: String? = null,
        @OptionTag("transport") var transport: String = "stdio", // "stdio" | "tcp"
        @OptionTag("tcpPort") var tcpPort: Int = 8123,
        @OptionTag("tcpHost") var tcpHost: String = "127.0.0.1",
        @OptionTag("trace") var trace: Boolean = false,
        @OptionTag("diagnosticsEnabled") var diagnosticsEnabled: Boolean = true,
        @OptionTag("semanticTokensEnabled") var semanticTokensEnabled: Boolean = true,
        @OptionTag("inlayHintsEnabled") var inlayHintsEnabled: Boolean = true,
        @OptionTag("completionFallbackEnabled") var completionFallbackEnabled: Boolean = true,
        @OptionTag("debounceMs") var debounceMs: Int = 200,
        @OptionTag("validateRunVm") var validateRunVm: Boolean = false,
        @OptionTag("lspDebug") var lspDebug: Boolean = false,
    )

    @Volatile
    private var currentState: State = State()

    override fun getState(): State = currentState

    override fun loadState(stored: State) {
        currentState = stored
    }

    // Convenience accessors

    var interpreterPath: String?
        get() = currentState.interpreterPath
        set(value) {
            currentState.interpreterPath = value
        }

    var transport: String
        get() = currentState.transport
        set(value) {
            currentState.transport = value
        }

    var tcpPort: Int
        get() = currentState.tcpPort
        set(value) {
            currentState.tcpPort = value
        }

    var tcpHost: String
        get() = currentState.tcpHost
        set(value) {
            currentState.tcpHost = value
        }

    var trace: Boolean
        get() = currentState.trace
        set(value) {
            currentState.trace = value
        }

    var diagnosticsEnabled: Boolean
        get() = currentState.diagnosticsEnabled
        set(value) {
            currentState.diagnosticsEnabled = value
        }

    var semanticTokensEnabled: Boolean
        get() = currentState.semanticTokensEnabled
        set(value) {
            currentState.semanticTokensEnabled = value
        }

    var inlayHintsEnabled: Boolean
        get() = currentState.inlayHintsEnabled
        set(value) {
            currentState.inlayHintsEnabled = value
        }

    var completionFallbackEnabled: Boolean
        get() = currentState.completionFallbackEnabled
        set(value) {
            currentState.completionFallbackEnabled = value
        }

    var debounceMs: Int
        get() = currentState.debounceMs
        set(value) {
            currentState.debounceMs = value
        }

    var validateRunVm: Boolean
        get() = currentState.validateRunVm
        set(value) {
            currentState.validateRunVm = value
        }

    var lspDebug: Boolean
        get() = currentState.lspDebug
        set(value) {
            currentState.lspDebug = value
        }

    companion object {
        @JvmStatic
        fun getInstance(): HelixSettings =
            com.intellij.openapi.application.ApplicationManager.getApplication()
                .getService(HelixSettings::class.java)
    }
}
