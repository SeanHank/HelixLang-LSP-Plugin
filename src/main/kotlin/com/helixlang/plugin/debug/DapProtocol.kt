package com.helixlang.plugin.debug

import com.google.gson.JsonObject

/**
 * A single DAP `event` message received from the server (doc/04 §8). The most
 * relevant events for the XDebugger bridge are `stopped`, `continued` and
 * `terminated`.
 */
data class DapEvent(val name: String, val body: JsonObject)

/** Builds the arguments for a DAP request. */
object DapArgs {
    fun launch(program: String, cwd: String?): JsonObject =
        JsonObject().apply {
            addProperty("program", program)
            cwd?.let { addProperty("cwd", it) }
        }

    fun setBreakpoints(sourcePath: String, sourceName: String, lines: List<Int>): JsonObject =
        JsonObject().apply {
            add("source", JsonObject().apply {
                addProperty("name", sourceName)
                addProperty("path", sourcePath)
            })
            add("breakpoints", com.google.gson.JsonArray().apply {
                for (line in lines) {
                    add(JsonObject().apply { addProperty("line", line) })
                }
            })
        }

    fun threadRequest(): JsonObject =
        JsonObject().apply { addProperty("threadId", 1) }

    fun scopes(frameId: Int): JsonObject =
        JsonObject().apply { addProperty("frameId", frameId) }

    fun variables(reference: Int): JsonObject =
        JsonObject().apply { addProperty("variablesReference", reference) }
}
