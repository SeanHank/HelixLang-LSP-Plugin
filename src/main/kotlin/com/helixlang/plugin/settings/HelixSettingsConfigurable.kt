package com.helixlang.plugin.settings

import com.helixlang.plugin.syntax.CodonColorKeys
import com.helixlang.plugin.syntax.CodonFamily
import com.intellij.openapi.editor.colors.EditorColorsManager
import com.intellij.openapi.options.SearchableConfigurable
import com.intellij.openapi.project.ProjectManager
import com.intellij.openapi.ui.TextFieldWithBrowseButton
import com.intellij.ui.ColorPicker
import com.intellij.ui.SeparatorFactory
import com.intellij.ui.components.JBCheckBox
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextField
import com.intellij.ui.components.panels.HorizontalBox
import com.intellij.ui.components.panels.VerticalBox
import com.intellij.util.ui.FormBuilder
import com.intellij.util.ui.JBUI
import java.awt.Color
import java.awt.Component
import java.awt.Dimension
import java.awt.GridBagConstraints
import java.awt.GridBagLayout
import javax.swing.JButton
import javax.swing.JComboBox
import javax.swing.JComponent
import javax.swing.JLabel
import javax.swing.JPanel
import javax.swing.JSlider

/**
 * "Languages & Frameworks → HelixLang" settings page (doc/04 §11, doc/08 §4).
 *
 * Layout: grouped, fixed-height rows (no vertical stretching); the **Test
 * interpreter** button sits to the right of the interpreter field in the same
 * row; a new **Codon colors** section lets users override the nine opcode-family
 * colors (`doc/08` §3.5).
 */
class HelixSettingsConfigurable : SearchableConfigurable {

    private val settings = HelixSettings.getInstance()

    private val interpreter = TextFieldWithBrowseButton()
    private val testButton = JButton("Test interpreter")
    private val testStatus = JLabel(" ")
    private val transport = JComboBox(arrayOf("stdio", "tcp"))
    private val tcpPort = JBTextField()
    private val trace = JBCheckBox("Write --trace transcript")
    private val diagnosticsEnabled = JBCheckBox("Diagnostics")
    private val semanticTokensEnabled = JBCheckBox("Semantic tokens")
    private val inlayHintsEnabled = JBCheckBox("Inlay hints")
    private val completionFallback = JBCheckBox("Completion fallback (offline)")
    private val debounce = JSlider(50, 2000, 200)
    private val debounceValue = JLabel("200 ms")
    private val validateRunVm = JBCheckBox("Validate by running the VM")
    private val codonColorCustom = JBCheckBox("Custom codon colors")
    private val resetAllColors = JButton("Reset all")
    private val colorRows: Map<CodonFamily, ColorRow> =
        CodonColorKeys.families.associateWith { ColorRow(it) }
    private val codonPreview = JLabel(" ")

    /** Pending per-family overrides (`family.id -> "#RRGGBB"`), applied on Apply. */
    private val pendingColorOverrides = mutableMapOf<String, String>()

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
            debounce.value != settings.debounceMs ||
            validateRunVm.isSelected != settings.validateRunVm ||
            codonColorCustom.isSelected != settings.codonColorCustom ||
            pendingColorOverrides != settings.codonColorOverrides

    override fun apply() {
        settings.interpreterPath = interpreter.text.ifBlank { null }
        settings.transport = transport.selectedItem as? String ?: "stdio"
        settings.tcpPort = tcpPort.text.toIntOrNull() ?: 8123
        settings.trace = trace.isSelected
        settings.diagnosticsEnabled = diagnosticsEnabled.isSelected
        settings.semanticTokensEnabled = semanticTokensEnabled.isSelected
        settings.inlayHintsEnabled = inlayHintsEnabled.isSelected
        settings.completionFallbackEnabled = completionFallback.isSelected
        settings.debounceMs = debounce.value
        settings.validateRunVm = validateRunVm.isSelected
        settings.codonColorCustom = codonColorCustom.isSelected
        settings.codonColorOverrides =
            pendingColorOverrides.filterValues { CodonColorKeys.parseHexColor(it) != null }.toMap()
        rehighlightOpenHelixEditors()
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
        debounce.value = settings.debounceMs
        debounceValue.text = "${settings.debounceMs} ms"
        validateRunVm.isSelected = settings.validateRunVm
        codonColorCustom.isSelected = settings.codonColorCustom
        pendingColorOverrides.clear()
        pendingColorOverrides.putAll(settings.codonColorOverrides)
        colorRows.forEach { (family, row) -> refreshPicker(family, row) }
        refreshPreview()
    }

    override fun createComponent(): JComponent {
        testButton.addActionListener { runInterpreterTest() }
        tcpPort.isEnabled = transport.selectedItem == "tcp"
        transport.addActionListener {
            tcpPort.isEnabled = transport.selectedItem == "tcp"
        }
        debounce.addChangeListener {
            debounceValue.text = "${debounce.value} ms"
        }
        codonColorCustom.addActionListener { refreshPreview() }
        resetAllColors.addActionListener {
            pendingColorOverrides.clear()
            colorRows.forEach { (family, row) -> refreshPicker(family, row) }
            refreshPreview()
        }

        val root = VerticalBox()

        // ── General ──
        val general = FormBuilder.createFormBuilder()
        val interpreterRow = HorizontalBox().apply {
            add(interpreter)
            add(testButton)
        }
        general.addLabeledComponent("Interpreter:", interpreterRow)
        general.addComponentToRightColumn(testStatus)
        root.add(section("General", general.getPanel()))

        // ── Language server ──
        val server = FormBuilder.createFormBuilder()
        server.addLabeledComponent("Transport:", buildTransportRow())
        server.addComponent(trace)
        root.add(section("Language server", server.getPanel()))

        // ── Features ──
        val features = FormBuilder.createFormBuilder()
        features.addComponent(HorizontalBox().apply {
            add(diagnosticsEnabled)
            add(semanticTokensEnabled)
        })
        features.addComponent(HorizontalBox().apply {
            add(inlayHintsEnabled)
            add(completionFallback)
        })
        val debounceRow = HorizontalBox().apply {
            add(debounce)
            add(debounceValue)
        }
        features.addLabeledComponent("Debounce:", debounceRow)
        features.addComponent(validateRunVm)
        root.add(section("Features", features.getPanel()))

        // ── Codon colors ──
        val colors = FormBuilder.createFormBuilder()
        colors.addComponent(buildCodonColorsGrid())
        colors.addLabeledComponent("Preview:", codonPreview)
        root.add(section("Codon colors", colors.getPanel()))

        val scroll = JBScrollPane(root)
        scroll.border = JBUI.Borders.empty()
        return scroll
    }

    private fun section(title: String, body: JComponent): JComponent {
        val box = VerticalBox()
        box.add(SeparatorFactory.createSeparator(title, null))
        box.add(body)
        return box
    }

    /**
     * `[stdio ▾]  TCP port: [8123]` on one line. Uses GridBagLayout so the
     * "TCP port:" label is vertically centered against the field (the bare
     * label in a Box appears shifted up against a taller field).
     */
    private fun buildTransportRow(): JComponent {
        val row = JPanel(GridBagLayout())
        row.isOpaque = false
        val portLabel = JLabel("TCP port:")
        val portLabelHeight = maxOf(transport.preferredSize.height, tcpPort.preferredSize.height)
        portLabel.preferredSize = Dimension(portLabel.preferredSize.width, portLabelHeight)
        portLabel.alignmentY = Component.CENTER_ALIGNMENT

        val transportConstraints = GridBagConstraints()
        transportConstraints.gridy = 0
        transportConstraints.anchor = GridBagConstraints.WEST
        transportConstraints.insets = JBUI.insetsRight(JBUI.scale(8))
        row.add(transport, transportConstraints)

        val labelConstraints = GridBagConstraints()
        labelConstraints.gridy = 0
        labelConstraints.anchor = GridBagConstraints.CENTER
        labelConstraints.insets = JBUI.insetsRight(JBUI.scale(8))
        row.add(portLabel, labelConstraints)

        val portConstraints = GridBagConstraints()
        portConstraints.gridy = 0
        portConstraints.anchor = GridBagConstraints.WEST
        portConstraints.fill = GridBagConstraints.HORIZONTAL
        portConstraints.weightx = 1.0
        row.add(tcpPort, portConstraints)
        return row
    }

    /**
     * Codon-colors area as one grid: the `Custom codon colors` checkbox and
     * `Reset all` in a two-column header (aligned with the label / picker
     * columns), then one aligned row per family:
     * `Start (ATG)  [FFFFFF]  [Reset]`
     */
    private fun buildCodonColorsGrid(): JComponent {
        val grid = JPanel(GridBagLayout())
        grid.isOpaque = false
        val pickerWidth = JBUI.scale(120)
        val resetWidth = JBUI.scale(80)

        var y = 0
        val headerLabel = GridBagConstraints()
        headerLabel.gridy = y
        headerLabel.gridx = 0
        headerLabel.anchor = GridBagConstraints.WEST
        headerLabel.insets = JBUI.insets(0, 0, JBUI.scale(4), JBUI.scale(12))
        grid.add(codonColorCustom, headerLabel)

        val headerReset = GridBagConstraints()
        headerReset.gridy = y
        headerReset.gridx = 1
        headerReset.anchor = GridBagConstraints.WEST
        headerReset.insets = JBUI.insets(0, 0, JBUI.scale(4), JBUI.scale(12))
        grid.add(resetAllColors, headerReset)

        for (family in CodonColorKeys.families) {
            y++
            val row = colorRows.getValue(family)
            val label = JLabel(family.label)
            row.picker.preferredSize = Dimension(pickerWidth, row.picker.preferredSize.height)
            row.reset.preferredSize = Dimension(resetWidth, row.reset.preferredSize.height)

            val labelConstraints = GridBagConstraints()
            labelConstraints.gridy = y
            labelConstraints.gridx = 0
            labelConstraints.anchor = GridBagConstraints.WEST
            labelConstraints.insets = JBUI.insets(0, 0, JBUI.scale(4), JBUI.scale(12))
            grid.add(label, labelConstraints)

            val pickerConstraints = GridBagConstraints()
            pickerConstraints.gridy = y
            pickerConstraints.gridx = 1
            pickerConstraints.anchor = GridBagConstraints.WEST
            pickerConstraints.insets = JBUI.insets(0, 0, JBUI.scale(4), JBUI.scale(12))
            grid.add(row.picker, pickerConstraints)

            val resetConstraints = GridBagConstraints()
            resetConstraints.gridy = y
            resetConstraints.gridx = 2
            resetConstraints.anchor = GridBagConstraints.WEST
            resetConstraints.insets = JBUI.insets(0, 0, JBUI.scale(4), 0)
            grid.add(row.reset, resetConstraints)
        }
        return grid
    }

    private fun runInterpreterTest() {
        val python = java.io.File(interpreter.text)
        testButton.isEnabled = false
        testStatus.text = "Checking..."
        com.intellij.openapi.application.ApplicationManager.getApplication()
            .executeOnPooledThread {
                com.helixlang.plugin.lsp.HelixServerDescriptor.clearCache()
                val ok = com.helixlang.plugin.lsp.HelixServerDescriptor.canImport(python)
                com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                    testButton.isEnabled = true
                    testStatus.text =
                        if (ok) "OK: helixlang importable" else "FAILED: cannot import helixlang"
                }
            }
    }

    private fun refreshPicker(family: CodonFamily, row: ColorRow) {
        val color = CodonColorKeys.parseHexColor(pendingColorOverrides[family.id]) ?: schemeColor(family)
        row.picker.text = color?.let(::toHex) ?: "N/A"
        row.picker.foreground = color ?: Color.BLACK
        row.picker.toolTipText = color?.let(::toHex) ?: "Using IDE Color Scheme"
    }

    private fun toHex(color: Color): String =
        "%02X%02X%02X".format(color.red, color.green, color.blue)

    private fun refreshPreview() {
        val html = buildString {
            append("<html>")
            append(colorSpan("ATG", CodonFamily.START)).append(' ')
            append(colorSpan("GCT", CodonFamily.SYNTHESIS)).append(' ')
            append(colorSpan("GGT", CodonFamily.SYNTHESIS)).append(' ')
            append(colorSpan("GTA", CodonFamily.BEHAVIOR)).append(' ')
            append(colorSpan("TAA", CodonFamily.HALT))
            append("</html>")
        }
        codonPreview.text = html
    }

    private fun colorSpan(codon: String, family: CodonFamily): String {
        if (!codonColorCustom.isSelected) return codon
        val color = effectiveColor(family) ?: return codon
        val hex = "#%02x%02x%02x".format(color.red, color.green, color.blue)
        return "<font color='$hex'>$codon</font>"
    }

    private fun effectiveColor(family: CodonFamily): Color? =
        CodonColorKeys.parseHexColor(pendingColorOverrides[family.id]) ?: schemeColor(family)

    private fun schemeColor(family: CodonFamily): Color? =
        EditorColorsManager.getInstance().globalScheme
            .getAttributes(CodonColorKeys.keyForFamily(family))?.foregroundColor

    /** doc/08 §3.7: re-run highlight passes so new colors apply without a restart. */
    private fun rehighlightOpenHelixEditors() {
        for (project in ProjectManager.getInstance().openProjects) {
            com.intellij.codeInsight.daemon.DaemonCodeAnalyzer.getInstance(project).restart()
        }
    }

    override fun disposeUIResources() {}

    /** One interactive row of the Codon colors table. */
    private inner class ColorRow(val family: CodonFamily) {
        val picker: JButton = JButton("Color Picker")
        val reset: JButton = JButton("Reset")

        init {
            picker.isOpaque = false
            picker.isContentAreaFilled = false
            picker.isBorderPainted = true
            picker.isFocusPainted = false
            picker.isRolloverEnabled = false
            picker.toolTipText = "Click to pick a color"
            picker.addActionListener {
                val current = CodonColorKeys.parseHexColor(pendingColorOverrides[family.id])
                    ?: schemeColor(family) ?: Color.WHITE
                val picked = ColorPicker.showDialog(
                    picker,
                    "Codon color — ${family.label}",
                    current,
                    false,
                    emptyList(),
                    false,
                )
                if (picked != null) {
                    pendingColorOverrides[family.id] =
                        String.format("#%02X%02X%02X", picked.red, picked.green, picked.blue)
                }
                refreshPicker(family, this)
                refreshPreview()
            }
            reset.addActionListener {
                pendingColorOverrides.remove(family.id)
                refreshPicker(family, this)
                refreshPreview()
            }
        }
    }
}
