package com.helixlang.plugin.lsp.listeners

import com.helixlang.plugin.lsp.HelixLspServerManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.project.ProjectManagerListener

/** Starts the language server when a HelixLang project opens (doc/04 §4.4). */
class HelixProjectOpenedListener : ProjectManagerListener {

    override fun projectOpened(project: Project) {
        if (project.isDisposed) return
        HelixLspServerManager.getInstance(project).start()
    }

    override fun projectClosing(project: Project) {
        val manager = project.getService(HelixLspServerManager::class.java)
            ?: return
        manager.dispose()
    }
}
