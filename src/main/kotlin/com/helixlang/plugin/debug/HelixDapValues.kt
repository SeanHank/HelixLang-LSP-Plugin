package com.helixlang.plugin.debug

import com.google.gson.JsonElement
import com.google.gson.JsonObject
import com.intellij.icons.AllIcons
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.ui.ColoredTextContainer
import com.intellij.ui.SimpleTextAttributes
import com.intellij.xdebugger.XDebuggerUtil
import com.intellij.xdebugger.XSourcePosition
import com.intellij.xdebugger.frame.XCompositeNode
import com.intellij.xdebugger.frame.XExecutionStack
import com.intellij.xdebugger.frame.XNamedValue
import com.intellij.xdebugger.frame.XStackFrame
import com.intellij.xdebugger.frame.XSuspendContext
import com.intellij.xdebugger.frame.XValueChildrenList
import com.intellij.xdebugger.frame.XValueGroup
import com.intellij.xdebugger.frame.XValueNode
import com.intellij.xdebugger.frame.XValuePlace

/** One call-stack frame from a DAP `stackTrace` response. */
class HelixDapStackFrame(
    private val frame: JsonObject,
    private val file: VirtualFile,
    private val project: Project,
    private val client: HelixDapClient,
) : XStackFrame() {

    val frameId: Int = frame.get("id")?.asInt ?: 1

    private val position: XSourcePosition? = run {
        val line = (frame.get("line")?.asInt ?: 1) - 1
        XDebuggerUtil.getInstance().createPosition(file, line.coerceAtLeast(0))
    }

    override fun getSourcePosition(): XSourcePosition? = position

    override fun getEqualityObject(): Any = frame

    override fun customizePresentation(renderer: ColoredTextContainer) {
        renderer.append(
            frame.get("name")?.asString ?: "<frame>",
            SimpleTextAttributes.REGULAR_ATTRIBUTES)
    }

    override fun computeChildren(node: XCompositeNode) {
        val future = client.request("scopes", DapArgs.scopes(frameId))
        future.whenComplete { result, error ->
            if (error != null) {
                node.setErrorMessage(error.message ?: "failed to load scopes")
            } else {
                val list = XValueChildrenList()
                for (scope in result.getAsJsonArray("scopes")) {
                    val o = scope.asJsonObject
                    val reference = o.get("variablesReference")?.asInt ?: 0
                    if (reference > 0) {
                        list.addTopGroup(
                            HelixDapScope(
                                o.get("name")?.asString ?: "Scope",
                                reference,
                                client))
                    }
                }
                node.addChildren(list, true)
            }
        }
    }

    companion object {
        fun fromBody(
            body: JsonObject,
            file: VirtualFile,
            project: Project,
            client: HelixDapClient,
        ): List<HelixDapStackFrame> =
            body.getAsJsonArray("stackFrames")
                .mapNotNull { it.takeIf(JsonElement::isJsonObject)?.asJsonObject }
                .map { HelixDapStackFrame(it, file, project, client) }
    }
}

/** A DAP `scopes` entry (Cell / GRN / Stack), shown as a value group. */
class HelixDapScope(
    name: String,
    private val variablesReference: Int,
    private val client: HelixDapClient,
) : XValueGroup(name) {

    override fun computeChildren(node: XCompositeNode) {
        val future = client.request("variables", DapArgs.variables(variablesReference))
        future.whenComplete { result, error ->
            if (error != null) {
                node.setErrorMessage(error.message ?: "failed to load variables")
            } else {
                val list = XValueChildrenList()
                for (variable in result.getAsJsonArray("variables")) {
                    list.add(variableOf(variable.asJsonObject, client))
                }
                node.addChildren(list, true)
            }
        }
    }

    companion object {
        fun variableOf(o: JsonObject, client: HelixDapClient): XNamedValue =
            HelixDapValue(
                o.get("name")?.asString ?: "?",
                o.get("type")?.asString,
                o.get("value")?.asString ?: "",
                o.get("variablesReference")?.asInt ?: 0,
                client)
    }
}

/** A single variable from a DAP `variables` response. */
class HelixDapValue(
    name: String,
    private val type: String?,
    private val value: String,
    private val variablesReference: Int,
    private val client: HelixDapClient,
) : XNamedValue(name) {

    override fun computePresentation(node: XValueNode, place: XValuePlace) {
        node.setPresentation(AllIcons.Debugger.Value, type, value, variablesReference > 0)
    }

    override fun computeChildren(node: XCompositeNode) {
        if (variablesReference <= 0) {
            node.addChildren(XValueChildrenList.EMPTY, false)
            return
        }
        val future = client.request("variables", DapArgs.variables(variablesReference))
        future.whenComplete { result, error ->
            if (error != null) {
                node.setErrorMessage(error.message ?: "failed to load variables")
            } else {
                val list = XValueChildrenList()
                for (variable in result.getAsJsonArray("variables")) {
                    list.add(HelixDapScope.variableOf(variable.asJsonObject, client))
                }
                node.addChildren(list, true)
            }
        }
    }
}

/** Execution stack for a suspended debug session. */
class HelixDapExecutionStack(
    name: String,
    private val frames: List<HelixDapStackFrame>,
) : XExecutionStack(name) {

    private val topFrame: XStackFrame? = frames.firstOrNull()

    override fun getTopFrame(): XStackFrame? = topFrame

    override fun computeStackFrames(startIndex: Int, container: XStackFrameContainer) {
        container.addStackFrames(frames.drop(startIndex), true)
    }
}

/** Suspend context backing the whole paused state. */
class HelixDapSuspendContext(
    frames: List<HelixDapStackFrame>,
) : XSuspendContext() {

    private val stack = HelixDapExecutionStack("main", frames)

    override fun getExecutionStacks(): Array<XExecutionStack> = arrayOf(stack)

    override fun getActiveExecutionStack(): XExecutionStack = stack
}
