# 02 — System Architecture

> System decomposition, component map, data flows, lifecycle, and concurrency
> model for the HelixLang LSP plugin.

---

## 1. Layer model

The system is composed of four layers. Each layer depends only on the layer
directly below it.

```
Layer 0   User interface            PyCharm editor, tool windows, menus
Layer 1   IDE plugin (client)       Kotlin, runs inside the IDE JVM
Layer 2   Language server           Python process (helixlang_lsp)
Layer 3   Language kernel           helixlang compiler/runtime (src/helixlang)
```

**Dependency rule:** layer *N* talks to layer *N+1* exclusively through the
protocol boundary. The IDE never imports `helixlang`; the server never touches
IntelliJ APIs. This keeps each layer individually testable and lets the server
be reused by other editors (VS Code, Neovim) later.

## 2. Component diagram

```
┌──────────────────────────── Layer 1: IDE plugin (Kotlin) ─────────────────────────────┐
│                                                                                        │
│  ┌────────────────────┐     ┌─────────────────────────────┐     ┌───────────────────┐  │
│  │ File type / lang   │     │ HelixLspServerManager (app- │     │ Settings UI       │  │
│  │ .helix registration│     │ scoped service)             │     │ HelixSettings     │  │
│  └────────────────────┘     │  • lifecycle / restart      │     └───────────────────┘  │
│  ┌────────────────────┐     │  • capability registry      │          ▲                 │
│  │ Mini-PSI model     │     └──────────────┬──────────────┘          │                 │
│  │ HelixPsiFile,      │                    │ owns                       │               │
│  │ HelixSymbol        │                    ▼                            │               │
│  └────────────────────┘     ┌─────────────────────────────┐             │               │
│  ┌────────────────────┐     │ LSP client core             │             │               │
│  │ Editor integrations │    │ ┌───────────┐ ┌───────────┐ │             │               │
│  │ • Annotator (diag) │◄────│ │ Transport │ │ JSON-RPC  │ │             │               │
│  │ • CompletionContrib│◄────│ │ stdio/TCP │ │ dispatcher│ │             │               │
│  │ • GotoDecl / Find  │◄────│ └───────────┘ └───────────┘ │             │               │
│  │   Usages           │     │  request/response table     │             │               │
│  │ • Structure / Fold │     │  notification pump          │             │               │
│  │ • Semantic HL      │     └─────────────────────────────┘             │               │
│  │ • Inlay hints      │                                                 │               │
│  │ • Run config       │                                                 │               │
│  └────────────────────┘                                                 │               │
└───────────────────────────────┬─────────────────────────────────────────┘               │
                                │ LSP (JSON-RPC 2.0) — stdio by default, TCP optional     │
┌───────────────────────────────▼─────────────────────────────────────────┐               │
│  Layer 2: Language server (Python, stdlib)                              │               │
│  ┌──────────────┐ ┌───────────────┐ ┌──────────────┐ ┌───────────────┐  │               │
│  │ jsonrpc.py   │ │ server.py     │ │ analysis.py  │ │ positions.py  │  │               │
│  │ framing/     │ │ initialize/   │ │ pipeline +   │ │ UTF-16 ↔      │  │               │
│  │ dispatcher   │ │ capabilities  │ │ symbol table │ │ 1-based       │  │               │
│  └──────────────┘ └──────┬────────┘ └──────┬───────┘ └───────────────┘  │               │
│  ┌───────────────────────▼────────────────▼───────────────────────────┐  │               │
│  │ features/: completion, hover, definitions, references, symbols,    │  │               │
│  │ semantic_tokens, folding, formatting, inlay_hints, code_actions    │  │               │
│  └────────────────────────────────────────────────────────────────────┘  │               │
└───────────────────────────────┬─────────────────────────────────────────┘               │
                                │ imports                                    │               │
┌───────────────────────────────▼─────────────────────────────────────────┐               │
│  Layer 3: HelixLang kernel — Lexer, Parser, SemanticAnalyzer, Compiler, │               │
│  disassembler, debugger, errors, and the sim-runtime adapter            │               │
│  (sim_runtime.run → classic VM or whole_cell/population/fba/            │               │
│  calibration/benchmark), src/helixlang                                  │               │
└─────────────────────────────────────────────────────────────────────────┘               │
```

## 3. Data flows

### 3.1 Editing session (diagnostics)

```
open .helix          ──> client: didOpen(text)                    ──> server
typing               ──> client: didChange(version, edits)       ──> server
                                                                    server: re-analyze
                                                                    (debounced)
                                                                    server: publishDiagnostics(uri, items)
client stores        <──────────────────────────────────────────────────────
Annotator renders squiggles <───────────────────────────────────────────────
```

### 3.2 Request/response (hover example)

```
Ctrl+<hover> over codon "GCT"
   editor                          client                          server
      │  EditorMouseEvent             │  textDocument/hover            │
      │──────────────────────────────▶│  {position, uri, version}      │
      │                               │───────────────────────────────▶│
      │                               │                               │  decode via STANDARD_TABLE
      │                               │   hover { contents: Markdown }│  → OP_BUILD_PROTEIN arg=0
      │                               │◀───────────────────────────────│
      │  tooltip render ◀─────────────│
```

### 3.3 Run flow

```
Run "sample.helix"
   HelixRunConfiguration
   ──> GeneralCommandLine: <python> -m helixlang <file> [--table] [--ticks]
   │                                       [--backend NAME] [--csv|--json]
   ──> OSProcessHandler ──> console view (stdout) / tool window
   optional: --disassemble ──> dedicated disassembly tab
```

`--backend NAME` overrides the source's `#config backend` (any of
`classic | whole_cell | population | fba | calibration | benchmark`); `--json`
emits the `SimResult` payload for the sim backends. Both are surfaced by the
run configuration (`doc/04` §6.1).

## 4. Concurrency model

### 4.1 Client (IDE JVM)

| Concern | Thread | Notes |
|---------|--------|-------|
| Editor events, menus | EDT | Never block; all LSP calls go to background executor. |
| Transport read pump | dedicated "LSP reader" thread | Reads `Content-Length` frames, dispatches to EDT via `invokeLater` for UI mutations. |
| Transport write | same reader thread or a small writer lock | Writes are serialized with a mutex. |
| Server process lifecycle | background executor | Start/stop/restart off EDT. |
| Semantic highlights | `ExternalAnnotator` background pass | Annotator is `DumbAware`; cheap cache read. |
| Annotations (diagnostics) | `ExternalAnnotator` | Runs on highlight pass; reads the client-side diagnostics cache. |

### 4.2 Server (Python)

The server is single-threaded and **event-loop driven** (stdlib `queue.Queue` +
worker thread, or `asyncio` if the 3.11 baseline is adopted project-wide). All
requests for a document are serialized and processed in arrival order; analysis
state is owned by the single worker so no locks are needed.

| Concern | Model |
|---------|-------|
| Frame reader | dedicated reader thread feeding an inbound queue |
| Frame writer | single writer with an outbound lock |
| Analysis | on the worker thread; cancelled/replaced by newer edits (debounce window) |
| Diagnostics push | published asynchronously after each re-analysis |

## 5. Lifecycle & state

### 5.1 Server lifecycle (client-managed)

```
idle                    server not started
   │  first .helix opened / first feature requested
   ▼
starting                launch process, send initialize + initialized
   │  initialized response received, capabilities stored
   ▼
ready                   respond to requests, publish diagnostics
   │  process exited unexpectedly
   ▼
restarting (max N times/10 min)     →  back to starting
   │  project closed / all .helix closed → shutdown request → kill process
   ▼
stopped
```

- Startup is **lazy** and **per-project** (`HelixLspServerManager` is a
  project-scoped service).
- Idle policy: keep alive while ≥ 1 `.helix` document is open; stop when the
  project is disposed.
- Crash policy: exponential backoff restart, at most 5 restarts per 10 minutes;
  after that, diagnostics fall back to "server unavailable" and a status-bar
  notification is shown. The annotator degrades gracefully (no squiggles).

### 5.2 Server state (per workspace)

| State | Description |
|-------|-------------|
| `documents: {uri: DocumentState}` | text version, full text cache, last analysis result |
| `symbols: {name: SymbolOccurrence}` | definitions + references index, rebuilt per analysis |
| `diagnostics: {uri: [Diagnostic]}` | last published diagnostics |
| `capabilities` | advertised in `initialize` result |

## 6. Client mini-PSI model (navigation layer)

The client keeps a deliberately minimal source model so that *structural*
features (Find Usages, Structure view, Rename, breadcrumbs, go-to-symbol) work
even though the semantic analysis lives on the server.

```
HelixFile (PsiFileBase)
 ├── HelixAnnotation(kind, startLine)          # #gene / #promoter / ...
 │    ├── HelixField(name, value, range)
 │    └── HelixSymbol(name, kind, definitionRange)   # genes, promoters
 ├── HelixCodonBlock(genes...)                 # DNA body lines
 └── HelixSymbolReference(element)             # usage of a symbol
```

- Built by `HelixPsiParser` — a regex/tokenizer pass (~200 LOC) that recognizes
  `#<kind> name=…`, `#regulate src -> tgt`, `promoter=`, `target=`, `#end`.
- It is **not** the compiler: it may be wrong about edge cases; it exists only
  to make navigation instant and offline.
- The server's symbol index is authoritative; where the two disagree for
  navigation, the client accepts server results (hover/definition resolve
  through the server first, with mini-PSI as fallback).

**Why not full PSI?** A complete client parser would duplicate the language
spec and drift. The hybrid model (mini-PSI + LSP) is the standard pragmatic
architecture used by IDE language plugins that are LSP-backed.

## 7. Module map

### 7.1 Kotlin (client) — `src/main/kotlin/com/helixlang/plugin/`

| Package | Responsibility |
|---------|----------------|
| `filetype/` | `HelixLanguage`, `HelixFileType`, file-type factory, icon |
| `lsp/protocol/` | LSP message builders (`LspMessages`), framing parser, method constants |
| `lsp/transport/` | `LspTransport` interface, `StdioTransport`, `TcpTransport` |
| `lsp/` | `HelixLspServerManager`, `HelixServerDescriptor`, JSON-RPC dispatcher, request-correlation table |
| `lsp/handlers/` | Diagnostics, completion, hover, definition, references, symbols, semantic tokens, folding, code actions, inlay hints |
| `lsp/listeners/` | Document (open/change/save/close) and editor listeners |
| `psi/` | Mini-PSI classes + `HelixPsiParser` + `HelixFileType` PSI file |
| `syntax/` | Lexical highlighter, brace matcher, commenter, folding (client fallback) |
| `run/` | Run configuration type, producer, profile state (CLI runner) |
| `settings/` | Persisted settings + `Configurable` UI |
| `actions/` | Disassemble action, simulation-run action |
| `icons/` | `HelixIcons` |

### 7.2 Python (server) — `server/helixlang_lsp/`

| Module | Responsibility |
|--------|----------------|
| `__init__.py` | version, exports |
| `main.py` | entry point (`helixlang-lsp` console script) |
| `jsonrpc.py` | JSON-RPC 2.0 framing (read/write), message dispatch |
| `protocol.py` | LSP types & message builders (dataclasses) |
| `server.py` | server orchestration: initialize, capabilities, feature routing |
| `positions.py` | 1-based↔0-based, UTF-16 conversion |
| `analysis.py` | compilation pipeline wrapper, per-document caching, symbol table |
| `diagnostics.py` | `HelixError` → LSP `Diagnostic` mapping |
| `features/*.py` | one module per LSP feature |

## 8. Error & failure handling

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Server process crash | reader EOF / exit code | restart with backoff (client) |
| Malformed server response | JSON schema mismatch | drop request, log, mark server unhealthy |
| Compiler crash (internal bug) | uncaught exception in analysis | server reports `window/logMessage` error, keeps serving other docs |
| Python interpreter missing | process start throws | settings error surfaced in settings UI + status bar |
| Server version mismatch | `serverInfo` vs expected in `initialize` | warning dialog once per session |
| Document version race | client checks `version` of response vs current | stale responses are discarded |

## 9. Observability

- **Client:** `HelixLspLog` (INFO-level) records lifecycle events, request
  latency, and skipped/cancelled requests; exposed through a dedicated log file
  when `helix.lsp.debug=true`.
- **Server:** `window/logMessage` for errors/warnings; optional
  `--trace` writes a JSONL transcript of every message for conformance tests and
  bug reports.
- **Metrics (P1):** per-feature latency histogram, diagnostics time per file
  size, server restarts — collected in-memory and dumped on shutdown.

---

Next: [03 — Language Server](./03-language-server.md).
