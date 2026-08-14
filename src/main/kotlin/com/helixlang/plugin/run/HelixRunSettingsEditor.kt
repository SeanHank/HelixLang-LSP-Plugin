package com.helixlang.plugin.run

import com.intellij.openapi.options.ConfigurationException
import com.intellij.openapi.options.SettingsEditor
import com.intellij.openapi.ui.TextFieldWithBrowseButton
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.ui.components.JBTextField
import java.awt.BorderLayout
import javax.swing.JComboBox
import javax.swing.JComponent
import javax.swing.JLabel
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
        val panel = JPanel(BorderLayout())
        val grid = com.intellij.ui.components.panels.VerticalBox()
        grid.add(row("Interpreter:", interpreter))
        grid.add(row("Script:", script))
        grid.add(row("Translation table:", table))
        grid.add(row("Backend:", backend))
        grid.add(row("Ticks override:", ticks))
        grid.add(row("Output format:", output))
        grid.add(disassemble)
        panel.add(grid, BorderLayout.NORTH)
        return panel
    }

    private fun row(label: String, component: JComponent): JPanel {
        val row = JPanel(BorderLayout())
        row.add(JLabel(label), BorderLayout.WEST)
        row.add(component, BorderLayout.CENTER)
        return row
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
