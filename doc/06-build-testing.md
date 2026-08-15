# 06 — Build, Testing, and Distribution

> Build system, quality gates, test pyramid, and distribution for the
> HelixLang LSP plugin.

---

## 1. Repository layout

```
HelixLang-LSP-Plugin/
├── doc/                       # these design documents
├── build.gradle.kts           # Kotlin plugin build
├── settings.gradle.kts
├── gradle.properties
├── gradle/wrapper/…
├── gradlew / gradlew.bat
├── server/                    # Python language server
│   ├── pyproject.toml
│   ├── helixlang_lsp/
│   │   ├── __init__.py
│   │   ├── __main__.py           # python -m helixlang_lsp entry point
│   │   ├── main.py
│   │   ├── jsonrpc.py
│   │   ├── protocol.py
│   │   ├── server.py
│   │   ├── positions.py
│   │   ├── analysis.py
│   │   ├── diagnostics.py
│   │   └── features/{completion, hover, definitions, symbols,
│   │                 semantic_tokens, folding, formatting,
│   │                 inlay_hints, code_actions}.py
│   └── tests/
├── src/main/kotlin/com/helixlang/plugin/…    # Kotlin client
├── src/main/resources/META-INF/plugin.xml
├── src/test/kotlin/…                         # Kotlin tests
└── .github/workflows/ci.yml
```

## 2. Python side (language server)

### 2.1 Reference environment

All commands below use the canonical interpreter

```
/opt/anaconda3/envs/helix/bin/python
```

(conda env `helix`, Python 3.11.15; `helixlang` installed editable; `pytest`,
`ruff`, `mypy` available). CI installs the same packages in a fresh 3.11
environment.

### 2.2 Packaging

`server/pyproject.toml`:

```toml
[project]
name = "helixlang-lsp"
version = "2026.8.2"
requires-python = ">=3.11"
dependencies = ["helixlang>=1.0.0"]
[project.scripts]
helixlang-lsp = "helixlang_lsp.main:main"
[project.optional-dependencies]
dev = ["pytest>=7.4", "pytest-cov>=4.1", "ruff>=0.4", "mypy>=1.8"]
```

Also declared as the `lsp` extra of the HelixLang distribution so a single
`pip install "helixlang[lsp]"` provides both the compiler and the server.

### 2.2 Quality gates

| Gate | Command | Policy |
|------|---------|--------|
| Unit + conformance tests | `/opt/anaconda3/envs/helix/bin/python -m pytest server/tests` | 100% pass |
| Coverage | `--cov=helixlang_lsp --cov-fail-under=85` | ≥ 85% |
| Latency budgets | `pytest server/tests/test_latency.py` (un-instrumented) | §7 budgets hold |
| Lint | `/opt/anaconda3/envs/helix/bin/python -m ruff check server` | clean |
| Types | `/opt/anaconda3/envs/helix/bin/python -m mypy server` | clean |

The latency-budget tests skip themselves when pytest-cov is active (coverage
instrumentation invalidates their timings) and are enforced in CI by a separate
un-instrumented run of `tests/test_latency.py`.

### 2.3 Test pyramid (server)

| Layer | What | Example |
|-------|------|---------|
| Unit | pure feature functions | `hover` returns expected Markdown for a codon |
| Transport | framing parse/serialize, JSON-RPC correlation | malformed `Content-Length` recovery |
| Conformance | full wire-protocol round trip with `FakeClient` | open → type → assert `publishDiagnostics` |
| Golden | examples **01–34** with golden snapshots (zero diagnostics + hover; sim-only examples use the first-annotation fallback position); a 20-example floor is enforced at import | `examples/02_lac_operon.helix` |
| Error matrix | one source per error class | §8.1 table |
| Latency | 64 KB synthetic file budgets | p95 diagnostics < 100 ms, hover < 50 ms |
| Cross-client | minimal echo client against `--stdio` and `--tcp` | smoke |

The conformance harness (`tests/conformance/client.py`) implements a tiny LSP
client and is reused by CI and by the Kotlin integration tests for golden
messages.

## 3. Kotlin side (IDE plugin)

### 3.1 Gradle build (`build.gradle.kts`)

```kotlin
plugins {
    kotlin("jvm") version "1.8.22"
    id("org.jetbrains.intellij") version "1.14.1"
}

intellij {
    version.set("PY-222.3345.118")   // PyCharm Community 2022.2 baseline
    type.set("PY")
    plugins.set(listOf("com.intellij.modules.python"))
    updateSinceUntilBuild.set(false)  // since-build only; no until-build
}

tasks {
    buildPlugin { }
    verifyPlugin { }
    runIde {
        ideDir.set(file("…/PyCharm-2022.2"))   // CI: both 222 and latest
    }
    patchPluginXml {
        sinceBuild.set("222.0")
    }
}
```

Targets: `buildPlugin` (zip), `verifyPlugin` (bundled verification),
`runIde` (smoke), `test` (fixtures).

### 3.2 Test pyramid (client)

| Layer | Framework | What |
|-------|-----------|------|
| Unit (pure) | JUnit 5 | `LspFraming` parser; `LspMessages` builders; version tracking; UTF-16 offset mapping |
| Transport | JUnit 5 + `FakeServerProcess` | stdio round trip against a stub process; backoff/restart logic |
| Handler mapping | JUnit 5 | JSON `Diagnostic` → `Annotation`; `CompletionItem` → `LookupElement` |
| Platform fixtures | `com.intellij.testFramework.fixtures` | open `.helix`, apply completion, assert popup items; annotator assertions with a stubbed diagnostics cache |
| Integration | real server subprocess + `EditorTestUtil` | start real `helixlang-lsp`, open file, assert diagnostics arrive and squiggles appear |
| E2E | Gradle `test` against `examples/*.helix` | zero-diagnostic corpus + navigation smoke |

All platform tests run headless (`HeadlessApplication`) on the 222 baseline and
on the latest IDE in CI.

## 4. CI pipeline (GitHub Actions)

Implemented in `.github/workflows/ci.yml` as two independent jobs:

```yaml
jobs:
  server:                       # Python 3.11, working-dir: server
    steps:
      - setup-python 3.11
      - pip install "helixlang @ git+https://github.com/SeanHank/HelixLang.git"
      - pip install -e ".[dev]"
      - ruff check .            # lint
      - mypy helixlang_lsp      # types
      - pytest tests --cov=helixlang_lsp --cov-fail-under=85   # gates + coverage
      - pytest tests/test_latency.py                           # budgets (no cov)
  plugin:                       # JDK 17, repo root
    steps:
      - setup-java temurin 17
      - ./gradlew build --no-daemon     # test + buildPlugin + verifyPlugin
      - upload build/distributions/*.zip
```

The reference env on dev machines is `/opt/anaconda3/envs/helix/bin/python`
(conda env `helix`; `helixlang` installed editable; pytest/ruff/mypy present).
CI installs the same packages in a fresh 3.11 environment, pulling `helixlang`
from the `HelixLang` repository's git `main`.

Gates: all of the above must pass before a PR merges. A nightly job runs the
server conformance suite against the latest `helixlang` from git `main` to catch
compiler-API drift (see §7).

## 5. Compatibility drift guard

The server imports a documented subset of the `helixlang` API. To keep the two
repos decoupled:

- A **contract file** (`server/helixlang_lsp/_helix_contract.py`) lists every
  imported symbol with its expected signature.
- CI runs `import-check`:
  `/opt/anaconda3/envs/helix/bin/python -c "from helixlang_lsp._helix_contract import *"`
  and a reflection check that each symbol exists with the expected arity.
- The nightly drift job fails loudly (and sends a notification) when the
  compiler API changes, instead of silently breaking the server.

## 6. Distribution

### 6.1 Plugin artifact

- `buildPlugin` produces `helixlang-ide-<version>.zip`.
- Release checklist:
  1. bump `pluginVersion` in `plugin.xml` + `version` in `pyproject.toml`;
  2. run full CI;
  3. tag `v<version>`;
  4. upload to **JetBrains Marketplace** (plugin id `com.helixlang.ide`).
- Marketplace categories: `Languages · Code editing`, `Build tools · Tools
  integration`.

### 6.2 Server artifact

- `helixlang-lsp` is published to PyPI (and included as `helixlang[lsp]`).
- The plugin does **not** bundle a pip installer by default; it auto-detects an
  interpreter with `helixlang_lsp` importable and offers one-click install in
  the settings dialog when missing (P1):
  `<python> -m pip install helixlang-lsp`.

### 6.3 Versioning policy

| Component | Versioning |
|-----------|------------|
| Plugin | `MAJOR.MINOR.PATCH`, marketplace channel `stable`; `eap` channel for previews |
| Server | independent `MAJOR.MINOR.PATCH`; `serverInfo.version` checked by the client |
| Compatibility | plugin declares `since-build` only; server is backward-compatible with the whole compiler API (contract file) |

## 7. Performance budgets

| Metric | Budget | Measured by |
|--------|--------|-------------|
| Diagnostics (64 KB file) | p95 < 100 ms | server latency tests |
| Hover | p95 < 50 ms | server latency tests |
| Completion round trip | < 100 ms end-to-end | client timing tests |
| Semantic token decode (client) | < 30 ms for 64 KB | client unit test |
| Server startup → initialized | < 1.5 s cold / < 0.3 s warm | E2E test |
| Memory | server RSS < 256 MB for a 100-file workspace | CI soak (P1) |

## 8. Manual verification checklist (release)

1. Fresh PyCharm 2022.2 install; plugin from disk zip loads with no errors.
2. Open `examples/02_lac_operon.helix` → zero squiggles; hover `GCT`; Ctrl+B on
   `p_lac`; Alt+F7 on `lacI`; structure view shows genes; fold `lacZ`.
3. Introduce a seeded error (remove a `TAA`) → single `parse` diagnostic with
   correct range; quick-fix appends `TAA`.
4. Run configuration runs `01_hello_dna.helix`; disassembly matches the CLI.
5. Kill the server process → status bar shows offline; restart is automatic.
6. Repeat 1–5 on latest PyCharm.

---

Next: [07 — Roadmap](./07-roadmap.md).
