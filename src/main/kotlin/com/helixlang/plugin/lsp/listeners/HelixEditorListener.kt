package com.helixlang.plugin.lsp.listeners

import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.intellij.openapi.editor.Document
import com.intellij.openapi.editor.event.EditorFactoryEvent
import com.intellij.openapi.editor.event.EditorFactoryListener
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project

/**
 * Sends `didOpen` when a `.helix` file opens in an editor and `didClose` when
 * its last editor closes (doc/04 §4.5). Also attaches the hover controller.
 */
class HelixEditorListener(private val project: Project) : EditorFactoryListener {

    private val hoverController = com.helixlang.plugin.lsp.handlers.HelixHoverController(project)

    override fun editorCreated(event: EditorFactoryEvent) {
        val file = FileDocumentManager.getInstance().getFile(event.editor.document) ?: return
        if (file.fileType !is com.helixlang.plugin.filetype.HelixFileType) return
        event.editor.contentComponent.addMouseMotionListener(hoverController)
        event.editor.contentComponent.addMouseListener(hoverController)
        project.getService(com.helixlang.plugin.lsp.handlers.HelixInlayHintsController::class.java)
            ?.attach(event.editor)
        val manager = project.getService(HelixLspServerManager::class.java) ?: return
        val text: String = event.editor.document.text
        manager.notify(LspConstants.DID_OPEN, LspMessages.didOpen(file.url, text, 1))
    }

    override fun editorReleased(event: EditorFactoryEvent) {
        val file = FileDocumentManager.getInstance().getFile(event.editor.document) ?: return
        if (file.fileType !is com.helixlang.plugin.filetype.HelixFileType) return
        event.editor.contentComponent.removeMouseMotionListener(hoverController)
        event.editor.contentComponent.removeMouseListener(hoverController)
        project.getService(com.helixlang.plugin.lsp.handlers.HelixInlayHintsController::class.java)
            ?.detach(event.editor)
        val manager = project.getService(HelixLspServerManager::class.java) ?: return
        manager.notify(LspConstants.DID_CLOSE, LspMessages.didClose(file.url))
    }
}
