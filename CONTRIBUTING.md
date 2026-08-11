# Contributing to HelixLang IDE

Thanks for your interest in HelixLang IDE! This project ships the **Language
Server Protocol (LSP) integration** for the HelixLang DSL: a Python language
server (`server/`) and an IntelliJ Platform plugin for PyCharm 2022.2+
(`src/`). The language itself lives in the sibling repository
[`SeanHank/HelixLang`](https://github.com/SeanHank/HelixLang).

Please read this guide before opening an issue or pull request.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Ground rules](#ground-rules)
- [Getting started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment & installation](#environment--installation)
- [Where things live](#where-things-live)
- [Finding something to work on](#finding-something-to-work-on)
- [Development workflow](#development-workflow)
  - [Branches](#branches)
  - [Commit messages](#commit-messages)
  - [Open a pull request](#open-a-pull-request)
- [Quality gates](#quality-gates)
  - [Language server (Python)](#language-server-python)
  - [Plugin (Kotlin / Gradle)](#plugin-kotlin--gradle)
  - [Golden tests need HelixLang examples](#golden-tests-need-helixlang-examples)
  - [Continuous integration](#continuous-integration)
- [Releases & versioning](#releases--versioning)
- [Coding conventions](#coding-conventions)
- [Documentation policy](#documentation-policy)
- [Reviewing and merging](#reviewing-and-merging)
- [License & contribution terms](#license--contribution-terms)

---

## Code of Conduct

Be respectful and constructive. This project welcomes contributors of all
levels. Reviewers give actionable, kind feedback; authors treat it as a
learning opportunity. Harassment or abusive behavior is not tolerated.

## Ground rules

- **Preserve the LSP contract.** Published messages, request shapes, and the
  extension registration in `plugin.xml` are the compatibility surface.
  Behavior changes must be additive or opt-in.
- **The server and the plugin evolve together.** A feature touching both sides
  (e.g. a new LSP capability) must land in one PR with both parts updated.
- **Never silently change defaults.** Legacy behavior is the compatibility
  contract.
- **Docs travel with code.** If you change behavior, update the affected
  `doc/*.md` files in the same pull request.

## Getting started

### Prerequisites

| Component | Requirement |
|---|---|
| JDK | **17** (required by Gradle 7.6 / the IntelliJ Platform Gradle Plugin) |
| Python | 3.11+ with the `helixlang` package importable |
| IDE (dev) | PyCharm 2022.2+ for `runIde` / manual installs |

### Environment & installation

```bash
git clone https://github.com/SeanHank/HelixLang-LSP-Plugin.git
cd HelixLang-LSP-Plugin

# Language server (editable, with dev extras)
python -m pip install -e "server[dev]"

# Plugin — build with JDK 17
JAVA_HOME=/path/to/jdk-17 ./gradlew build
```

The server depends on the `helixlang` package (from PyPI or installed from the
sibling repository). For the golden tests you additionally need a local
[`SeanHank/HelixLang`](https://github.com/SeanHank/HelixLang) checkout — see
[Golden tests need HelixLang examples](#golden-tests-need-helixlang-examples).

## Where things live

```
server/                        Python language server (helixlang-lsp)
  helixlang_lsp/               analysis, LSP features, protocol, server
  tests/                       pytest suite + tests/golden/ snapshots
src/main/kotlin/com/helixlang/ PyCharm plugin (Kotlin): filetype, psi, lsp, run, debug, actions
src/main/resources/META-INF/   plugin.xml descriptor + pluginIcon.svg
src/test/kotlin/               JUnit 5 plugin tests
doc/                           design documents (authoritative reference)
.gradle / build / out          generated (never commit)
```

Key entry points:

- `doc/03-language-server.md` — language server design and golden-test spec.
- `doc/04-intellij-plugin.md` — PyCharm client design + implementation status.
- `doc/06-build-testing.md` — build, quality gates, CI, distribution.
- `server/pyproject.toml` — ruff / mypy / pytest configuration.
- `build.gradle.kts` + `gradle.properties` — plugin build and versioning.

## Finding something to work on

- **Issues**: look for `good first issue` / `help wanted` labels.
- **TODO markers**: `grep -rn "TODO" server src`.
- **Coverage gaps**: `pytest --cov=helixlang_lsp --cov-report=term-missing` and
  pick an uncovered branch.
- **Docs drift**: a PR that fixes stale `doc/*.md` or docstrings is always
  appreciated.

Not sure where to start? Open an issue describing what you'd like to do before
writing code — maintainers can point you at the right component and expected
design.

## Development workflow

### Branches

Fork the repository, then create a focused branch off `main`:

```bash
git checkout -b fix/completion-uri          # fixes
git checkout -b feat/inlay-hint-kinds       # features
git checkout -b docs/update-architecture    # documentation
```

Keep each PR to **one logical change**. Small PRs review faster and are less
likely to bit-rot.

### Commit messages

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add hover support for #regulate blocks
fix: resolve relative URIs in diagnostics
test: cover golden snapshot for the lac operon example
docs: document the auto-release workflow
```

Include *what* and *why* in the body when it isn't obvious from the subject.

### Open a pull request

1. Push your branch to your fork.
2. Open a PR against `main`.
3. Fill in the PR template (what changed, why, how it was tested).
4. Make sure all [quality gates](#quality-gates) pass locally before requesting
   review.

## Quality gates

Every PR must pass the gates below — they are exactly what CI runs.

### Language server (Python)

From `server/`:

```bash
python -m ruff check .
python -m mypy helixlang_lsp
python -m pytest tests --cov=helixlang_lsp --cov-fail-under=85
```

- Coverage gate is **85%** (see `server/pyproject.toml`).
- Run a single file: `python -m pytest tests/test_hover.py`
- **Latency budgets** run un-instrumented, because they skip themselves under
  pytest-cov:

  ```bash
  python -m pytest tests/test_latency.py
  ```

- **When you add behavior, add tests.** New LSP features must ship with a
  validation suite that asserts the protocol payload, not just "it doesn't
  crash".

### Plugin (Kotlin / Gradle)

```bash
JAVA_HOME=/path/to/jdk-17 ./gradlew build
```

`build` runs the JUnit tests, `buildPlugin` (zip) and `verifyPlugin`
(structural verification of `plugin.xml` and the distribution). The artifact
lands in `build/distributions/helixlang-ide-<version>.zip`.

For a live sandbox: `JAVA_HOME=/path/to/jdk-17 ./gradlew runIde`.

### Golden tests need HelixLang examples

`tests/test_golden.py` replays 20 `.helix` examples from the
[`SeanHank/HelixLang`](https://github.com/SeanHank/HelixLang) repository and
compares diagnostics + hover against the recorded snapshots in
`tests/golden/`. The examples are **not** bundled with the `helixlang` package,
so point the tests at a checkout:

```bash
git clone https://github.com/SeanHank/HelixLang.git /tmp/HelixLang
HELIX_EXAMPLES_DIR=/tmp/HelixLang/examples \
  python -m pytest tests/test_golden.py
```

(CI does this automatically via `actions/checkout`.)

When the `.helix` corpus or the server's output changes, regenerate snapshots
with `python tests/generate_golden.py` (same `HELIX_EXAMPLES_DIR`), then
review the diff — golden drift must be intentional.

### Continuous integration

`.github/workflows/ci.yml` runs, on every push/PR:

| Job | Runs |
|-----|------|
| `server` | Python 3.11: `ruff` + `mypy` + `pytest --cov-fail-under=85` + latency budgets |
| `plugin` | JDK 17: `./gradlew build` + uploads the plugin zip artifact |
| `release` | (push to `main` only) publishes a GitHub Release — see below |

Green CI is required before merge. If you can't reproduce a CI-only failure,
mention it in the PR.

## Releases & versioning

Every push to `main` builds the plugin and **publishes a GitHub Release**
tagged `v<version>` (created or updated), with the plugin zip attached.

The version is configured in **one place**:
[`gradle.properties`](gradle.properties) → `pluginVersion=1.0.0`.

- Bump `pluginVersion` and push → CI releases `v1.0.1`, `v1.1.0`, …
- Re-pushing the same version overwrites that release (delete + recreate).

## Coding conventions

- **Follow the surrounding style.** Match the file you're editing — imports,
  docstrings, and section layout.
- **Python (server):** type annotations mandatory in `helixlang_lsp` (enforced
  by mypy); named constants over magic literals; protocol messages serialized
  through the `to_dict()`/`from_dict()` dataclasses in `helixlang_lsp/protocol.py`.
- **Kotlin (plugin):** follow the IntelliJ Platform conventions; register every
  extension in `META-INF/plugin.xml` with the correct extension point and
  `language="Helix"` where applicable. Plugin icons live at
  `META-INF/pluginIcon.svg` / `pluginIcon_dark.svg` (PyCharm 2022.2 reads those
  entries — not the `<icon>` element).
- **No dead code.** Delete the code you're replacing; don't leave commented-out
  alternatives.

## Documentation policy

The project states: *"docs and code are kept in sync; when they conflict, the
code prevails."* Behavior changes must update the affected `doc/*.md` in the
same PR:

- Language server behavior → `doc/03-language-server.md`
- PyCharm client / extensions → `doc/04-intellij-plugin.md`
- Feature specs → `doc/05-features.md`
- Build / CI / distribution → `doc/06-build-testing.md`

If you notice stale docs while working on something else, fixing them in the
same PR is appreciated — but call it out in the description.

## Reviewing and merging

- PRs need **one approving review** from a maintainer.
- The reviewer checks: gates green, LSP contract preserved (or intentionally
  changed with a release note), both server and plugin updated together where
  relevant, docs updated, tests meaningful.
- Maintainers follow the same standards as contributors — no rubber-stamping.

## License & contribution terms

This project is licensed under the **GNU Affero General Public License v3.0**
(`LICENSE`). Copyright © 2026 Sean Hank.

By opening a pull request, you agree that your contribution is offered under
the project's license (inbound = outbound). If your contribution incorporates
third-party code or data, ensure its license is compatible with AGPL-3.0 and
note the attribution in the PR.

Questions about licensing, contributing, or anything else? Open an issue — we
prefer public discussion so the whole community benefits.
