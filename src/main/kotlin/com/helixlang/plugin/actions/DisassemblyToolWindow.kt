package com.helixlang.plugin.actions

import com.intellij.openapi.components.Service
import com.intellij.openapi.components.ServiceManager
import com.intellij.openapi.editor.colors.EditorColorsManager
import com.intellij.openapi.fileEditor.FileEditorManager
import com.intellij.openapi.fileEditor.FileEditorManagerListener
import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowAnchor
import com.intellij.openapi.wm.ToolWindowManager
import com.intellij.psi.PsiDocumentManager
import com.intellij.ui.content.ContentFactory
import com.intellij.ui.content.ContentManagerEvent
import com.intellij.ui.content.ContentManagerListener
import javax.swing.JTextArea
import javax.swing.SwingConstants

/**
 * Read-only "Bytecode" tool window showing disassembly output (doc/04 §6.2).
 */
@Service
class DisassemblyToolWindow(private val project: Project) {

    private val textArea: JTextArea = JTextArea().apply {
        isEditable = false
        lineWrap = false
        tabSize = 4
        font = java.awt.Font(java.awt.Font.MONOSPACED, java.awt.Font.PLAIN, 12)
    }

    fun show(name: String, content: String) {
        textArea.text = content
        textArea.caretPosition = 0
        val toolWindow: ToolWindow = ToolWindowManager.getInstance(project)
            .getToolWindow(TOOL_WINDOW_ID) ?: createToolWindow()
        toolWindow.show()
        val factory = ContentFactory.getInstance()
        toolWindow.contentManager.removeAllContents(true)
        val content = factory.createContent(textArea, "Bytecode · $name", false)
        toolWindow.contentManager.addContent(content)
    }

    private fun createToolWindow(): ToolWindow {
        val manager = ToolWindowManager.getInstance(project)
        val toolWindow = manager.registerToolWindow(
            TOOL_WINDOW_ID,
            true,
            ToolWindowAnchor.BOTTOM,
            project,
        )
        return toolWindow
    }

    companion object {
        private const val TOOL_WINDOW_ID = "Helix Bytecode"

        @JvmStatic
        fun show(project: Project, name: String, content: String) {
            val service = project.getService(DisassemblyToolWindow::class.java)
            service.show(name, content)
        }
    }
}
