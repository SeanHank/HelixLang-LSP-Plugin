package com.helixlang.plugin.lsp

import com.helixlang.plugin.settings.HelixSettings
import com.intellij.execution.configurations.GeneralCommandLine
import com.intellij.openapi.diagnostic.Logger
import java.io.File

/**
 * Resolves the Python interpreter used to launch the language server and builds
 * the [GeneralCommandLine] (doc/04 §6.3).
 *
 * Resolution order:
 * 1. the user-chosen interpreter in [HelixSettings];
 * 2. the canonical reference interpreter `/opt/anaconda3/envs/helix/bin/python`
 *    when it exists and can import `helixlang`;
 * 3. a Python SDK configured in PyCharm with `helixlang` importable
 *    (`PythonSdkService` — only when the Python plugin is present);
 * 4. `python`/`python3` on `PATH`.
 */
object HelixServerDescriptor {

    private val log = Logger.getInstance(HelixServerDescriptor::class.java)

    /** Probe results keyed by interpreter path; a probe can take up to 15 s per
     *  candidate, so cache aggressively (invalidated only via [clearCache]). */
    private val importCache = java.util.concurrent.ConcurrentHashMap<String, Boolean>()

    val REFERENCE_INTERPRETER: File =
        File("/opt/anaconda3/envs/helix/bin/python")

    /** Bundled fallback envs probed after SDK resolution and before PATH. */
    private val BUNDLED_CANDIDATES: List<File> = listOf(
        File("/opt/anaconda3/envs/helix/bin/python3"),
        File("/opt/anaconda3/envs/helix/bin/python"),
        File("/usr/local/opt/helix/bin/python3"),
        File("/opt/helix/bin/python3"),
    )

    /** The interpreter that will be used, or null if none resolves. */
    fun resolveInterpreter(settings: HelixSettings): File? {
        settings.interpreterPath?.let { p ->
            val f = File(p)
            if (f.isFile && f.canExecute()) return f
        }
        if (REFERENCE_INTERPRETER.isFile && REFERENCE_INTERPRETER.canExecute()) {
            if (canImport(REFERENCE_INTERPRETER)) return REFERENCE_INTERPRETER
        }
        resolveFromPythonSdk()?.let { return it }
        for (candidate in BUNDLED_CANDIDATES) {
            if (candidate.isFile && candidate.canExecute() && canImport(candidate)) return candidate
        }
        for (name in listOf("python3", "python")) {
            val fromPath = findOnPath(name) ?: continue
            if (canImport(fromPath)) return fromPath
        }
        return null
    }

    /** Build the command line for a stdio transport. */
    fun serverCommand(settings: HelixSettings): GeneralCommandLine {
        val python = resolveInterpreter(settings)
            ?: throw IllegalStateException(
                "No Python interpreter with helixlang found. " +
                    "Install 'helixlang[lsp]' and pick the interpreter in Settings → HelixLang.")
        return GeneralCommandLine().apply {
            exePath = python.absolutePath
            addParameters("-m", "helixlang_lsp", "--stdio")
            workDirectory = File(System.getProperty("user.home"))
        }
    }

    /** True if `<python> -c "import helixlang, helixlang_lsp"` succeeds. */
    fun canImport(python: File): Boolean {
        if (!python.isFile || !python.canExecute()) return false
        val key = python.absolutePath
        importCache[key]?.let { return it }
        val ok = try {
            val proc = ProcessBuilder(
                python.absolutePath, "-c", "import helixlang, helixlang_lsp",
            ).redirectErrorStream(true).start()
            val exited = proc.waitFor(15, java.util.concurrent.TimeUnit.SECONDS)
            exited && proc.exitValue() == 0
        } catch (t: Throwable) {
            log.warn("interpreter check failed for $python: ${t.message}")
            false
        }
        importCache[key] = ok
        return ok
    }

    /** Forget cached probe results so the next [canImport] re-checks from scratch. */
    fun clearCache() {
        importCache.clear()
    }

    private fun findOnPath(name: String): File? {
        val path = System.getenv("PATH") ?: return null
        for (dir in path.split(File.pathSeparator)) {
            if (dir.isEmpty()) continue
            val candidate = File(dir, name)
            if (candidate.isFile && candidate.canExecute()) return candidate
        }
        return null
    }

    private fun resolveFromPythonSdk(): File? {
        return try {
            val serviceClass = Class.forName("com.jetbrains.python.sdk.PythonSdkService")
            val instance = serviceClass.getMethod("getInstance").invoke(null)
            val sdk = serviceClass.getMethod("getAllPythonSdks").invoke(instance)
            val interpreterPath = sdk.toString()
            File(interpreterPath).takeIf { it.isFile }
        } catch (_: Throwable) {
            null
        }
    }
}
