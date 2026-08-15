package com.helixlang.plugin.run

import com.intellij.openapi.options.ConfigurationException
import com.intellij.openapi.options.SettingsEditor
import com.intellij.openapi.ui.TextFieldWithBrowseButton
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.ui.components.JBTextField
import javax.swing.JComboBox
import javax.swing.JComponent
import javax.swing.JPanel
import javax.swing.JCheckBox

/** Simple settings editor for a [HelixRunConfiguration]. */
class HelixRunSettingsEditor : SettingsEditor<HelixRunConfiguration>() {

    private val interpreter = TextFieldWithBrowseButton()
    private val script = TextFieldWithBrowseButton()
    private val table = JComboBox(arrayOf("standard", "mito_vertebrate", "ciliate"))
    private val backend = JComboBox(arrayOf(
        "classic", "whole_cell", "population", "fba", "calibration", "benchmark"))
    private val ticks = JBTextField()
    private val output = JComboBox(arrayOf("stdout", "csv", "png", "json"))
    private val disassemble = JCheckBox("Disassemble first")
    private val panel: JPanel = buildPanel()

    private fun buildPanel(): JPanel {
        val builder = com.intellij.util.ui.FormBuilder.createFormBuilder()
        builder.addLabeledComponent("Interpreter:", interpreter)
        builder.addLabeledComponent("Script:", script)
        builder.addLabeledComponent("Translation table:", table)
        builder.addLabeledComponent("Backend:", backend)
        builder.addLabeledComponent("Ticks override:", ticks)
        builder.addLabeledComponent("Output format:", output)
        builder.addComponent(disassemble)
        return builder.getPanel()
    }

    override fun resetEditorFrom(configuration: HelixRunConfiguration) {
        interpreter.text = configuration.interpreter ?: ""
        script.text = configuration.script
        table.selectedItem = configuration.table
        backend.selectedItem = configuration.backend
        ticks.text = configuration.ticks
        output.selectedItem = configuration.output
        disassemble.isSelected = configuration.disassembleFirst
    }

    override fun applyEditorTo(configuration: HelixRunConfiguration) {
        configuration.interpreter = interpreter.text.ifBlank { null }
        configuration.script = script.text
        configuration.table = table.selectedItem as? String ?: "standard"
        configuration.backend = backend.selectedItem as? String ?: "classic"
        configuration.ticks = ticks.text
        configuration.output = output.selectedItem as? String ?: "stdout"
        configuration.disassembleFirst = disassemble.isSelected
    }

    override fun createEditor(): JComponent = panel

    override fun disposeEditor() {}
}
