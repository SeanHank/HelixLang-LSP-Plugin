package com.helixlang.plugin.actions

import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.fileEditor.FileDocumentManager
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import java.util.concurrent.TimeUnit

/**
 * Disassemble the current `.helix` file (doc/04 §6.2): sends
 * `workspace/executeCommand {command: "helix.disassemble", args:[uri]}` to the
 * server, or falls back to invoking the CLI directly when the server is offline.
 * Output is shown in a tool window (P1: dedicated "Bytecode" tab).
 */
class ShowDisassemblyAction : AnAction() {

    override fun update(event: AnActionEvent) {
        val file: VirtualFile? = event.getData(CommonDataKeys.VIRTUAL_FILE)
        event.presentation.isEnabledAndVisible =
            file != null && file.fileType is com.helixlang.plugin.filetype.HelixFileType
    }

    override fun actionPerformed(event: AnActionEvent) {
        val project: Project = event.getRequiredData(CommonDataKeys.PROJECT)
        val file: VirtualFile = event.getRequiredData(CommonDataKeys.VIRTUAL_FILE)
        val manager = project.getService(HelixLspServerManager::class.java)

        com.intellij.openapi.application.ApplicationManager.getApplication()
            .executeOnPooledThread {
                val disassembly: String
                if (manager != null && manager.isReady) {
                    val params = com.google.gson.JsonObject().apply {
                        addProperty("command", LspConstants.HELIX_DISASSEMBLE)
                        add("arguments", com.google.gson.JsonArray().apply { add(file.url) })
                    }
                    val future = manager.request(LspConstants.WORKSPACE_EXECUTE_COMMAND, params)
                    disassembly = try {
                        future.get(5000, TimeUnit.MILLISECONDS)
                            .getAsJsonObject("result")?.get("result")?.asString ?: ""
                    } catch (_: Exception) {
                        ""
                    }
                } else {
                    disassembly = cliDisassemble(file)
                }
                com.intellij.openapi.application.ApplicationManager.getApplication().invokeLater {
                    if (!project.isDisposed) DisassemblyToolWindow.show(project, file.name, disassembly)
                }
            }
    }

    private fun cliDisassemble(file: VirtualFile): String {
        return try {
            val doc = FileDocumentManager.getInstance().getDocument(file) ?: return ""
            val python = com.helixlang.plugin.lsp.HelixServerDescriptor
                .resolveInterpreter(com.helixlang.plugin.settings.HelixSettings.getInstance())
                ?: return ""
            val proc = ProcessBuilder(
                python.absolutePath, "-m", "helixlang", file.path, "--disassemble",
            ).redirectErrorStream(true).start()
            proc.inputStream.readBytes().decodeToString()
        } catch (_: Throwable) {
            ""
        }
    }
}
