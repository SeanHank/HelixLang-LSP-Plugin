# 01 — Project Overview

> Vision, goals, scope, and compatibility strategy for the HelixLang LSP plugin
> for PyCharm 2022.2 and later.

---

## 1. Context

[HelixLang](https://github.com/SeanHank/HelixLang) is a domain-specific language
in which **DNA is the source code**: a `.helix` file mixes DNA sequence blocks
(runs of `A/C/G/T`, split into codons) with `#`-prefixed annotation blocks
(`#gene`, `#promoter`, `#regulate`, `#lsystem`, `#field`, `#config`, and bio
instructions). The compiler maps each codon to a bytecode opcode through a
switchable "translation table" (standard / mitochondrial / ciliate) and runs the
result on a stack-based bytecode VM ("the ribosome") that simulates a cell.

Today HelixLang ships a CLI, a Python API, a Flask web visualization, and 20
example programs — but **no IDE integration**. Editing `.helix` files means
working in a plain-text editor with no syntax highlighting, no diagnostics, no
navigation, and no way to run or debug a program from the IDE.

This project closes that gap with a **Language Server Protocol (LSP) plugin for
PyCharm 2022.2 and later**.

## 2. Mission statement

> Provide a first-class HelixLang editing experience inside PyCharm 2022.2+ by
> pairing a **Python language server** (which wraps the real HelixLang compiler)
> with an **IntelliJ Platform plugin** (the LSP client) — so that the IDE never
> re-implements language semantics and stays correct as the language evolves.

## 3. Goals

| # | Goal | Measured by |
|---|------|-------------|
| G1 | Correct, always-current diagnostics | Every compiler error class (`LexError`, `ParseError`, `SemanticError`, `RegulationError`, `CompileError`) surfaces as an LSP diagnostic with a precise range. |
| G2 | Rich editing features | Hover, completion, go-to-definition, find-references, document structure, folding, semantic highlighting, code actions, inlay hints. |
| G3 | Run + inspect from the IDE | A run configuration that compiles/executes a program and shows trace output; a disassembly tool window (P1 debugger via DAP). |
| G4 | Compatibility with PyCharm 2022.2 → current | One codebase builds against build 222 (PyCharm 2022.2) and remains compatible through current releases. |
| G5 | Zero duplicated semantics | The client renders what the server computes; the server delegates all language understanding to `src/helixlang/`. |
| G6 | Testability | Language-agnostic conformance tests on the server; platform fixtures + E2E on the client; CI gates. |

## 4. Non-goals (v1)

- A full Python-flavored re-implementation of the HelixLang parser on the client.
- Rewriting or forking the HelixLang compiler.
- Supporting the Flask web visualization from within the IDE (launched externally).
- Replacing the existing CLI or Python API.
- Bio-module analytics inside the IDE (protein structure, FBA, CRISPR design
  workflows remain Python-library / CLI features; the plugin only exposes run
  output and the static language features).
- A general-purpose "anything editor" LSP client (the client is HelixLang-specific).

## 5. High-level architecture

```
┌────────────────────────────── PyCharm 2022.2+ ──────────────────────────────┐
│                                                                             │
│   IntelliJ Platform plugin (Kotlin) ──────────────── LSP client             │
│   • file type / language registration      • transport (stdio/TCP)          │
│   • mini-PSI for navigation                • JSON-RPC request correlation   │
│   • diagnostics annotator                  • feature handlers               │
│   • completion / hover / structure / ...   • run configuration              │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │ Language Server Protocol (JSON-RPC 2.0)
                                │ stdio by default, TCP optional
┌───────────────────────────────▼────────────────────────────────────────────┐
│                                                                             │
│   Helix Language Server (Python, stdlib-only)                               │
│   • JSON-RPC framing + dispatcher              • position mapping (UTF-16)  │
│   • analysis pipeline wrapper                 • symbol index / workspace    │
│   • feature handlers (completion, hover, …)   • diagnostics publisher       │
└───────────────────────────────┬────────────────────────────────────────────┘
                                │ imports / calls
┌───────────────────────────────▼────────────────────────────────────────────┐
│   HelixLang compiler & runtime (src/helixlang/*)                            │
│   Lexer → Parser → SemanticAnalyzer → Compiler → Chunk → (optional) VM      │
└─────────────────────────────────────────────────────────────────────────────┘
```

Three layers, one boundary each:

1. **HelixLang compiler** (`src/helixlang/`) — the source of truth for language
   semantics. **No modifications to this repository are required.**
2. **Helix language server** (`server/helixlang_lsp/`, new, Python) — thin,
   testable wrapper that translates editor events into compiler calls and
   compiler results into LSP messages.
3. **IntelliJ Platform plugin** (`src/main/kotlin/…`, new, Kotlin) — the LSP
   client and the IDE integration surface.

## 6. Key design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| IDE plugin vs. external tool | IntelliJ Platform plugin targeting PyCharm | Native file-type registration, run configurations, settings UI, distribution through JetBrains Marketplace. |
| Protocol | LSP 3.17 over stdio (TCP optional) | Editor-agnostic, testable headlessly, reuses the compiler as-is. |
| Language server language | Python, standard library only | HelixLang is pure-Python stdlib; importing `helixlang` is free. No pip dependency beyond the project itself. |
| LSP client framework | **Custom minimal client** (default); **LSP4IJ adapter** (alternative, 2023.1+) | LSP4IJ releases require IntelliJ 2023.1+; a from-scratch JSON-RPC client keeps the **222 baseline** guarantee and full control. |
| Symbol model on the client | **Mini-PSI** (regex-based, ~200 LOC) | Gives native Find Usages / Structure / Rename without re-implementing language semantics; the server stays authoritative for semantics. |
| Diagnostics pipeline | Server-computed, client-rendered | Single implementation of the error model (in `src/helixlang/errors.py`). |
| Run integration | `GeneralCommandLine` invoking `helixlang` CLI / a small runner script | No JVM-side re-compilation; exact parity with CLI behavior. |

## 7. Compatibility strategy

The IntelliJ Platform is backward-compatible within a major version line, so a
plugin built against **build 222** runs on every later release unless it uses
deprecated APIs. The strategy:

- `since-build="222.0"` and no `until-build` restriction in v1 (JetBrains
  Marketplace convention for forward compatibility).
- Build against **PyCharm Community `PY-222.3345.118`** using IntelliJ Platform
  Gradle Plugin (IPGP) **1.14.x**, Kotlin **1.8.x**, Gradle **7.6.x**.
- Annotate new-API usage with `@RequiresBackgroundThread`-style guards and
  version checks where 222 differs from newer builds (e.g. the inlay-hint
  renderer API which predates `com.intellij.codeInsight.hints`).
- CI matrix verifies the same artifact on **PyCharm 2022.2** and the **latest
  stable PyCharm** each release.

### Compatibility matrix

| PyCharm | Build | Supported | Notes |
|---------|-------|-----------|-------|
| 2022.2  | 222    | ✅ (baseline) | CI-verified |
| 2022.3  | 223    | ✅ | |
| 2023.1 – 2023.3 | 231–233 | ✅ | |
| 2024.1+ | 241+   | ✅ | Newer features guarded by API checks |
| PyCharm Community | — | ✅ | Target `PY` type |
| PyCharm Professional | — | ✅ | Same artifact |

## 8. Deliverables

1. `server/` — installable Python language-server package (`helixlang_lsp`).
2. `src/main/` — IntelliJ Platform plugin sources (Kotlin) + `plugin.xml`.
3. `tests/` — Python conformance tests, Kotlin unit tests, platform fixture
   tests, E2E tests.
4. `docs/` — these design documents.
5. CI pipeline (GitHub Actions) that gates on pytest + ruff + mypy + Gradle
   `verifyPlugin` + plugin-artifact integration smoke tests.

### 8.1 Reference environment

The canonical development interpreter is
`/opt/anaconda3/envs/helix/bin/python` (conda env `helix`, Python 3.11.15,
`helixlang` installed editable). Every command in `doc/03`, `doc/04`, and
`doc/06` uses this absolute path by default.

## 9. Out of scope for this document

The biological/simulation semantics of HelixLang, the compiler internals, and
the CLI are covered by the HelixLang repository's own documentation
(`HelixLang/doc/*`). This design only specifies the **integration surface**.

---

Next: [02 — Architecture](./02-architecture.md).
