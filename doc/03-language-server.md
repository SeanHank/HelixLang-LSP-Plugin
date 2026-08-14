# 03 — The Helix Language Server

> Complete design of the Python language server that gives editors LSP features
> for HelixLang. This document is the contract between the server and any LSP
> client, including our PyCharm plugin.

---

## 1. Goals

The server's single job is to **translate editor events into compiler calls and
compiler results into LSP messages**. It adds no language semantics of its own;
every answer is derived from `src/helixlang/` (lexer, parser, semantic
analyzer, compiler, codon table, disassembler, debugger, errors).

- G1: Publish correct, positioned diagnostics for every compiler error class.
- G2: Answer all features listed in §5 with sub-100 ms latency on files up to
  64 KB.
- G3: Run on any CPython 3.11+ using only the standard library.
- G4: Be fully testable headlessly (no GUI), so the conformance suite runs in CI.

## 2. Runtime and packaging

### 2.1 Reference environment

The canonical development/reference interpreter (mirroring
`HelixLang/doc/engineering-design.md` §1.1) is the absolute path

```
/opt/anaconda3/envs/helix/bin/python
```

- Conda environment `helix`, **Python 3.11.15**.
- `helixlang` is installed editable (`pip install -e /Users/admin/PycharmProjects/HelixLang`).
- `pytest`, `ruff`, and `mypy` are available in the same environment.
- **Mandatory constraint:** every command-line example, CI script, and IDE run
  configuration must use the absolute path above, to avoid accidentally using
  the system Python.

### 2.2 Packaging

| Item | Value |
|------|-------|
| Language | Python 3.11+ (`requires-python = ">=3.11"`) |
| Dependencies | `helixlang` (required), standard library only otherwise |
| Entry points | console script `helixlang-lsp`; `python -m helixlang_lsp` |
| Transport | stdio (default), TCP (`--host --port`) |
| Extra flags | `--trace <file>` (JSONL transcript), `--loglevel` |
| Distribution | published as `helixlang[lsp]` extra of the HelixLang distribution, and as a standalone `helixlang-lsp` package |

Example invocation from the client:

```
/opt/anaconda3/envs/helix/bin/python -m helixlang_lsp --stdio
```

## 3. JSON-RPC 2.0 transport

### 3.1 Framing

Standard LSP framing: messages are prefixed with a header block terminated by
`\r\n\r\n`, carrying `Content-Length: <bytes>` (and optional
`Content-Type: application/vscode-jsonrpc; charset=utf-8`), followed by a UTF-8
JSON body.

```python
# reader: parse header, read Content-Length bytes, json.loads the body
def read_message(r) -> dict | None
def write_message(w, msg: dict) -> None   # serialize, prepend headers
```

- Requests: `{jsonrpc, id, method, params}`
- Responses: `{jsonrpc, id, result | error{code,message,data}}`
- Notifications: `{jsonrpc, method, params}` (no id)
- The server must **always** respond to requests with matching ids; unknown
  methods return `MethodNotFound (-32601)`.

### 3.2 Message flow (server side)

```
reader thread ──> inbound Queue ──> worker loop
                                    ├─ request  → handle → outbound Queue
                                    ├─ notify   → handle → maybe publish
                                    └─ shutdown → flush → exit
```

Outbound writer flushes messages; large `publishDiagnostics` batches are split
if needed (max 512 diagnostics per message, remainder queued).

## 4. Lifecycle handshake

| Request/Notification | Server behavior |
|----------------------|-----------------|
| `initialize` | Validate params (processId, rootUri/workspaceFolders, capabilities). Return `capabilities` (see §6), `serverInfo {name:"helixlang-lsp", version}`. |
| `initialized` | Start workspace scan; subscribe to `workspace/didChangeConfiguration` (settings), `workspace/didChangeWatchedFiles` (P1: directory scan). |
| `shutdown` | Flush analysis, return `null`. |
| `exit` | Exit process with code 0 if shutdown received, else 1. |
| `$/cancelRequest` | If a request is still queued, drop it; if in-flight (analysis), mark result stale and discard. |

## 5. Supported LSP capabilities

| Capability | Method(s) | Detail |
|-----------|-----------|--------|
| `textDocumentSync` | `didOpen`, `didChange` (incremental, versioned), `didSave`, `didClose` | full text on open; `range`+`text` deltas on change |
| `diagnosticProvider` | `textDocument/publishDiagnostics` | server-pushed, `interFileDependencies=false` |
| `hoverProvider` | `textDocument/hover` | Markdown content |
| `completionProvider` | `textDocument/completion` | `triggerCharacters` = `#= >`, no resolve needed (P0) |
| `definitionProvider` | `textDocument/definition` | gene/promoter definitions |
| `referencesProvider` | `textDocument/references` | `{includeDeclaration}` |
| `documentSymbolProvider` | `textDocument/documentSymbol` | hierarchical, `hierarchicalDocumentSymbolSupport=true` |
| `foldingRangeProvider` | `textDocument/foldingRange` | annotation blocks, DNA bodies |
| `semanticTokensProvider` | `textDocument/semanticTokens/full` (+`/range`, P1) | legend in §9, relative delta encoding |
| `codeActionProvider` | `textDocument/codeAction` | `codeActionKinds` (quickfix) |
| `documentFormattingProvider` | `textDocument/formatting` | codon normalization (§10) |
| `inlayHintProvider` | `textDocument/inlayHint` | decoded-opcode annotations after each codon |
| `workspaceSymbolProvider` | `workspace/symbol` | cross-file symbol index |
| `executeCommandProvider` | `workspace/executeCommand` | `helix.disassemble` (P1) |

`serverCapabilities` JSON (initialize result):

```json
{
  "textDocumentSync": {
    "openClose": true,
    "change": 2,
    "save": { "includeText": false }
  },
  "hoverProvider": true,
  "completionProvider": { "triggerCharacters": ["#", "=", ">"] },
  "definitionProvider": true,
  "referencesProvider": true,
  "documentSymbolProvider": true,
  "foldingRangeProvider": true,
  "diagnosticProvider": { "interFileDependencies": false, "workspaceDiagnostics": false },
  "semanticTokensProvider": {
    "legend": { "tokenTypes": ["keyword","type","function","variable","number","string","comment","operator","arrow"], "tokenModifiers": ["declaration","defaultLibrary"] },
    "range": false,
    "full": true
  },
  "codeActionProvider": { "codeActionKinds": ["quickfix"] },
  "documentFormattingProvider": true,
  "inlayHintProvider": true,
  "workspaceSymbolProvider": true
}
```

## 6. Text and position model

### 6.1 Source ↔ LSP mapping

The compiler reports positions as **1-based line/col** (`HelixError.line`,
`HelixError.col`) and a global **0-based codon index**; LSP uses **0-based**
UTF-16 code-unit offsets. The server owns this conversion in `positions.py`.

| Concept | Compiler | LSP |
|---------|----------|-----|
| line | 1-based | 0-based |
| column | 1-based | 0-based (UTF-16 units) |
| codon index | global, 0-based, across the file | not represented; used for messages |

```python
def linecol_to_position(text: str, line1: int, col1: int) -> Position
    # line1/col1 are 1-based from the compiler
    # → Position(line=line1-1, character=utf16_offset(text, line1-1, col1-1))
```

For ASCII DNA/codons the UTF-16 offset equals the code-unit offset, so this is
cheap; the conversion is still correct for annotations containing non-BMP
characters.

### 6.2 Range selection for diagnostics

Errors frequently carry a line but no exact column. The server resolves the
best-effort range by scanning the line:

1. If `line == 0` and the message references a codon, locate the codon's
   `CODON` token range via the lexer and use it.
2. Else if `col > 0`, use a single-character range at `(line-1, col-1)`.
3. Else use the first non-whitespace token on the line; fall back to the whole
   line.
4. `ParseError` from ORF handling (`no START codon`, `ORF not terminated`)
   span the gene's `#gene` line to its `#end` line (or EOF).

## 7. Analysis pipeline

### 7.1 Compilation wrapper

`analysis.py` exposes one function used by every feature:

```python
@dataclass
class Analysis:
    program: Program | None
    tokens: list[Token]
    chunk: Chunk | None
    diagnostics: list[Diagnostic]
    symbols: SymbolTable        # definitions + references
    disassembly: str | None     # lazily produced for hover/actions
    table_name: str             # effective translation table

def analyze(text: str, uri: str, *, include_compile: bool = True,
            table_hint: str | None = None) -> Analysis
```

Internal steps (mirroring `cli.main`):

```
1. table      = get_table(config.table or "standard")
2. stop       = stop_codons_from_table(table)
3. tokens     = list(Lexer(text).tokens())
4. program    = Parser(tokens, stop_codons=stop, enable_type_check=True).parse()
5. SemanticAnalyzer(program).check()         # raises SemanticError / RegulationError
6. chunk      = Compiler(table).compile(program)
```

**Robustness:** the pipeline collects *all* resolvable errors instead of
failing fast. Because the parser raises on the first error, the server runs a
small "error recovery" mode:

- Run the full pipeline once.
- If a `LexError` is raised, report it and stop (lexical errors make further
  analysis meaningless).
- If a `ParseError`/`SemanticError`/`RegulationError`/`CompileError` is raised,
  report it **and** continue with a partial program where possible (the parser
  yields partial AST before raising on the offending annotation, and
  `program.genes`/`program.promoters` are still usable for navigation).

This gives editors "many squiggles at once" instead of one-at-a-time.

### 7.2 Incremental re-analysis

- `didChange` deltas are applied to the cached text (client sends incremental
  edits); full re-analysis runs on the worker thread.
- Debounce: re-analysis is scheduled **200 ms** after the last change (configurable
  via `helix.lsp.diagnostics.debounce`). A newer change cancels the pending job.
- Per-file analysis caching is keyed by `(uri, version)`; results for a
  completed analysis are reused for hover/completion until the text changes.
- Compilation (`Compiler.compile`) is skipped for hover/completion/folding
  unless the feature needs bytecode; most features use the **parse + semantic**
  stage only. `include_compile=False` is the default fast path.

### 7.3 Effective translation table

The table selection affects ORF stop-codon detection and opcode decoding:

- Parse the source once to read `#config table=…` (cheap pre-pass).
- Default `standard`; valid values from `TABLES` (`standard`,
  `mito_vertebrate`, `ciliate`).
- If `#config table=` is invalid, emit a diagnostic on the `#config` line and
  fall back to `standard`.
- The `table_name` is carried into every feature result (hover shows the table
  that produced the decoding).

### 7.4 Simulation surface (upstream W-1…W-6)

Since the simulation wiring, the upstream parser also exposes:

- `#config backend = classic | whole_cell | population | fba | calibration |
  benchmark` (`classic` default) → `Program.config.backend`;
- every other `#config` key collected verbatim into `Program.config.sim`
  (typed coercion is the sim adapter's job, `SimConfigError` on bad values);
- the structural annotations `#media` / `#enzyme` / `#metabolite` and the open
  `#sim key=value` extension point (`Program.sim_extensions`) — parsed by the
  upstream parser, inert (warned) under `classic`.

The server reads these through the same `Analysis` object (§7.1); none of them
change the classic compile pipeline. The server's lenient structural pass
(`analysis.py` `_structural_check`) accepts them via its extended
`ANNOTATION_KINDS` and `REQUIRED_FIELDS` (item 1 in the §14 sync table, ✅).

## 8. Diagnostics

### 8.1 Error → diagnostic mapping

Source of truth: `src/helixlang/errors.py`. Mapping in `diagnostics.py`:

| `HelixError` subclass | Severity | `code` | Examples |
|-----------------------|----------|--------|----------|
| `LexError` | Error | `lex` | "DNA length N not multiple of 3"; "unexpected char" |
| `ParseError` | Error | `parse` | unknown annotation; missing field; no START codon; ORF unterminated; type-check failure |
| `SemanticError` | Error | `semantic` | duplicate symbol; unknown promoter reference; empty ORF; invalid config |
| `RegulationError` | Error | `regulation` | `#regulate` source/target not defined |
| `CompileError` | Error | `compile` | unknown codon; CALL_GENE target not defined |
| `RuntimeHelixError` | Error | `runtime` | only if VM validation is enabled (§8.3) |
| `BioError` | Error | `bio` | bio-instruction validation (central-dogma mode) |
| semantic **warnings** (regulation cycles) | Warning | `warning` | `SemanticAnalyzer.warnings` |

`Diagnostic` fields:

```json
{
  "range": { "start": { "line": 0, "character": 4 }, "end": { "line": 0, "character": 7 } },
  "severity": 1,
  "code": "parse",
  "source": "helix",
  "message": "[ParseError @ line 5] #gene 'x' has no START codon (ATG)",
  "data": { "codonIndex": 12, "className": "ParseError" }
}
```

- The compiler's `__str__` message (already `[Kind @ line N codon #M] msg`) is
  kept verbatim as the user-facing message; `data.className` lets the client
  map to quick-fixes.
- **`relatedInformation`**: `CompileError` about `OP_CALL_GENE` target not
  defined links the caller codon to the definition site (if any) of the target.

### 8.2 Warnings

- `SemanticAnalyzer` collects warnings into `warnings: list[str]` (e.g.
  `regulation cycle detected at 'p_lac'`). The server turns these into
  `severity=Warning` diagnostics with a range on the first node of the cycle.
- Cycles must remain warnings (never errors) per the language spec.

### 8.3 Optional runtime validation

By default the server performs **static** analysis only (a `.helix` file is a
program; running it on every keystroke is wasteful and would consume CPU). An
opt-in `helix.validate.runVm` (default `false`) runs the VM for the configured
`ticks` after each analysis and adds `RuntimeHelixError` diagnostics, capped at
`ticks<=64` to bound cost. The PyCharm settings UI exposes this with a warning.

## 9. Semantic tokens

- **Token types** in the legend: `keyword` (annotation kinds `#gene`,
  `#promoter`, `#regulate`, `#lsystem`, `#field`, `#config`, `#type`,
  `#crispr`, `#evolve`, `#methylate`, `#histone`, `#transcribe`,
  `#translate`, `#quorum`, `#media`, `#enzyme`, `#metabolite`, `#sim`,
  `#end`), `type` (type annotations: `Protein`,
  `Signal`, `Float`, …), `function` (gene symbols), `variable` (promoter
  symbols), `number` (field values), `string` (quoted values), `comment`
  (`# ...`), `operator` (`->`).
- **Codon classification** (the interesting case): each codon token is tagged by
  its decoded opcode family:
  - `OP_START` → `keyword`, modifier `defaultLibrary`
  - `OP_HALT` → `keyword`
  - `OP_BUILD_PROTEIN` / `OP_BUILD_MEMBRANE` / `OP_BUILD_PIGMENT` → `function`
  - `OP_MOVE` / `OP_SIGNAL` / `OP_DIVIDE` / `OP_DIE` / `OP_FEED` → `variable`
  - morphology/regulation/memory/arithmetic opcodes → `operator`
  - unknown codon → `string` (renders as error-colored via a `Diagnostic` too)
- **Encoding:** standard LSP relative delta encoding (first token absolute,
  then `{deltaLine, deltaStartChar, length, tokenType, tokenModifiers}`), one
  token per source codon / annotation token.
- The client re-requests full tokens when it receives the pushed
  `workspace/diagnostic` or a `textDocument/semanticTokens/full` invalidated by
  its own edit tracking; the server recomputes from the cached analysis.

## 10. Feature specifications

### 10.1 Hover

Contents (Markdown):

- **On a codon:** the decoded opcode, operand, amino acid, and the wobble value:
  `GCT → OP_BUILD_PROTEIN (Ala), operand=0 (wobble A)` plus a link-style note of
  the effective table. Includes the full codon family table for the family
  (all aliases).
- **On an annotation kind:** its grammar + allowed fields (from the language
  spec, embedded as server-side doc data) — including `#media`
  (`nutrient=`/`concentration=`/`diffusion_um2_s=`), `#enzyme`
  (`gene=`/`reaction=`/`kcat=`), `#metabolite` (`name=`/`init=`), and `#sim`
  (open `key=value`; the `kind=` values dispatch to long-tail backends).
- **On a gene/promoter name:** definition line, promoter, ORF summary (start/
  stop codons, amino-acid count), and any regulation edges touching it.
- **On a field name/value:** documented field semantics (e.g. `strength`
  ranges, `table` choices, `output` formats, `units` choices, `species`).
- **On a config value:** config defaults and allowed values — including
  `backend` (`classic | whole_cell | population | fba | calibration |
  benchmark`, default `classic`) and the typed sim keys (§7.4; the coerceable
  enums `division_rule`, `replication_mode`, `protein_maturation_mode`,
  `mechanics`, and `fba_model=core|<path>`, `seed=`, and the redefined
  `output=` column selection for sim backends).

### 10.2 Completion

Trigger characters: `#`, `=`, `>`, and word-start inside annotations. Context
sensitive:

| Context | Items |
|---------|-------|
| after `#` | annotation kinds (`gene`, `promoter`, `regulate`, `lsystem`, `field`, `config`, `type`, `crispr`, `evolve`, `methylate`, `histone`, `transcribe`, `translate`, `quorum`, `media`, `enzyme`, `metabolite`, `sim`) with doc summaries |
| annotation field names | per-kind field list: `#gene`: `name`, `promoter`, `call_target`; `#media`: `nutrient`, `concentration`, `diffusion_um2_s`; `#enzyme`: `gene`, `reaction`, `kcat`; `#metabolite`: `name`, `init`; `#config`: the classic keys (`ticks`, `output`, `table`, `ops_per_tick`, `react_steps`, `use_central_dogma`, `species`, `units`) plus `backend` and the sim keys (wiring doc `helix-language-wiring.md` §6.2; §7.4 here); `#sim`: open `key=value` (`kind=` for the long-tail backends); … |
| field values | enums: `backend` ∈ {classic, whole_cell, population, fba, calibration, benchmark}; `table` ∈ {standard, mito_vertebrate, ciliate}; `species` ∈ {ecoli, yeast, human}; `units` ∈ {gameplay, real}; `output` ∈ {stdout, csv, png, none} (classic) / a comma-separated column list (sim backends); `division_rule` ∈ {energy, adder}; `replication_mode` ∈ {flat, cooper_helmstetter}; `protein_maturation_mode` ∈ {instant, chaperone}; `mechanics` ∈ {none, shove, …}; `dynfba`/`signaling`/`crowding`/`dfba` ∈ {true, false}; `fba_model` ∈ {core, \<path\>}; `cas` ∈ {SpCas9, SaCas9, Cas12a}; `repair` ∈ {NHEJ, HDR}; `mark` ∈ {H3K4me3, H3K27me3, H3K36me3, H3K9me3, H3K27ac}; `methylase` ∈ {dam, dcm, cpg} |
| `name=`, `promoter=` in `#gene` | defined promoters (from symbol table) |
| `source -> ` / `-> target` in `#regulate` | defined genes/promoters |
| `target=` in bio instructions | defined genes |
| after codons | codon snippets (the 64 codons) with decoded opcode in detail |
| `#type` value | `Protein`, `Signal`, `Float`, `Int`, `Bool`, `String`, `Gene`, `Record`, `Any` |

Each item carries `kind` (Keyword/Variable/Function/…), `documentation`, and a
`sortText` that keeps required fields first.

### 10.3 Definition & references

- `textDocument/definition`: resolves a symbol **reference** (right side of
  `#regulate`, `promoter=`, `target=`, `call_target=`, codon `OP_CALL_GENE`
  wobble→gene-name mapping, `#type` symbol) to the definition `Location`.
- `textDocument/references`: walks the symbol table for the definition and
  returns all usage `Location`s. `includeDeclaration` honored.
- Symbol table entries:

```python
@dataclass
class SymbolOccurrence:
    name: str
    kind: "gene" | "promoter" | "type"
    definition: Range          # in definition document
    usages: list[Range]        # in referencing documents
    doc_uri: str
```

The index is **per-workspace**: the server scans `**/*.helix` under the
workspace folders on `initialized`, re-scans on `workspace/didChangeWatchedFiles`
(P1), and merges per-document analyses. Cross-file go-to-definition works for
symbols defined in other files.

### 10.4 Document symbols (hierarchical)

```
Program
 ├─ Gene name="lacZ"            (kind=Function)
 ├─ Gene name="lacI"            (kind=Function)
 ├─ Promoter name="p_lac"       (kind=Variable)
 ├─ Regulation p_lacI -> lacI   (kind=Operator)
 ├─ LSystem name="plant"        (kind=Class)
 ├─ Field size=32               (kind=Class)
 ├─ Media nutrient=GLC          (kind=Class)
 ├─ Enzyme gene=glk             (kind=Class)
 ├─ Metabolite name=glc__D      (kind=Class)
 ├─ Sim kind=spatial_dfba       (kind=Event)
 ├─ Config                     (kind=Constant)
 └─ BioInstructions (#crispr…)  (kind=Event)
```

`selectionRange` = the name range; `range` = whole block.

### 10.5 Folding ranges

- `#gene … #end` blocks (kind `region`).
- DNA bodies longer than 3 lines (kind `region`).
- Long annotation fields (lsystem rules strings) — disabled by default.
- The structural annotations `#media`/`#enzyme`/`#metabolite`/`#sim` are
  single-line declarations (no `#end`); like `#field` and `#config` they
  produce no folding region of their own.
- Client-side fallback folding (see plugin doc) mirrors these rules when the
  server is offline.

### 10.6 Code actions

| Action | When | Effect |
|--------|------|--------|
| `helix.fix.unterminatedOrf` | `parse` error "ORF not terminated" | suggest appending `TAA` (preview + apply via workspace/edit) |
| `helix.fix.dnaLength` | `lex` error "not multiple of 3" | suggest removing last N bases (preview) |
| `helix.fix.addName` | `parse` error "missing name=" | suggest inserting `name=<cursor>` |
| `helix.disassemble` | always (P1) | `workspace/executeCommand` → returns disassembly string; client opens a read-only viewer |

All edits are returned as LSP `WorkspaceEdit`s; the client applies them on
confirmation.

### 10.7 Formatting (`textDocument/formatting`)

A conservative, semantics-preserving formatter:

- Normalize codon spacing: group every 3 bases with single spaces
  (`ATG GCT GGT TAA`), one ORF per line by default, aligned to `#gene` indentation.
- Keep annotation field `key=value` spacing; align consecutive `=` signs within
  a block (optional, off by default).
- Do **not** reorder fields, change DNA case, or rewrite `#regulate` arrows.
- Provide `insertSpaces`/`tabSize`-aware output using the client's editor
  options.

### 10.8 Inlay hints

For each codon in a gene body, an inlay hint after the codon text:

```
ATG GCT GGT TAA
    ▲    ▲    ▲
    │    │    │
    OP_START  OP_BUILD_PROTEIN arg=0  OP_BUILD_MEMBRANE arg=1  OP_HALT
```

Hint data: `{kind:"codon", opcode:"OP_BUILD_PROTEIN", operand:0, codon:"GCT",
table:"standard"}`. Client renders text hints; P1 adds tooltips (hover on the
hint shows the amino-acid family table).

### 10.9 Workspace symbol

`workspace/symbol` query across the per-workspace symbol index; supports
wildcard `*` and camel-case fuzzy matching. Used by the IDE's "Go to Symbol"
(Cmd+O style) for `.helix`.

## 11. Server settings (`workspace/didChangeConfiguration`)

| Key | Default | Meaning |
|-----|---------|---------|
| `helix.lsp.diagnostics.enabled` | `true` | publish diagnostics |
| `helix.lsp.diagnostics.debounceMs` | `200` | re-analysis debounce |
| `helix.lsp.validate.runVm` | `false` | opt-in runtime validation (capped `ticks<=64`) |
| `helix.lsp.completion.triggerOnCodons` | `true` | codon completion items |
| `helix.lsp.semanticTokens.enabled` | `true` | emit semantic tokens |
| `helix.lsp.inlayHints.enabled` | `true` | emit inlay hints |
| `helix.lsp.formatting.alignEquals` | `false` | align `=` in annotation blocks |

## 12. Server Python API surface (for tests and reuse)

| Module | Public API |
|--------|------------|
| `helixlang_lsp.jsonrpc` | `read_message`, `write_message`, `JsonRpcError`, `ErrorCodes` |
| `helixlang_lsp.protocol` | `Position`, `Range`, `Location`, `Diagnostic`, `CompletionItem`, `Hover`, `SemanticToken`, … |
| `helixlang_lsp.server` | `HelixLspServer.run(transport)` |
| `helixlang_lsp.analysis` | `analyze(text, uri, ...) -> Analysis`, `SymbolTable` |
| `helixlang_lsp.diagnostics` | `errors_to_diagnostics(exc, text, ...) -> list[Diagnostic]` |
| `helixlang_lsp.positions` | `linecol_to_position`, `position_to_linecol`, `utf16_offset` |
| `helixlang_lsp.features.*` | pure functions `(text, analysis, params) -> LSP result` |

All feature handlers are **pure functions** over `(text, analysis)` so they can
be unit-tested without the transport.

## 13. Testing contract

- **Conformance tests** (pytest) drive the server through its public entry point
  with a `FakeClient` that speaks the LSP wire protocol: open a file, type,
  assert `publishDiagnostics` payloads; request hover/completion/etc., assert
  exact JSON shapes.
- **Golden files:** for each `examples/*.helix`, a golden
  `publishDiagnostics` snapshot (expected zero errors) and a hover snapshot for
  representative positions. Snapshots currently exist for examples **01–34**
  (`31_whole_cell_adder.helix`, `32_colony_dfba.helix`,
  `33_fba_diauxie.helix`, `34_whole_cell_calibration.helix`, plus the
  rewritten 10/16/20/21/24/30 and the W-6 `#sim kind=` examples).
  `tests/test_golden.py` enforces a **20-example floor** at import and fails on
  any example without a snapshot. For examples with no codons (sim-only), the
  snapshot hover position falls back to the first annotation.
- **Error matrix tests:** every row of the §8.1 table is exercised with a
  crafted source that triggers exactly that error.
- **Latency budget tests:** analyze a synthetic 64 KB file; assert
  `p95 < 100 ms` for diagnostics and `p95 < 50 ms` for hover on CI-class
  hardware. These tests **skip themselves when run under pytest-cov
  instrumentation** (the trace hook inflates per-call timings), so CI runs them
  in a separate un-instrumented step.
- **Cross-client compatibility:** a smoke test runs the `client_test`
  utilities from the LSP spec (if available) or a minimal JSON-RPC echo client.

---

## 14. Language-surface sync status (upstream W-1…W-6)

The upstream language surface changed in `HelixLang/doc/helix-language-wiring.md`
(W-1…W-6, implemented upstream Aug 2026). The upstream parser/AST already
expose it (§7.4), so the server's analysis pipeline sees it for free; what
needed to catch up was the **server-side feature data** that enumerates kinds
and keys. Status legend: ✅ implemented in `server/helixlang_lsp/` ·
🟡 pending (this document is the design contract for it).

| New surface (upstream) | Server module(s) affected | Status |
|------------------------|---------------------------|:------:|
| `#media` / `#enzyme` / `#metabolite` / `#sim` accepted by the lenient structural pass (today they are mis-flagged "unknown annotation", `_structural_check`) | `analysis.py` (`ANNOTATION_KINDS`, `REQUIRED_FIELDS`) | ✅ |
| `#media` / `#enzyme` / `#metabolite` / `#sim` in the semantic-token legend | `features/semantic_tokens.py` (§9 keyword list) | ✅ |
| Completion after `#` (4 new kinds) and `#config` sim keys / `backend` enum / redefined `output=` | `features/completion.py` (`ANNOTATION_KINDS`, `FIELD_SETS`, `FIELD_DOCS`, `ENUM_VALUES`) | ✅ |
| Hover docs for the 4 structural annotations and the sim config keys | `features/hover.py` (`ANNOTATION_DOCS`) | ✅ |
| Document-symbol nodes (Media/Enzyme/Metabolite/Sim) | `features/document_symbols.py` | ✅ |
| `#media`/`#enzyme`/`#metabolite`/`#sim` single-line parsing (no folding region) | `features/folding.py` — no change (single-line annotations already handled) | ✅ |
| Golden snapshots for examples 31–34 (+ any rewritten example drift) | `tests/golden/*.json`, `tests/generate_golden.py` | ✅ |
| Static client fallback list and run-config `--backend`/`--json` | plugin (`doc/04` §5.3, §6.1) | ✅ |

Note the upstream `classic` path is bit-identical, so the server's classic
feature data (codons, bio instructions) is unchanged; the new surface is purely
additive.

---

Next: [04 — IntelliJ/PyCharm Plugin](./04-intellij-plugin.md).
