package com.helixlang.plugin.lsp.handlers

import com.google.gson.JsonObject
import com.helixlang.plugin.filetype.HelixLanguage
import com.helixlang.plugin.icons.HelixIcons
import com.helixlang.plugin.lsp.HelixLspServerManager
import com.helixlang.plugin.lsp.protocol.LspConstants
import com.helixlang.plugin.lsp.protocol.LspMessages
import com.helixlang.plugin.psi.HelixFile
import com.helixlang.plugin.psi.HelixSymbol
import com.intellij.ide.structureView.StructureViewBuilder
import com.intellij.ide.structureView.StructureViewTreeElement
import com.intellij.ide.structureView.TextEditorBasedStructureViewModel
import com.intellij.ide.structureView.TreeBasedStructureViewBuilder
import com.intellij.ide.util.treeView.smartTree.NodeProvider
import com.intellij.ide.util.treeView.smartTree.TreeElement
import com.intellij.navigation.ItemPresentation
import com.intellij.navigation.NavigationItem
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.DumbAware
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.psi.PsiFile
import java.util.concurrent.TimeUnit

/**
 * Structure view (doc/04 §5.7): nodes from `textDocument/documentSymbol`
 * (server), falling back to the mini-PSI model when the server is offline.
 */
class HelixStructureViewBuilderFactory : com.intellij.lang.PsiStructureViewFactory, DumbAware {

    override fun getStructureViewBuilder(file: PsiFile): StructureViewBuilder? {
        if (file !is HelixFile) return null
        return object : TreeBasedStructureViewBuilder() {
            override fun createStructureViewModel(editor: Editor?): TextEditorBasedStructureViewModel {
                return HelixStructureViewModel(file, editor)
            }
        }
    }
}

/** One hierarchical document symbol decoded from the server. */
data class HelixServerSymbol(
    val name: String,
    val detail: String?,
    val kind: Int,
    val rangeStartLine: Int,
    val rangeStartChar: Int,
    val selectionStartLine: Int,
    val selectionStartChar: Int,
    val children: List<HelixServerSymbol>,
)

class HelixStructureViewModel(
    private val file: HelixFile,
    editor: Editor?,
) : TextEditorBasedStructureViewModel(editor, file) {

    private val serverSymbols: List<HelixServerSymbol> = fetchServerSymbols(file)

    private fun fetchServerSymbols(file: HelixFile): List<HelixServerSymbol> {
        val manager = file.project.getService(HelixLspServerManager::class.java) ?: return emptyList()
        if (!manager.isReady) return emptyList()
        val uri = file.virtualFile?.url ?: return emptyList()
        return try {
            val response = manager.request(
                LspConstants.DOCUMENT_SYMBOL,
                LspMessages.requestFull(LspConstants.DOCUMENT_SYMBOL, uri),
            ).get(1500, TimeUnit.MILLISECONDS)
            val array = response.getAsJsonObject("result").getAsJsonArray()
            decodeSymbols(array)
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun decodeSymbols(array: com.google.gson.JsonArray): List<HelixServerSymbol> {
        val out = mutableListOf<HelixServerSymbol>()
        for (element in array) {
            if (!element.isJsonObject) continue
            out.add(decodeSymbol(element.asJsonObject))
        }
        return out
    }

    private fun decodeSymbol(obj: JsonObject): HelixServerSymbol {
        val range = obj.getAsJsonObject("range").getAsJsonObject("start")
        val sel = obj.getAsJsonObject("selectionRange").getAsJsonObject("start")
        val children = mutableListOf<HelixServerSymbol>()
        obj.getAsJsonArray("children")?.let { arr ->
            for (child in arr) if (child.isJsonObject) children.add(decodeSymbol(child.asJsonObject))
        }
        return HelixServerSymbol(
            name = obj.get("name")?.asString ?: "?",
            detail = obj.get("detail")?.asString,
            kind = obj.get("kind")?.asInt ?: 0,
            rangeStartLine = range.get("line").asInt,
            rangeStartChar = range.get("character").asInt,
            selectionStartLine = sel.get("line").asInt,
            selectionStartChar = sel.get("character").asInt,
            children = children,
        )
    }

    override fun getRoot(): StructureViewTreeElement =
        if (serverSymbols.isNotEmpty()) {
            HelixServerRootTreeElement(file, serverSymbols)
        } else {
            HelixRootTreeElement(file, file.symbols)
        }

    override fun getSuitableClasses(): Array<Class<*>> = arrayOf(HelixFile::class.java)

    override fun getSorters(): Array<out com.intellij.ide.util.treeView.smartTree.Sorter> =
        arrayOf(com.intellij.ide.util.treeView.smartTree.Sorter.ALPHA_SORTER)

    override fun getNodeProviders(): Collection<NodeProvider<*>> = emptyList()
}

/** Root using server documentSymbol nodes. */
class HelixServerRootTreeElement(
    private val file: HelixFile,
    private val symbols: List<HelixServerSymbol>,
) : StructureViewTreeElement {

    override fun getValue(): Any = file

    override fun getPresentation(): ItemPresentation = object : ItemPresentation {
        override fun getPresentableText(): String = file.name ?: "HelixLang"
        override fun getIcon(unused: Boolean): javax.swing.Icon? = HelixIcons.FILE
    }

    override fun getChildren(): Array<TreeElement> =
        symbols.map { HelixServerSymbolTreeElement(file, it) }.toTypedArray()

    override fun navigate(requestFocus: Boolean) {
        (file as? NavigationItem)?.navigate(requestFocus)
    }

    override fun canNavigate(): Boolean = true
    override fun canNavigateToSource(): Boolean = true
}

class HelixServerSymbolTreeElement(
    private val file: HelixFile,
    private val symbol: HelixServerSymbol,
) : StructureViewTreeElement {

    override fun getValue(): Any = symbol

    override fun getPresentation(): ItemPresentation = object : ItemPresentation {
        override fun getPresentableText(): String =
            if (symbol.detail != null) "${symbol.name}  [${symbol.detail}]" else symbol.name
        override fun getIcon(unused: Boolean): javax.swing.Icon? = iconFor(symbol.kind)
    }

    override fun getChildren(): Array<TreeElement> =
        symbol.children.map { HelixServerSymbolTreeElement(file, it) }.toTypedArray()

    override fun navigate(requestFocus: Boolean) {
        val doc = file.viewProvider.document ?: return
        val virtualFile = file.virtualFile ?: return
        if (symbol.selectionStartLine >= doc.lineCount) return
        val offset = doc.getLineStartOffset(symbol.selectionStartLine) +
            symbol.selectionStartChar.coerceAtMost(doc.getLineEndOffset(symbol.selectionStartLine) - doc.getLineStartOffset(symbol.selectionStartLine))
        val descriptor = com.intellij.openapi.fileEditor.OpenFileDescriptor(file.project, virtualFile, offset)
        com.intellij.openapi.fileEditor.FileEditorManager.getInstance(file.project)
            .openTextEditor(descriptor, requestFocus)
    }

    override fun canNavigate(): Boolean = true
    override fun canNavigateToSource(): Boolean = true

    private fun iconFor(kind: Int): javax.swing.Icon? = when (kind) {
        12 -> HelixIcons.GENE      // function
        13 -> HelixIcons.PROMOTER  // variable
        else -> HelixIcons.FILE
    }
}

class HelixRootTreeElement(
    private val file: HelixFile,
    private val symbols: List<HelixSymbol>,
) : StructureViewTreeElement {

    override fun getValue(): Any = file

    override fun getPresentation(): ItemPresentation = object : ItemPresentation {
        override fun getPresentableText(): String = file.name ?: "HelixLang"
        override fun getIcon(unused: Boolean): javax.swing.Icon? = HelixIcons.FILE
    }

    override fun getChildren(): Array<TreeElement> =
        symbols.map { HelixSymbolTreeElement(file, it) }.toTypedArray()

    override fun navigate(requestFocus: Boolean) {
        val navigationItem = file as? NavigationItem ?: return
        navigationItem.navigate(requestFocus)
    }

    override fun canNavigate(): Boolean = true

    override fun canNavigateToSource(): Boolean = true
}

class HelixSymbolTreeElement(
    private val file: HelixFile,
    private val symbol: HelixSymbol,
) : StructureViewTreeElement {

    override fun getValue(): Any = symbol

    override fun getPresentation(): ItemPresentation = object : ItemPresentation {
        override fun getPresentableText(): String = symbol.name
        override fun getIcon(unused: Boolean): javax.swing.Icon? =
            if (symbol.kind == "gene") HelixIcons.GENE else HelixIcons.PROMOTER
    }

    override fun getChildren(): Array<TreeElement> = emptyArray()

    override fun navigate(requestFocus: Boolean) {
        val doc = file.viewProvider.document ?: return
        val virtualFile = file.virtualFile ?: return
        val offset = symbol.definitionRange.startOffset.coerceIn(0, doc.textLength)
        val descriptor = com.intellij.openapi.fileEditor.OpenFileDescriptor(file.project, virtualFile, offset)
        com.intellij.openapi.fileEditor.FileEditorManager.getInstance(file.project)
            .openTextEditor(descriptor, requestFocus)
    }

    override fun canNavigate(): Boolean = true
    override fun canNavigateToSource(): Boolean = true
}
