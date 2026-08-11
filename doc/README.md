# HelixLang IDE Integration — Design Documents

> Complete engineering design for a **Language Server Protocol (LSP) plugin for
> PyCharm 2022.2 and later** that brings first-class editing support for the
> HelixLang programming language (`.helix`).

This folder is the authoritative design reference for the `HelixLang-LSP-Plugin`
project. Every document is written in English and is kept in sync with the
implementation; when a document and the code disagree, the code prevails.

---

## Document map

| # | Document | Audience |
|---|----------|----------|
| [00](./README.md) | Everyone | Index, glossary, suggested reading order |
| [01](./01-overview.md) | Everyone | Project vision, goals, scope, compatibility strategy |
| [02](./02-architecture.md) | Architects & maintainers | System decomposition, component map, data flows, concurrency |
| [03](./03-language-server.md) | Server contributors | The Helix language server: JSON-RPC, LSP capabilities, analysis pipeline |
| [04](./04-intellij-plugin.md) | Plugin contributors | The PyCharm/IntelliJ Platform client: build baseline, LSP client, UI integration |
| [05](./05-features.md) | Feature owners & QA | Feature-by-feature specification, triggers, edge cases, priority matrix |
| [06](./06-build-testing.md) | Build & CI maintainers | Gradle/Python build, quality gates, test pyramid, distribution |
| [07](./07-roadmap.md) | Maintainers | Milestones, acceptance criteria, risks, future work |

## Suggested reading order

1. **[01-overview.md](./01-overview.md)** — what we build and why.
2. **[02-architecture.md](./02-architecture.md)** — how the pieces fit together.
3. **[03-language-server.md](./03-language-server.md)** — the server contract.
4. **[04-intellij-plugin.md](./04-intellij-plugin.md)** — the client contract.
5. **[05-features.md](./05-features.md)** — the user-facing feature contract.
6. **[06-build-testing.md](./06-build-testing.md)** — before you open a PR.
7. **[07-roadmap.md](./07-roadmap.md)** — where the project is going.

## Upstream references

The design is grounded in the HelixLang language and its reference
implementation:

- **Language specification:** `HelixLang/doc/language-spec.md` (alphabet,
  annotation syntax, codon table, bytecode format, runtime semantics, type system).
- **Compiler design:** `HelixLang/doc/compiler-design.md` (Lexer → Parser →
  AST → Semantic → Compiler → Chunk → VM).
- **Compiler API:** `HelixLang/src/helixlang/` — the Python modules that the
  language server wraps (lexer, parser, semantic, compiler, codon_table,
  disassembler, debugger, errors).
- **Example programs:** `HelixLang/examples/*.helix` — the acceptance corpus.

## Glossary

| Term | Meaning |
|------|---------|
| **LSP** | Language Server Protocol, a JSON-RPC-based protocol (v3.17 as of this design) that decouples language features from the editor. |
| **Language server (LS)** | The Python process that analyzes `.helix` source and answers language-feature requests over LSP. |
| **LSP client** | The part of the plugin inside the IDE that talks to the language server and renders its results. |
| **PSI** | Program Structure Interface, the IntelliJ Platform's source-model API. |
| **Build 222** | The IntelliJ Platform build number for PyCharm 2022.2; the minimum platform baseline for this plugin. |
| **Semantic tokens** | LSP feature that gives the client per-token classifications (colors) for editor highlighting. |
| **Mini-PSI** | A deliberately tiny, regex-based PSI subset defined on the client for navigation features, decoupled from the full semantic analysis performed by the server. |
| **Diagnostic** | An error, warning, or information item attached to a range of a document (`textDocument/publishDiagnostics`). |
| **DAP** | Debug Adapter Protocol; used (P1) to expose the HelixLang bytecode debugger in the IDE. |
| **Reference interpreter** | `/opt/anaconda3/envs/helix/bin/python` — the canonical Python 3.11.15 (conda env `helix`) used for the server, tests, and run configurations. |

---

*Copyright © 2026 Sean Hank.*
