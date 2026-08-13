package com.helixlang.plugin.settings

import com.intellij.openapi.options.SearchableConfigurable
import com.intellij.openapi.ui.TextFieldWithBrowseButton
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBTextField
import com.intellij.ui.components.panels.VerticalBox
import javax.swing.JButton
import javax.swing.JComboBox
import javax.swing.JComponent
import javax.swing.JLabel
import javax.swing.JPanel

/**
 * "Languages & Frameworks → HelixLang" settings page (doc/04 §11).
 * Interpreter path + test button, transport choice, feature toggles and the
 * diagnostics debounce slider.
 */
class HelixSettingsConfigurable : SearchableConfigurable {

    private val settings = HelixSettings.getInstance()

    private val interpreter = TextFieldWithBrowseButton()
    private val testButton = JButton("Test interpreter")
    private val transport = JComboBox(arrayOf("stdio", "tcp"))
    private val tcpPort = JBTextField()
    private val trace = JBCheckBox("Write --trace transcript")
    private val diagnosticsEnabled = JBCheckBox("Diagnostics")
    private val semanticTokensEnabled = JBCheckBox("Semantic tokens")
    private val inlayHintsEnabled = JBCheckBox("Inlay hints")
    private val completionFallback = JBCheckBox("Completion fallback (offline)")
    private val debounce = JBCheckBox("Debounce diagnostics (200 ms)")
    private val validateRunVm = JBCheckBox("Validate by running the VM")
    private val status = JLabel(" ")

    override fun getId(): String = "helixlang.settings"

    override fun getDisplayName(): String = "HelixLang"

    override fun getHelpTopic(): String? = null

    override fun isModified(): Boolean =
        interpreter.text != (settings.interpreterPath ?: "") ||
            transport.selectedItem != settings.transport ||
            tcpPort.text != settings.tcpPort.toString() ||
            trace.isSelected != settings.trace ||
            diagnosticsEnabled.isSelected != settings.diagnosticsEnabled ||
            semanticTokensEnabled.isSelected != settings.semanticTokensEnabled ||
            inlayHintsEnabled.isSelected != settings.inlayHintsEnabled ||
            completionFallback.isSelected != settings.completionFallbackEnabled ||
            validateRunVm.isSelected != settings.validateRunVm

    override fun apply() {
        settings.interpreterPath = interpreter.text.ifBlank { null }
        settings.transport = transport.selectedItem as? String ?: "stdio"
        settings.tcpPort = tcpPort.text.toIntOrNull() ?: 8123
        settings.trace = trace.isSelected
        settings.diagnosticsEnabled = diagnosticsEnabled.isSelected
        settings.semanticTokensEnabled = semanticTokensEnabled.isSelected
        settings.inlayHintsEnabled = inlayHintsEnabled.isSelected
        settings.completionFallbackEnabled = completionFallback.isSelected
        settings.validateRunVm = validateRunVm.isSelected
    }

    override fun reset() {
        interpreter.text = settings.interpreterPath ?: ""
        transport.selectedItem = settings.transport
        tcpPort.text = settings.tcpPort.toString()
        trace.isSelected = settings.trace
        diagnosticsEnabled.isSelected = settings.diagnosticsEnabled
        semanticTokensEnabled.isSelected = settings.semanticTokensEnabled
        inlayHintsEnabled.isSelected = settings.inlayHintsEnabled
        completionFallback.isSelected = settings.completionFallbackEnabled
        validateRunVm.isSelected = settings.validateRunVm
    }

    override fun createComponent(): JComponent {
        testButton.addActionListener {
            val python = java.io.File(interpreter.text)
            testButton.isEnabled = false
            status.text = "Checking..."
            com.intellij.openapi.application.ApplicationManager.getApplication()
                .executeOnPooledThread {
                    com.helixlang.plugin.lsp.HelixServerDescriptor.clearCache()
                    val ok = com.helixlang.plugin.lsp.HelixServerDescriptor.canImport(python)
                    com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                        testButton.isEnabled = true
                        status.text =
                            if (ok) "OK: helixlang importable" else "FAILED: cannot import helixlang"
                    }
                }
        }
        val box = VerticalBox()
        box.add(row("Interpreter:", interpreter))
        box.add(testButton)
        box.add(status)
        box.add(row("Transport:", transport))
        box.add(row("TCP port:", tcpPort))
        box.add(trace)
        box.add(diagnosticsEnabled)
        box.add(semanticTokensEnabled)
        box.add(inlayHintsEnabled)
        box.add(completionFallback)
        box.add(debounce)
        box.add(validateRunVm)
        return box
    }

    private fun row(label: String, component: JComponent): JPanel {
        val row = JPanel(java.awt.BorderLayout())
        row.add(JLabel(label), java.awt.BorderLayout.WEST)
        row.add(component, java.awt.BorderLayout.CENTER)
        return row
    }

    override fun disposeUIResources() {}
}
