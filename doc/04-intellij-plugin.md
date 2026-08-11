# 04 — The IntelliJ/PyCharm Plugin (LSP Client)

> Complete design of the Kotlin IntelliJ Platform plugin that runs inside
> PyCharm 2022.2 and later, connects to the Helix language server, and renders
> HelixLang editing features.

---

## 1. Build baseline & toolchain

The plugin targets **PyCharm Community/Professional 2022.2 (build 222)** as the
minimum baseline and remains forward compatible.

| Component | Version | Rationale |
|-----------|---------|-----------|
| IntelliJ Platform Gradle Plugin | **1.14.x** | Last line supporting build 222 toolchains; IPGP 2.x requires 2023.3+. |
| Kotlin | **1.8.22** | Stable with IPGP 1.14; JVM 17 toolchain. |
| Gradle | **7.6.x** | Compatible with IPGP 1.14 and Java 17. |
| JVM target | 17 | Matches PyCharm 2022.2+ runtime. |
| IntelliJ dependency | `PY-222.3345.118` (PyCharm Community) | `intellij { type = "PY" }`; professional-compatible artifact. |
| Plugin SDK deps | `com.intellij.modules.platform`, `com.intellij.modules.lang`, `com.intellij.modules.python` | Python-module integration for interpreter auto-detection and run configurations. |

`gradle.properties`:

```properties
org.gradle.jvmargs=-Xmx2g
kotlin.stdlib.default.dependency=true
intellij.version=PY-222.3345.118
intellij.type=PY
```

Because we build against 222, all newer-API usages are version-guarded
(see §9). This is the single most important compatibility rule in the project.

## 2. plugin.xml

```xml
<idea-plugin>
  <id>com.helixlang.ide</id>
  <name>HelixLang</name>
  <vendor url="https://github.com/SeanHank/HelixLang-LSP-Plugin">Sean Hank</vendor>
  <description><![CDATA[
    Language Server Protocol support for the HelixLang DSL (.helix).
    Diagnostics, hover, completion, navigation, structure, semantic
    highlighting, inlay hints, and run/disassemble integration.
  ]]></description>
  <idea-version since-build="222.0" until-build=""/>
  <depends>com.intellij.modules.platform</depends>
  <depends>com.intellij.modules.lang</depends>
  <depends>com.intellij.modules.python</depends>

  <extensions defaultExtensionNs="com.intellij">
    <fileType name="Helix" extensions="helix"
              implementationClass="com.helixlang.plugin.filetype.HelixFileType"
              fieldName="INSTANCE" language="Helix"/>
    <lang.parserDefinition language="Helix"
              implementationClass="com.helixlang.plugin.psi.HelixParserDefinition"/>
    <lang.fileViewProviderFactory language="Helix"
              implementationClass="com.intellij.psi.SingleRootFileViewProviderFactory"/>
    <lang.syntaxHighlighterFactory language="Helix"
              implementationClass="com.helixlang.plugin.syntax.HelixSyntaxHighlighterFactory"/>
    <lang.braceMatcher language="Helix"
              implementationClass="com.helixlang.plugin.syntax.HelixBraceMatcher"/>
    <lang.commenter language="Helix"
              implementationClass="com.helixlang.plugin.syntax.HelixCommenter"/>
    <externalAnnotator language="Helix"
              implementationClass="com.helixlang.plugin.lsp.handlers.HelixDiagnosticsAnnotator"/>
    <completion.contributor language="Helix"
              implementationClass="com.helixlang.plugin.lsp.handlers.HelixCompletionContributor"/>
    <lang.findUsagesProvider language="Helix"
              implementationClass="com.helixlang.plugin.psi.HelixFindUsagesProvider"/>
    <gotoDeclarationHandler implementationClass="com.helixlang.plugin.lsp.handlers.HelixGotoDeclarationHandler"/>
    <structureViewBuilder language="Helix"
              implementationClass="com.helixlang.plugin.lsp.handlers.HelixStructureViewBuilderFactory"/>
    <lang.foldingBuilder language="Helix"
              implementationClass="com.helixlang.plugin.syntax.HelixClientFoldingBuilder"/>
    <configurationType implementation="com.helixlang.plugin.run.HelixRunConfigurationType"/>
    <runConfigurationProducer implementation="com.helixlang.plugin.run.HelixRunConfigurationProducer"/>
  </extensions>

  <applicationListeners>…</applicationListeners>
  <projectListeners>
    <listener class="com.helixlang.plugin.lsp.listeners.HelixProjectOpenedListener"
              topic="com.intellij.openapi.project.ProjectManagerListener"/>
    <listener class="com.helixlang.plugin.lsp.listeners.HelixDocumentListener"
              topic="com.intellij.openapi.editor.event.DocumentListener"/>
    <listener class="com.helixlang.plugin.lsp.listeners.HelixEditorListener"
              topic="com.intellij.openapi.editor.event.EditorFactoryListener"/>
  </projectListeners>

  <actions>
    <action id="Helix.ShowDisassembly" class="com.helixlang.plugin.actions.ShowDisassemblyAction"
            text="Show Bytecode Disassembly" description="Disassemble the current .helix file">
      <add-to-group group-id="EditorPopupMenu" anchor="last"/>
    </action>
  </actions>
</idea-plugin>
```

## 3. File type and language

- `HelixLanguage` — a `Language("Helix")` singleton.
- `HelixFileType` — `Icons.FILE`, `extensions=["helix"]`, with a bundled example
  file template (`New → HelixLang File`).
- `HelixParserDefinition` + mini-PSI: `HelixFile` (a `PsiFileBase`), plus the
  `HelixAnnotation`/`HelixField`/`HelixSymbol`/`HelixSymbolReference` hierarchy.
  PSI is built lazily by `HelixPsiParser` on demand and is **read-only** (no
  PSI-backed editing); the editor never reparses PSI on typing (only on demand
  for navigation). This keeps typing latency at pure-editor speed.

## 4. LSP client core

### 4.1 Design goals

- Runs on **build 222** with zero third-party LSP dependencies.
- Server process lifecycle is fully managed (start/stop/restart/backoff).
- All LSP wire activity happens off the EDT; results are marshalled back to the
  EDT for UI.

### 4.2 Transport abstraction

```kotlin
interface LspTransport {
    fun start(): Process               // launch or connect
    fun send(message: JsonObject)      // thread-safe, serialized by a lock
    fun setMessageConsumer(c: (JsonObject) -> Unit)
    fun dispose()
}
```

| Implementation | When | Notes |
|----------------|------|-------|
| `StdioTransport` | default | `GeneralCommandLine(python, "-m", "helixlang_lsp", "--stdio")` + `ProcessIOExecutorService`; a dedicated reader thread parses `Content-Length` frames from the child's stdout. |
| `TcpTransport` | advanced/troubleshooting | connects to `helixlang_lsp --host 127.0.0.1 --port 8123`; useful for debugging the server in isolation and for attaching profilers. |

### 4.3 JSON-RPC layer

- `LspMessages`: small builders for `initialize`, `initialized`,
  `didOpen/didChange/didSave/didClose`, `textDocument/*` requests, and param
  objects. Uses the platform-bundled **Gson** (`com.google.gson`), which is
  guaranteed on 222.
- `LspDispatcher`: 
  - request IDs are monotonically increasing `Long`s;
  - a `ConcurrentHashMap<Long, CompletableFuture<JsonObject>>` correlates
    responses;
  - notifications are routed to registered handlers by method name;
  - `$/cancelRequest` and `window/logMessage` are handled natively.
- Framing parser (`LspFraming`): a small state machine reading
  `Content-Length: <n>\r\n\r\n<body>`, tolerant of header order, with a hard
  cap (default 64 MB) to avoid unbounded memory.

### 4.4 Server manager

`HelixLspServerManager` is a **project-level service**:

```
on first .helix open / first request
  ──> resolve interpreter (§6.3)
  ──> HelixServerDescriptor  (command, env, cwd, timeout)
  ──> start transport
  ──> initialize (rootUri = project root; capabilities stored)
  ──> send initialized
  ──> subscribe listeners
on project dispose / no .helix open for 5 min
  ──> shutdown → exit → dispose transport
on unexpected process exit
  ──> schedule restart with exponential backoff (100ms, 400ms, 1.6s, … max 5/10min)
  ──> mark "server unavailable", notify status bar
```

Threading: the manager runs on `ApplicationManager.getApplication().executeOnPooledThread`;
all UI mutations go through `invokeLater`.

### 4.5 Document sync

`HelixDocumentListener` (a `BulkAwareDocumentListener`):

| Event | LSP message |
|-------|-------------|
| file opened in editor | `textDocument/didOpen` (full text, version 1) |
| document change | compute `Range`+`text` delta (editor `Document` offsets → LSP UTF-16 offsets) → `didChange` with incremented version |
| save | `textDocument/didSave` |
| editor closed / file closed | `textDocument/didClose` |

Version handling: the client tracks `(uri → version)`; every response that
carries a document version is validated against the current version, and stale
results are discarded (diagnostics from an old version are never rendered).

## 5. Editor integration

### 5.1 Diagnostics (annotator)

- `HelixDiagnosticsAnnotator` is a `DumbAware` `ExternalAnnotator`.
- Prepass reads the client-side diagnostics cache (populated from
  `textDocument/publishDiagnostics`); it does **not** call the server.
- `collectInformation`/`doAnnotate` translate cached `Diagnostic` → `Annotation`
  (`ERROR`/`WARNING`/`INFO`), with the compiler's `data.className` mapped to
  `QuickFix` registrations (see §7 code actions).
- If the server is offline, no annotations are produced (graceful degradation);
  a status-bar indicator shows "Helix LS: offline".

### 5.2 Semantic highlighting

Two layers:

1. **Lexical** (`HelixSyntaxHighlighter`): colors annotation keywords, field
   names, numbers, strings, comments, and the four DNA bases. Instant, offline,
   always on.
2. **Semantic** (from `textDocument/semanticTokens/full`): applied as a
   layered `ExternalAnnotator` (`HelixSemanticTokensAnnotator`) that re-uses the
   token legend and adds the opcode-family colors for codons. The annotator
   stores server tokens keyed by `(uri, version)` and re-requests on invalidation.

The two layers are combined by making the semantic annotator return `null` for
tokens it does not classify, letting the lexical layer show through.

### 5.3 Completion

`HelixCompletionContributor` (a `CompletionContributor`):

- Prefix matching uses the current offset inside a `.helix` file.
- On completion-query it builds the LSP `textDocument/completion` request with
  the cursor `Position`, awaits the result (with a 500 ms cap and `defer`),
  and maps `CompletionItem`s to `LookupElement`s (`Priority`, `InsertHandler`).
- `triggerCharacters` handled via `CompletionConfidence` returning
  `GENERAL` only for `#`, `=`, `>` and word starts in annotations.
- If the server is unavailable, a **static fallback** completion list (annotation
  kinds and field names from an embedded table) is offered so `#` completion
  always works.

### 5.4 Hover

`HelixHoverInfoController` extension: on editor mouse move over a `.helix`
file (with a 350 ms debounce), sends `textDocument/hover` and renders the
Markdown in a `JBHtmlEditorKit`-backed tooltip. A tiny Markdown renderer is
used (platform `MarkdownJCEF` is avoided on 222; a minimal subset renderer is
bundled).

### 5.5 Go-to-definition

`HelixGotoDeclarationHandler` intercepts navigation gestures (Ctrl/Cmd+B) on
`HelixSymbolReference` PSI elements: sends `textDocument/definition`, navigates
to the returned `Location` (opening the target file if needed). Resolution is
**server-first**, with the mini-PSI fallback (same-file definitions) when the
server is offline.

### 5.6 Find usages

- `HelixFindUsagesProvider` provides the "find usages" entry point for
  `HelixSymbol` elements.
- `HelixReferenceSearchExecutor` (a `ReferenceSearchExecutor`) sends
  `textDocument/references` and maps results to `UsageInfo` + `PsiLocation`.
- Result highlighting and the usages tool window work out of the box because we
  produce native `PsiLocation` objects from the mini-PSI.

### 5.7 Structure view

`HelixStructureViewBuilderFactory` produces a `TreeBasedStructureViewBuilder`
whose model is populated from `textDocument/documentSymbol` (cached). Each node
maps to a `HelixStructureViewElement` (name, icon, range, navigation callback).
Structure persists even when the server is offline by using the mini-PSI
symbols as a fallback source.

### 5.8 Folding

`HelixClientFoldingBuilder` implements region folding for `#gene … #end` and
DNA bodies. Primary source is `textDocument/foldingRange`; the builder falls
back to mini-PSI regions when the server is offline. Regions are recomputed
incrementally on document change (only lines within the affected block are
re-requested in range mode).

### 5.9 Inlay hints

- Uses the legacy editor-custom-element renderer API (available on 222) to
  draw opcode labels after codons.
- Data source: `textDocument/inlayHint` (server) with a mini-PSI fallback that
  decodes codons against the bundled `STANDARD_TABLE` copy used only for
  rendering (never for diagnostics).
- Hints are re-queried on semantic-token invalidation and on caret-in-line
  changes (surrounding 2 lines only).
- On 2023.1+, hints additionally use `InlayHintsProvider` when available;
  guarded by `ApplicationInfo` version check.

### 5.10 Brace matcher & commenter

- `HelixBraceMatcher`: pairs `#gene`↔`#end`, `[`↔`]` in L-system rules, and
  `"` quotes.
- `HelixCommenter`: `#` line comments, block-comment support via `#begin`/`#end`
  (P1).

## 6. Running HelixLang from the IDE

### 6.1 Run configuration

`HelixRunConfigurationType` ("HelixLang") with fields:

| Field | Default | Maps to CLI |
|-------|---------|-------------|
| Interpreter | auto-detected | `<python>` |
| Script | current `.helix` file | `<file>` |
| Translation table | `standard` | `--table` |
| Ticks override | (empty) | `--ticks` |
| Output format | `stdout` | `--csv`, `--png PREFIX` |
| Disassemble first | off | `--disassemble` |

`HelixRunProfileState` builds a `GeneralCommandLine`, runs it via
`OSProcessHandler`, and streams stdout/stderr into the run-console. Exit code
and compile/runtime error output are surfaced in the console; the error message
format matches the CLI exactly.

`HelixRunConfigurationProducer` creates a config from the active `.helix` file
(context menu / gutter).

### 6.2 Disassembly view

- `ShowDisassemblyAction` and a toolbar button send
  `workspace/executeCommand {command: "helix.disassemble", args:[uri]}` (P1) or
  fall back to invoking `<python> -m helixlang <file> --disassemble` directly.
- Output opens in a read-only, monospaced, syntax-colored tool window tab
  ("Bytecode"). Gene offsets are clickable → navigate to the source line.

### 6.3 Interpreter resolution

Order of resolution for the interpreter used by both the LS and run configs:

1. The user-chosen interpreter in `HelixSettings` (explicit).
2. **The canonical reference interpreter
   `/opt/anaconda3/envs/helix/bin/python`** when it exists and has
   `helixlang` importable — the recommended default on this project's machines.
3. A Python SDK configured in PyCharm with `helixlang` importable (via
   `PythonSdkService.getInstance().getAllPythonSdks()` — only when the Python
   plugin is present).
4. `python`/`python3` on `PATH`.
5. A bundled stdlib-only fallback environment shipped inside the plugin (P1)
   containing the language server and `helixlang` (so the plugin works with
   zero configuration).

A settings test button runs
`<python> -c "import helixlang, helixlang_lsp"` (using
`/opt/anaconda3/envs/helix/bin/python` by default) and
reports version + path.

## 7. Quick-fixes (code actions)

Cached diagnostics carry `data.className`; the annotator registers quick-fixes:

| Compiler error | Quick-fix | Underlying LSP call |
|----------------|-----------|---------------------|
| `LexError` DNA length | "Append bases to multiple of 3" / "Remove trailing bases" | `textDocument/codeAction` → apply `WorkspaceEdit` |
| `ParseError` missing `name=` | "Insert name=…" | codeAction |
| `ParseError` unterminated ORF | "Append TAA" | codeAction |
| `RegulationError` undefined symbol | "Create symbol" (adds `#gene`/`#promoter`) | codeAction |

Client applies `WorkspaceEdit`s through the `WriteCommandAction`+`Document`
API with a single undoable command.

## 8. Debugging (P1, DAP adapter)

Exposes the `helixlang.debugger.HelixDebugger` (breakpoints by offset/line,
step/step_over/step_out, watches, call stack) as a **Debug Adapter Protocol**
adapter, bridged into IntelliJ's XDebugger:

- `server/helixlang_lsp/dap.py` implements `initialize`, `setBreakpoints`,
  `continue`, `next`, `stepIn`, `stepOut`, `stackTrace`, `scopes`, `variables`,
  `evaluate`, and emits `stopped`/`terminated` events. `python -m helixlang_lsp
  --dap --dap-port-file <file>` serves one session over a local TCP socket.
- Client side: `HelixDebuggerRunner` (`ProgramRunner` for the Debug executor,
  registered `order="first"` for `HelixRunConfiguration`) launches the server,
  performs the `initialize`/`launch`/`configurationDone` handshake over
  `HelixDapClient` (Content-Length framing), and opens an XDebugger session via
  `XDebuggerManager.startSessionAndShowTab`.
- `HelixXDebugProcess` + `HelixXLineBreakpointType` map line breakpoints to DAP
  breakpoints; `HelixDapSuspendContext`/`HelixDapStackFrame`/`HelixDapScope`/
  `HelixDapValue` render the call stack and Cell/GRN/Stack variables.
- P1 scope: breakpoints at codon offsets, step, inspect; **no** edit-and-continue.

## 9. 222-compatibility notes (API guards)

| Feature | 222 API | 2023.1+ improvement | Guard |
|---------|---------|---------------------|-------|
| Inlay hints | `EditorCustomElementRenderer` (legacy) | `InlayHintsProvider` | `ApplicationInfo` version check |
| Markdown tooltip | bundled mini renderer | `MarkdownJCEF` | capability flag |
| Semantic tokens | own annotator pipeline | `SemanticHighlightingComponent` | version check |
| File templates | `FileTemplateGroupDescriptor` | same | n/a |
| Python interpreter list | `PythonSdkService` | same | `depends` python module |

Rule: any API call that exists only in newer builds is wrapped in a version
check and a 222 fallback; CI runs the **same artifact** on 222 and latest so
regressions are caught at build time.

## 10. Alternative: LSP4IJ adapter (2023.1+)

For maintainers who prefer Red Hat's LSP4IJ framework (richer built-in client
machinery), the client core isolates all LSP wiring behind `LspTransport` +
`LspDispatcher` + handlers. A future `lsp4ij/` adapter module can register the
same `HelixServerDefinition` (command, initialize options) through LSP4IJ's
`ServerDefinition`, reusing the server unchanged.

- **Constraint:** LSP4IJ current releases require IntelliJ 2023.1+; therefore it
  **cannot** be the primary client if the 222 baseline is to be honored. It is
  documented as an optional module compiled only for newer baselines.

## 11. Settings UI

`HelixSettingsConfigurable` ("Languages & Frameworks → HelixLang"):

- Interpreter path (+ auto-detect button, test button).
- Language server: stdio/TCP choice, TCP port, `--trace` toggle, log level.
- Features: enable/disable diagnostics, semantic tokens, inlay hints,
  completion fallback; debounce slider.
- Validation: `helix.validate.runVm` with warning.
- Diagnostics: "server status" readout (version, pid, uptime, restart count).

Settings are persisted per-application (`HelixSettings` is an application-level
`PersistentStateComponent`) with per-project overrides supported.

## 12. Implementation status (skeleton)

Current state of the codebase as of the initial skeleton pass. `✅` = module
present and wired in `plugin.xml`; `🟡` = wiring/entry points present but the
server round-trip is a P1 placeholder; `⏳` = not started (P1/P2).

| § | Feature | Status | Notes |
|---|---------|:------:|-------|
| 3 | File type & language | ✅ | `HelixLanguage`, `HelixFileType` (+ icon), `SingleRootFileViewProviderFactory`. |
| 3 | Mini-PSI (read-only, lazy) | ✅ | `HelixPsiParser` + `HelixModel` (`HelixAnnotation`/`HelixField`/`HelixSymbol`), `HelixFile`, `HelixSymbolReference`. |
| 4.2 | Transports | ✅ | `LspTransport` interface; `StdioTransport` (default) and `TcpTransport` both implemented. |
| 4.3 | JSON-RPC layer | ✅ | `LspMessages` (Gson builders), `LspDispatcher` (id correlation, routing, `$/cancelRequest`, `window/logMessage`), `LspFraming` framing parser, `TextPositions` (UTF-16 offsets). Unit-tested. |
| 4.4 | Server manager | ✅ | `HelixLspServerManager` (project service): lazy start, `initialize`/`initialized`, exponential-backoff restart capped at 5/10 min, graceful shutdown on project dispose. |
| 4.4 | Server descriptor | ✅ | `HelixServerDescriptor` builds the command from `HelixSettings` interpreter resolution. |
| 4.5 | Document sync | ✅ | `HelixDocumentListener`/`HelixEditorListener`/`HelixProjectOpenedListener`; `didOpen`/`didChange` (versioned)/`didSave`/`didClose`. |
| 5.1 | Diagnostics | ✅ | `HelixDiagnosticsAnnotator` (DumbAware `ExternalAnnotator`) reads the client-side `diagnosticsCache` from `publishDiagnostics`; offline ⇒ no squiggles. |
| 5.2 | Lexical highlighting | ✅ | `HelixLexer`, `HelixSyntaxHighlighter(Factory)`. |
| 5.2 | Semantic-token highlighting | ✅ | `HelixSemanticTokensAnnotator` — `textDocument/semanticTokens/full` delta decoding, cached per URI, layered over the lexical pass. |
| 5.3 | Completion | ✅ | `HelixCompletionContributor` — LSP request path + static fallback (annotation kinds/field names) when the server is unavailable or disabled in settings. |
| 5.4 | Hover | ✅ | `HelixHoverController` — mouse-motion listener, `textDocument/hover`, markdown tooltip via `HintManager`. |
| 5.5 | Go-to-definition | ✅ | `HelixGotoDeclarationHandler` — server-first with same-file mini-PSI fallback. |
| 5.6 | Find usages | ✅ | `HelixFindUsagesHandlerFactory`/`HelixReferencesHandler` — `textDocument/references` mapped to `UsageInfo`s; same-file fallback offline. |
| 5.7 | Structure view | ✅ | `HelixStructureViewModel` fetches `textDocument/documentSymbol` (hierarchical, navigable); mini-PSI fallback offline. |
| 5.8 | Folding | ✅ | `HelixClientFoldingBuilder` folds `#gene…#end`/annotation ranges from the mini-PSI model; server `foldingRange` path pending. |
| 5.9 | Inlay hints | ✅ | `HelixInlayHintsController` + `LabelRenderer` — `textDocument/inlayHint`, inline elements refreshed on edit. |
| 5.10 | Brace matcher & commenter | ✅ | `HelixBraceMatcher`, `HelixCommenter`. |
| 6.1 | Run configuration | ✅ | `HelixRunConfigurationType`, `HelixRunConfigurationProducer`, `HelixRunProfileState` (CLI parity), `HelixRunSettingsEditor`. |
| 6.2 | Disassembly view | ✅ | `ShowDisassemblyAction` + `DisassemblyToolWindow` (read-only monospaced tab; CLI fallback path). |
| 6.3 | Interpreter resolution | ✅ | Resolution chain (settings → reference interpreter → Python SDKs → bundled fallback envs → PATH) implemented. |
| 7 | Quick-fixes | ✅ | `HelixQuickFixPlaceholder` sends `textDocument/codeAction` with diagnostic context and applies the first `WorkspaceEdit` in a write command. |
| 8 | DAP debugger | ✅ | Server `--dap` mode (`DapSession`, `HelixDebugAdapter`, stopped/terminated events) + `HelixDebuggerRunner` (`ProgramRunner` for the Debug executor), `HelixDapClient` (TCP framing), `HelixXDebugProcess`/`HelixXLineBreakpointType`, frames/variables via `HelixDapSuspendContext`/`HelixDapScope`/`HelixDapValue`. |
| 11 | Settings UI | ✅ | `HelixSettings` (application-level `PersistentStateComponent`) + `HelixSettingsConfigurable`. |

**Build status:** `./gradlew build` (JUnit tests, `buildPlugin`, `verifyPlugin`)
is green on JDK 17 / Gradle 7.6.4 against the PyCharm `2022.2.3`
(== build 222.3345.118) SDK; artifact at
`build/distributions/helixlang-ide-1.0.0.zip`. Known `verifyPlugin` warnings are
limited to the IPGP/Kotlin 1.8.22 OOM hint and harmless UI-DSL deprecations.

---

Next: [05 — Feature Specifications](./05-features.md).
