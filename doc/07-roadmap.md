# 07 — Roadmap, Acceptance, and Risks

> Milestones, acceptance criteria, risk register, and future work for the
> HelixLang LSP plugin.

---

## 1. Milestones

### M0 — Foundations (wk 1–2)

- Repo scaffold: Gradle (IPGP 1.14, Kotlin 1.8, `PY-222`), Python package.
- `HelixFileType`/`HelixLanguage` + lexical highlighter + brace matcher +
  commenter.
- Mini-PSI parser + file template.
- Server skeleton: framing, dispatcher, `initialize`, empty `capabilities`.
- CI skeleton (server gates only).

**Exit criteria:** a `.helix` file opens with colored syntax in PyCharm 2022.2;
`helixlang-lsp --stdio` handshakes with a raw JSON-RPC client.

### M1 — Diagnostics (wk 3–4)

- `analysis.py` + `diagnostics.py`; error-recovery pipeline.
- Client: server manager, document sync, `HelixDiagnosticsAnnotator`,
  status-bar indicator, restart/backoff.
- Conformance + error-matrix tests; golden zero-diagnostic run on examples.

**Exit criteria:** every error class renders a correctly ranged squiggle; server
crash recovers within 10 s; golden tests green.

### M2 — Core editing features (wk 5–7)

- Hover, completion (with static fallback), go-to-definition, find references,
  document symbols, folding.
- Semantic tokens layer.
- 222-compatibility guards for inlay hints and tooltips.

**Exit criteria:** all P0 features in `doc/05` pass acceptance; full CI green on
222 + latest.

### M3 — Run & inspect (wk 7–8)

- `HelixRunConfigurationType` + producer; console output; interpreter
  auto-detection.
- Disassembly action + read-only tool window.

**Exit criteria:** CLI parity for run/disassemble on the example corpus
(01–34); settings UI complete.

### M4 — Polish & release (wk 9–10)

- Inlay hints (P0), quick-fixes, formatting (P1), DAP debugger (P1).
- Performance budgets, manual checklist, marketplace packaging.

**Exit criteria:** `v2026.8.1` published to JetBrains Marketplace; release blog.

### M5 — Hardening (ongoing)

- Watched-files re-scan, multi-workspace, TCP troubleshooting, Docker/remote
  transport (P2).

### M6 — Language-surface sync (upstream W-1…W-6) ✅

The upstream simulation wiring (`HelixLang/doc/helix-language-wiring.md`,
W-1…W-6, implemented upstream Aug 2026) extended the language with
`#config backend` (six backends), the structural annotations
`#media`/`#enzyme`/`#metabolite`, the open `#sim key=value` hook, `--backend`/
`--json` CLI flags, `POST /api/sim/run`, and four new examples (31–34) plus
rewrites of 10/16/20/21/24/30. The parser side flows into the server for free;
this milestone shipped the **feature-data sync** (§14 of `doc/03`, all items ✅):

- Semantic-token legend, completion (`ANNOTATION_KINDS`, `FIELD_SETS`,
  `ENUM_VALUES`), hover docs, and document-symbol nodes for the new
  annotations and `#config` sim keys / `backend` — shipped.
- Regenerated golden snapshots for examples 31–34 (and re-snapshotted the
  rewritten examples 10/16/20/21/24/30 whose content changed).
- Plugin: static-completion fallback table and the run-config
  `--backend`/`--json` fields (`doc/04` §5.3, §6.1) — shipped.

**Exit criteria:** zero diagnostics on all 34 examples with golden snapshots for
each; typing `#` completes all 18 kinds; `#config backend=` completes the six
backends; a sim-backend example runs from the IDE with CLI-identical output.

## 2. Acceptance criteria (v1.0)

| Area | Criterion |
|------|-----------|
| Compatibility | Plugin installs and runs on PyCharm 2022.2 and the latest stable in the same CI job. |
| Correctness | Zero diagnostics on all `examples/*.helix`; one diagnostic per seeded error in the corpus. |
| Features | Every P0 feature in `doc/05` passes its acceptance test. |
| Resilience | Server killed ⇒ auto-restart ≤ 5 attempts/10 min; no EDT freeze. |
| Performance | Budgets in `doc/06` §7 hold on CI hardware. |
| Quality gates | pytest+coverage≥85%, ruff, mypy, `verifyPlugin`, `buildPlugin`, platform tests green. |
| Docs | `doc/*` in sync with the implementation at release (doc-vs-code, code wins). |

## 3. Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|:----------:|:------:|------------|
| Compiler API drift breaks the server | Medium | High | Contract file + nightly drift job (`doc/06` §5). |
| 222-only APIs removed in newer IDE builds | Medium | High | Build against 222, CI on 222 + latest, version guards (`doc/04` §9). |
| LSP parsing of large files too slow | Low | Medium | Debounce, staged analysis, `include_compile=False` fast path, latency budgets. |
| Server process instability on user machines | Medium | Medium | Backoff restart, status indicator, `--trace` diagnostics, graceful degradation. |
| Python interpreter discovery fails | Medium | Medium | Resolution chain + one-click install (P1) + bundled fallback env (P1). |
| Semantic-token decode corruption | Low | Medium | Client round-trip test over generated corpus. |
| Upstream language surface outpaces server feature data | High | Medium | The W-1…W-6 wiring landed upstream (new annotations, backends, examples); the M6 milestone tracks the feature-data sync (`doc/03` §14); the golden floor test fails loudly on missing snapshots; the nightly drift job (`doc/06` §5) catches parser changes. |
| Scope creep into editor/compiler internals | Medium | High | Non-goals in `doc/01` §4 enforced in review; server never forks the compiler. |

## 4. Future work (backlog)

- **Remote & embedded transports:** Docker/SSH server launch, embedding the
  server in-process via a JVM-to-Python bridge (GraalPy) — improves cold start
  at the cost of portability.
- **Central-dogma-aware editor:** species-aware codon coloring, tRNA/codon-usage
  inlay annotations for `#config species=`.
- **Sim-surface editing aids:** completion of the registered `#sim kind=`
  long-tail backends (`spatial_dfba` + the 14 W-6 kinds); hover/validation of
  `#config sim` keys. Note: `SimConfigError` (bad typed-coercion values) is a
  *runtime* config error, not a static `HelixError`, so it stays out of the
  §8.1 diagnostic matrix by design.
- **Bio-module tooling:** CRISPR guide designer and protein-structure reports as
  IDE panels backed by the Python API (out of scope for v1 by design).
- **Editor-agnostic bonus:** because the server is editor-independent, a thin
  VS Code / Neovim client can reuse `helixlang_lsp` unchanged.
- **Team features:** `.helix` formatting on save, pre-commit hook generator,
  lint suppression comments (`# helix-ignore: <code>`).

---

*End of the HelixLang LSP plugin design. All documents in `doc/` are the
authoritative design reference for the `HelixLang-LSP-Plugin` repository.*
