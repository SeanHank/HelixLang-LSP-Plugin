package com.helixlang.plugin.debug

import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import com.intellij.xdebugger.breakpoints.XBreakpointProperties
import com.intellij.xdebugger.breakpoints.XLineBreakpoint
import com.intellij.xdebugger.breakpoints.XLineBreakpointType

/**
 * Line breakpoints on `.helix` files, forwarded to the DAP server
 * (`HelixXDebugProcess`). Registered as `xdebugger.breakpointType`.
 */
class HelixXLineBreakpointType :
    XLineBreakpointType<HelixXLineBreakpointType.Properties>(
        "HelixLine",
        "HelixLang line breakpoint",
    ) {

    class Properties : XBreakpointProperties<Properties>() {
        override fun getState(): Properties = this
        override fun loadState(state: Properties) {
        }
    }

    override fun canPutAt(file: VirtualFile, line: Int, project: Project): Boolean =
        file.extension?.equals("helix", ignoreCase = true) == true

    override fun createBreakpointProperties(file: VirtualFile, line: Int): Properties =
        Properties()

    override fun getDisplayText(breakpoint: XLineBreakpoint<Properties>): String =
        "line ${breakpoint.getLine() + 1}"
}
