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

**Exit criteria:** CLI parity for run/disassemble on all 20 examples; settings
UI complete.

### M4 — Polish & release (wk 9–10)

- Inlay hints (P0), quick-fixes, formatting (P1), DAP debugger (P1).
- Performance budgets, manual checklist, marketplace packaging.

**Exit criteria:** `v1.0.0` published to JetBrains Marketplace; release blog.

### M5 — Hardening (ongoing)

- Watched-files re-scan, multi-workspace, TCP troubleshooting, Docker/remote
  transport (P2).

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
| Scope creep into editor/compiler internals | Medium | High | Non-goals in `doc/01` §4 enforced in review; server never forks the compiler. |

## 4. Future work (backlog)

- **Remote & embedded transports:** Docker/SSH server launch, embedding the
  server in-process via a JVM-to-Python bridge (GraalPy) — improves cold start
  at the cost of portability.
- **Central-dogma-aware editor:** species-aware codon coloring, tRNA/codon-usage
  inlay annotations for `#config species=`.
- **Bio-module tooling:** CRISPR guide designer and protein-structure reports as
  IDE panels backed by the Python API (out of scope for v1 by design).
- **Editor-agnostic bonus:** because the server is editor-independent, a thin
  VS Code / Neovim client can reuse `helixlang_lsp` unchanged.
- **Team features:** `.helix` formatting on save, pre-commit hook generator,
  lint suppression comments (`# helix-ignore: <code>`).

---

*End of the HelixLang LSP plugin design. All documents in `doc/` are the
authoritative design reference for the `HelixLang-LSP-Plugin` repository.*
