<div align="center">

# 🧬 HelixLang IDE

_"The precise sequence of the bases is the code which carries the genetical information." — James Watson & Francis Crick_

**Language Server Protocol integration for the HelixLang DSL — a PyCharm client plus a Python language server.**

Write `.helix` programs with real IDE superpowers: diagnostics, hover docs, completion,
navigation, semantic highlighting, inlay hints, a bytecode disassembler, and a line debugger.

[Install](#-quick-start) ·
[Features](#-features) ·
[Requirements](#-requirements) ·
[Build from source](#-build-from-source) ·
[CI & Releases](#-ci--releases) ·
[Contributing](#-contributing) ·
[Documentation](#-documentation)

![CI](https://github.com/SeanHank/HelixLang-LSP-Plugin/actions/workflows/ci.yml/badge.svg)

</div>

---

## 🚀 Quick Start

1. Grab the latest plugin zip from the **[Releases](https://github.com/SeanHank/HelixLang-LSP-Plugin/releases)** page.
2. In PyCharm open **Settings → Plugins → ⚙ → Install Plugin from Disk…** and pick the zip.
3. **Restart PyCharm**.
4. Install the language server (once, per Python interpreter):

```bash
pip install helixlang-lsp
```

> `helixlang-lsp` is published on **[PyPI](https://pypi.org/project/helixlang-lsp/)** and pulls
> in the `helixlang` compiler/VM as a dependency. 

5. Point the plugin at that interpreter in **Settings → HelixLang**.

Open any `.helix` file — the server starts automatically and the IDE comes alive.

> 💡 New releases ship automatically: every push to `main` builds the plugin and publishes a
> GitHub Release tagged `v<version>`. Bump the version in
> [`gradle.properties`](gradle.properties) (`pluginVersion=`) and push.

---

## ✨ Features

| | |
|---|---|
| 🩺 **Live diagnostics** | Real-time errors & warnings as you type, straight from the LSP server |
| 🧠 **Hover documentation** | Peek at gene/promoter annotations, semantics and inferred state |
| 🔎 **Intelligent completion** | Codons, annotation blocks, identifiers and LSP suggestions |
| 🧭 **Navigation** | Go to declaration, find usages, structure view for genes & operons |
| 🎨 **Semantic highlighting** | Codons, amino acids, genes and metadata colored by their role |
| 📍 **Inlay hints** | Decoded amino-acid / opcode annotations inline in the source |
| 🔧 **Folding & editing** | Code folding, brace matching and smart comments |
| ▶️ **Run & disassemble** | Run configurations plus a bytecode disassembly tool window |
| 🐛 **Line debugger** | DAP line breakpoints with the bytecode VM — set a breakpoint on a codon |
| ⚙️ **Configurable** | Dedicated `HelixLang` settings page for server & interpreter options |

---

## 📦 Requirements

| Component | Version |
|---|---|
| IDE | **PyCharm 2022.2+** (Community or Professional) |
| JDK (to build) | 17 |
| Python | 3.11+ with `helixlang-lsp` installed (from [PyPI](https://pypi.org/project/helixlang-lsp/)) |

The language, compiler and VM themselves live in the sibling repository
[`SeanHank/HelixLang`](https://github.com/SeanHank/HelixLang).

---

## 🛠️ Build from source

```sh
JAVA_HOME=/path/to/jdk-17 ./gradlew build
```

`build` runs the JUnit tests, `buildPlugin` (zip) and `verifyPlugin`
(structural verification). The distributable lands in:

```
build/distributions/helixlang-ide-<version>.zip
```

For a live dev sandbox: `./gradlew runIde`. The Python language server is under
[`server/`](server/), installable with `pip install -e "server[dev]"`.

### Test the language server

```sh
python -m pytest server/tests --cov=helixlang_lsp --cov-fail-under=85
python -m pytest server/tests/test_latency.py   # latency budgets, un-instrumented
python -m ruff check server
python -m mypy server
```

The latency-budget tests skip themselves under pytest-cov instrumentation, so they
run in a separate un-instrumented pass.

---

## 📁 Repository layout

```
HelixLang-LSP-Plugin/
├── doc/                        # design documents (authoritative reference)
├── server/                     # Python language server (helixlang-lsp)
│   ├── pyproject.toml
│   ├── helixlang_lsp/
│   └── tests/
├── src/main/kotlin/com/helixlang/plugin/   # PyCharm client (Kotlin)
├── src/main/resources/META-INF/plugin.xml  # plugin descriptor & icons
├── src/test/kotlin/                        # JUnit 5 unit tests
├── build.gradle.kts · settings.gradle.kts · gradle.properties
├── gradlew / gradlew.bat · gradle/wrapper/…
└── .github/workflows/ci.yml
```

---

## 🤖 CI & Releases

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs two quality gates on every
push/PR, then **publishes a GitHub Release on every push to `main`**:

| Job | What it does |
|---|---|
| **Server** | Python 3.11 — `ruff` + `mypy` + `pytest` with ≥85% coverage |
| **Plugin** | JDK 17 — `./gradlew build` (tests + `buildPlugin` + `verifyPlugin`) |
| **Release** | Uploads the plugin zip to a GitHub Release tagged `v<version>` (only on `main`) |

**Versioning** is a one-line change: edit `pluginVersion=` in
[`gradle.properties`](gradle.properties), push, and CI publishes the new release for you.

---

## 📚 Documentation

The full engineering design lives in [`doc/`](./doc/README.md):

| # | Document |
|---|----------|
| [01](./doc/01-overview.md) | Overview, goals, scope, compatibility strategy |
| [02](./doc/02-architecture.md) | Architecture, components, data flows |
| [03](./doc/03-language-server.md) | Language server design |
| [04](./doc/04-intellij-plugin.md) | IntelliJ/PyCharm client design + implementation status |
| [05](./doc/05-features.md) | Feature specifications and priority |
| [06](./doc/06-build-testing.md) | Build, quality gates, CI, distribution |
| [07](./doc/07-roadmap.md) | Milestones, acceptance criteria, risks |

---

## 🤝 Contributing

Contributions are welcome! Please read **[CONTRIBUTING.md](CONTRIBUTING.md)** first — it covers
the development setup, the quality gates (`ruff` + `mypy` + pytest ≥85% coverage for the
server; `./gradlew build` with JDK 17 for the plugin), the golden-test workflow, coding
conventions, and the documentation policy.

In short: fork the repo, create a branch off `main`, and open a pull request.

```bash
git clone https://github.com/SeanHank/HelixLang-LSP-Plugin.git
cd HelixLang-LSP-Plugin
python -m pip install -e "server[dev]"
JAVA_HOME=/path/to/jdk-17 ./gradlew build
```

## License

This project is licensed under the **GNU Affero General Public License v3.0** (AGPLv3).  

Copyright © 2026 Sean Hank.
