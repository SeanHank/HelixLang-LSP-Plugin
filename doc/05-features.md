# 05 — Feature Specifications

> User-facing feature contracts: trigger, LSP mapping, rendering, edge cases,
> and priority. This is the document feature owners and QA test against.

Each feature row references the LSP method from the server (`doc/03`) and the
client integration point from the plugin (`doc/04`).

**Priority legend:** P0 = must ship in v1 · P1 = v1.1 · P2 = backlog.

---

## 1. Diagnostics (P0)

| | |
|---|---|
| **Trigger** | document open, change (debounced 200 ms), save; configuration change |
| **LSP** | server pushes `textDocument/publishDiagnostics` |
| **Client** | `HelixDiagnosticsAnnotator` renders squiggles + gutter icons + inspection popup |
| **Rendering** | severity colors: Error red, Warning yellow, Info gray; message verbatim from compiler (`[ParseError @ line 5] …`) |
| **Edge cases** | stale-version results discarded; server offline ⇒ no squiggles + status-bar indicator; ≥512 diagnostics batched; closed documents keep no diagnostics |
| **Acceptance** | every `examples/*.helix` produces **zero** diagnostics; hand-written error corpus produces exactly one diagnostic per seeded error with correct range |

## 2. Syntax highlighting (P0)

| | |
|---|---|
| **Trigger** | editor render, document change |
| **Client** | `HelixSyntaxHighlighter` (lexical, always on) + semantic-token layer |
| **Token colors** | `#` keywords (annotation kinds, `#end`) bold purple; field names teal; numbers orange; strings green; comments gray-italic; codon text colored by opcode family (semantic layer) |
| **Edge cases** | lexical layer must not crash on mid-edit garbage (defensive tokenization); semantic layer returns `null` for unknown tokens |
| **Acceptance** | visual snapshot tests on each example; semantic layer shows `OP_BUILD_PROTEIN` codons with the same color as function calls |

## 3. Hover (P0)

| | |
|---|---|
| **Trigger** | mouse move over a codon / annotation / symbol / field (350 ms debounce) |
| **LSP** | `textDocument/hover` |
| **Client** | `JBHtmlEditorKit` tooltip (mini Markdown renderer) |
| **Content** | codon → opcode + amino acid + wobble operand + table; annotation → grammar + fields; gene/promoter → summary + regulation edges; field → semantics |
| **Edge cases** | no data ⇒ no tooltip (don't show empty); hover over mid-edit garbage returns nothing; long content scrolls |
| **Acceptance** | golden hover snapshots for the 20 examples |

## 4. Code completion (P0)

| | |
|---|---|
| **Trigger** | `#`, `=`, `>`, and word-start inside annotations; manual Ctrl+Space |
| **LSP** | `textDocument/completion` |
| **Client** | `HelixCompletionContributor`; static fallback list when server offline |
| **Items** | annotation kinds; per-kind fields; enum values (table/species/units/output/cas/repair/mark/methylase); symbol names for `promoter=`, `target=`, `->`; 64 codon snippets; type names |
| **Sorting** | required fields first; symbol names before keywords; case-insensitive |
| **Edge cases** | completion inside a comment disabled; `#` completion also available mid-line; item docs from server markdown |
| **Acceptance** | typing `#` shows 16 annotation kinds; typing `#config ` shows its 9 fields; `table=` offers `standard|mito_vertebrate|ciliate` |

## 5. Go-to-definition (P0)

| | |
|---|---|
| **Trigger** | Ctrl/Cmd+B on a symbol reference; middle-click |
| **LSP** | `textDocument/definition` (server-first), mini-PSI fallback |
| **Client** | `HelixGotoDeclarationHandler` → `EditorNavigationUtil` |
| **Edge cases** | cross-file definitions open the target file; definition in same file → caret move; server offline → mini-PSI same-file fallback |
| **Acceptance** | `#regulate lacI -> p_lac` — both symbols resolve; `#gene name=x promoter=p_lac` resolves `p_lac` |

## 6. Find references (P0)

| | |
|---|---|
| **Trigger** | Alt/Cmd+F7 on a symbol |
| **LSP** | `textDocument/references` |
| **Client** | `FindUsagesProvider` + `ReferenceSearchExecutor`; results in Find tool window |
| **Edge cases** | includeDeclaration toggle honored; cross-file usages; anonymous genes excluded from the symbol index |
| **Acceptance** | renaming `lacI`'s definition reports all 3 usages in `02_lac_operon.helix` |

## 7. Document structure (P0)

| | |
|---|---|
| **Trigger** | Structure tool window; breadcrumbs; Ctrl+O |
| **LSP** | `textDocument/documentSymbol` (hierarchical); mini-PSI fallback |
| **Client** | `HelixStructureViewBuilderFactory` |
| **Hierarchy** | Program → Gene/Promoter/Regulation/LSystem/Field/Config/BioInstructions |
| **Acceptance** | structure of every example shows genes + promoters; nodes navigate to their ranges |

## 8. Folding (P0)

| | |
|---|---|
| **Trigger** | document open/render; collapse/expand gestures |
| **LSP** | `textDocument/foldingRange`; client fallback regions |
| **Regions** | `#gene … #end`; DNA bodies ≥ 3 lines; long rule strings (off) |
| **Acceptance** | each gene folds to one line; folding survives server restarts |

## 9. Semantic tokens / codon colors (P0)

| | |
|---|---|
| **Trigger** | render + invalidation (edit, token legend change) |
| **LSP** | `textDocument/semanticTokens/full` (relative delta encoding) |
| **Client** | layered annotator |
| **Acceptance** | a 64 KB file's tokens decode with zero corruption (round-trip test client-side) |

## 10. Inlay hints — opcode annotations (P0/P1)

| | |
|---|---|
| **Trigger** | caret line render; after re-analysis |
| **LSP** | `textDocument/inlayHint`; mini-PSI fallback decodes codons locally |
| **Client** | legacy editor-custom-element renderer (222) / `InlayHintsProvider` (2023.1+) |
| **Rendering** | `▸ OP_BUILD_PROTEIN arg=0` after each codon, dim gray monospaced |
| **Edge cases** | off while editing inside a DNA block; toggleable in settings; hints don't shift layout (fixed-width gutter alignment) |
| **Acceptance** | hints appear for all codons in examples; correct opcode per table switch |

## 11. Quick-fixes (P1)

| | |
|---|---|
| **Trigger** | Alt+Enter on a diagnostic |
| **LSP** | `textDocument/codeAction`; client applies `WorkspaceEdit` |
| **Fixes** | append bases / remove trailing bases (DNA length); insert `name=`; append `TAA` (unterminated ORF); create missing symbol |
| **Acceptance** | each fix applied in a single undoable command; re-analysis clears the diagnostic |

## 12. Formatting (P1)

| | |
|---|---|
| **Trigger** | Reformat Code (Ctrl+Alt+L), selection format |
| **LSP** | `textDocument/formatting` |
| **Rules** | group codons by 3 with single spaces; one ORF per line; preserve field ordering and DNA case; optional `=` alignment |
| **Acceptance** | formatting is idempotent; no semantic change (compile output identical before/after) |

## 13. Run simulation (P0)

| | |
|---|---|
| **Trigger** | Run configuration / gutter run icon |
| **Client** | `HelixRunConfigurationType` + `GeneralCommandLine` (CLI parity) |
| **Output** | trace lines in Run console; optional CSV/PNG; disassembly tab |
| **Acceptance** | running `01_hello_dna.helix` prints the same final trace as the CLI |

## 14. Disassembly view (P0)

| | |
|---|---|
| **Trigger** | toolbar action / popup / run with "disassemble first" |
| **Output** | `helixlang --disassemble` text in a read-only tool-window tab; gene offsets clickable → source line |
| **Acceptance** | disassembly of every example matches CLI output byte-for-byte |

## 15. Debugging via DAP (P1)

| | |
|---|---|
| **Trigger** | Debug run configuration with breakpoints set on codon lines |
| **Adapter** | `helixlang_lsp.dap` wrapping `HelixDebugger` |
| **Client** | XDebugger bridge: breakpoints, step, step-over/out, stack, variables (proteins/energy/position/GRN), evaluate |
| **Acceptance** | breakpoint on a codon line halts before the codon executes; stepping matches `format_disasm_around` output |

## 16. Workspace "Go to Symbol" (P2)

`workspace/symbol` across the project; fuzzy + wildcard matching; exposed via
the standard Go-to-Symbol action for `.helix` files.

## 17. Priority matrix

| Feature | P0 | P1 | P2 |
|---------|:--:|:--:|:--:|
| Diagnostics | ✅ | | |
| Syntax highlighting (lexical + semantic) | ✅ | | |
| Hover | ✅ | | |
| Completion | ✅ | | |
| Go-to-definition | ✅ | | |
| Find references | ✅ | | |
| Document structure | ✅ | | |
| Folding | ✅ | | |
| Run simulation | ✅ | | |
| Disassembly view | ✅ | | |
| Inlay hints | ✅ | | |
| Quick-fixes | | ✅ | |
| Formatting | | ✅ | |
| Debugging (DAP) | | ✅ | |
| Workspace go-to-symbol | | | ✅ |
| Multi-workspace sync (watched files) | | ✅ | |
| Docker/remote server transport | | | ✅ |

---

Next: [06 — Build, Testing, and Distribution](./06-build-testing.md).
