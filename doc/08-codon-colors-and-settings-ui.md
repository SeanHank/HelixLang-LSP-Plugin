# 08 — Configurable Codon Colors & Settings UI Redesign

> Design for two coupled work items:
>
> **(A)** each codon in a gene body is colored by the bytecode **opcode** it
> decodes to (start / halt / synthesis / behavior / …), with colors that the
> user can configure; and
>
> **(B)** a redesigned HelixLang settings page that fixes the over-stretched
> input/dropdown/select heights and moves the **Test interpreter** button into
> the interpreter row instead of below it.
>
> Addendum to `doc/04` (§5.2 semantic highlighting, §11 settings UI),
> `doc/03` (§9 semantic tokens), and `doc/05` (§2, §9). Priority legend:
> P0 = must ship in v1 · P1 = v1.1.

---

## 1. Motivation

### 1.1 Colored gene encodings (the "DNA as code" ask)

A `.helix` file expresses logic as DNA. A gene body is a run of codons that the
compiler translates into bytecode:

```
#gene name=hello
ATG GCT GGT GTA TAA
#end
```

Each codon maps to exactly one opcode under the effective translation table:

| Codon | Decoded opcode | Meaning |
|-------|----------------|---------|
| `ATG` | `OP_START` | start of ORF |
| `GCT` | `OP_BUILD_PROTEIN` | synthesize a protein |
| `GGT` | `OP_BUILD_MEMBRANE` | synthesize a membrane |
| `GTA` | `OP_MOVE` | move / consume energy |
| `TAA` | `OP_HALT` | end of ORF |

Today the client classifies codons into only ~5 coarse buckets
(`keyword`/`function`/`variable`/`operator`/`string`) and colors are hard-coded
in the annotator — there is no way for the user to restyle the codons, and the
classification is not fine-grained enough to distinguish an ORF start from an
ORF halt or a protein synthesis from a movement.

**Goal A:** every codon is rendered with a color derived from its **opcode
family** (9 families, §3.1); codons that decode to the same opcode always share
a color; and the user can change every family color either in the native IDE
Color Scheme (**Editor → Color Scheme → HelixLang**) or directly in the
HelixLang settings page (§3.5). The colors must display correctly online
(server-driven semantic tokens) **and** offline (client-side fallback), for all
three translation tables.

### 1.2 Settings page ergonomics

The current `HelixSettingsConfigurable` (doc/04 §11) is a `VerticalBox` of
`BorderLayout` rows (`src/main/kotlin/…/settings/HelixSettingsConfigurable.kt`).
Observed problems:

1. **Over-stretched heights** — every `JBTextField`,
   `TextFieldWithBrowseButton`, and `JComboBox` row expands vertically to fill
   the dialog's free space, so inputs/dropdowns/selects look bloated.
2. **Test interpreter placement** — the button sits on its own row *below* the
   interpreter field, which is hard to scan and wastes vertical space; it should
   sit to the **right** of the interpreter input.

**Goal B:** a compact, grouped settings form (§4) with fixed-height rows, the
test button in the interpreter row, and a new **Codon colors** section that
holds the per-family color pickers (which is also where the over-stretch bug is
most visible once item A adds more controls).

---

## 2. Current state (as of this document)

| Area | Where | Status today |
|------|-------|--------------|
| Server codon classification | `server/helixlang_lsp/features/semantic_tokens.py` `_classify_codon` | Codons → `keyword` (START/HALT) / `function` (build) / `variable` (behavior) / `operator` (rest) / `string` (unknown). No per-opcode distinction. |
| Server legend | `server/helixlang_lsp/protocol.py` `TOKEN_TYPES`; `server.py` `serverCapabilities.semanticTokensProvider.legend` | 9 types, no opcode types. |
| Client mapping | `HelixSemanticTokensAnnotator` `TOKEN_TYPE_NAMES` / `KEY_FOR_TYPE` | Maps the 9 types to ad-hoc `HELIX_SEMANTIC_*` keys. |
| Lexical layer | `HelixSyntaxHighlighter` + `HelixLexer` | Colors the four DNA bases individually (`HELIX_BASE_*`, all `CONSTANT`); codon ranges are 3 consecutive base tokens. |
| Color scheme draft | `build/resources/main/colorSchemes/HelixLangDefault.xml` (stale build artifact) + uncommitted `plugin.xml` `<additionalTextAttributes …/>` | A 9-key scheme (`HELIX_CODON_*`) already exists but the source resource
  `src/main/resources/colorSchemes/HelixLangDefault.xml` is **missing** — the
  build artifact is orphaned. |
| Settings UI | `settings/HelixSettingsConfigurable.kt` | `VerticalBox` + `BorderLayout` rows; components stretch; test button below. |
| Settings state | `settings/HelixSettings.kt` (`PersistentStateComponent`, `helixlang-ide.xml`) | No color state. |
| Server tests | `server/tests/test_features.py` | `test_semantic_tokens_start_modifier` asserts the `keyword` index — will change. |

The orphaned color-scheme draft and the half-wired `plugin.xml` reference are
the starting point; this design finishes that work end-to-end and makes it
configurable.

---

## 3. Part A — Codon coloring by opcode

### 3.1 Opcode-family color model

Every `Op` value is mapped to one of **nine color families**. The mapping is
the single source of truth for "which codon gets which color"; codons decoding
to the same opcode share the family (and therefore the color).

| Family | Color key (`TextAttributesKey`) | Opcodes | LSP token type |
|--------|--------------------------------|---------|----------------|
| Start | `HELIX_CODON_START` | `OP_START` | `opcodeStart` |
| Halt | `HELIX_CODON_HALT` | `OP_HALT` | `opcodeHalt` |
| Stack | `HELIX_CODON_STACK` | `OP_PUSH_CONST`, `OP_POP`, `OP_DUP`, `OP_SWAP` | `opcodeStack` |
| Synthesis | `HELIX_CODON_SYNTHESIS` | `OP_BUILD_PROTEIN`, `OP_BUILD_MEMBRANE`, `OP_BUILD_PIGMENT` | `opcodeSynthesis` |
| Behavior | `HELIX_CODON_BEHAVIOR` | `OP_MOVE`, `OP_SIGNAL`, `OP_DIVIDE`, `OP_DIE`, `OP_FEED` | `opcodeBehavior` |
| Morphology | `HELIX_CODON_MORPHOLOGY` | `OP_GROW_LSYSTEM`, `OP_DIFFUSE`, `OP_REACT`, `OP_EMIT_MORPHOGEN` | `opcodeMorphology` |
| Regulation | `HELIX_CODON_REGULATION` | `OP_READ_MEM`, `OP_WRITE_MEM`, `OP_MODIFY_STATE`, `OP_REGULATE`, `OP_BIND` | `opcodeRegulation` |
| Call | `HELIX_CODON_CALL` | `OP_CALL_GENE` | `opcodeCall` |
| Arithmetic | `HELIX_CODON_ARITHMETIC` | `OP_ADD`, `OP_SUB`, `OP_MUL`, `OP_LT`, `OP_NOT`, `OP_JUMP`, `OP_JUMP_IF_ZERO`, `OP_TICK`, `OP_DEBUG` | `opcodeArithmetic` |

Notes:

- Only the opcodes in the **standard** table are reachable from source codons
  (`STANDARD_TABLE` in `src/helixlang/codon_table.py`); `OP_JUMP`, the
  arithmetic ops, `OP_TICK`, and `OP_DEBUG` are compiler/VM-generated and their
  family exists for completeness and for future codon assignments.
- The **mitochondrial** (`TGA→pigment`, `ATA→start`, `AGA/AGG→halt`) and
  **ciliate** (`TAA/TAG→morphogen`) tables reuse the same families — only the
  decoded opcode changes, never the family table.
- Unknown/undecodable codons keep the existing `string` type (error-colored via
  the accompanying diagnostic), unchanged from today.

The example `ATG GCT GGT GTA TAA` renders as (Default scheme defaults):

```
#gene name=hello
ATG GCT GGT GTA TAA     ← ATG=START(green,bold) GCT/GGT=SYNTHESIS(blue)
                            GTA=BEHAVIOR(orange) TAA=HALT(red)
#end
```

### 3.2 Server changes (`server/helixlang_lsp/`)

1. **`codons.py`** — add the canonical Python mapping:

   ```python
   OPCODE_FAMILY: dict[int, str] = {
       int(helix.Op.OP_START): "opcodeStart",
       int(helix.Op.OP_HALT): "opcodeHalt",
       int(helix.Op.OP_PUSH_CONST): "opcodeStack",
       int(helix.Op.OP_POP): "opcodeStack",
       # … all Op values from the §3.1 table …
   }
   def opcode_family(op: helix.Op) -> str | None: ...
   ```

   This is the server's single source of truth; the client mirrors it for
   rendering-only fallback (§3.6).

2. **`protocol.py`** — extend `TOKEN_TYPES` by appending the nine `opcode*`
   types *after* the existing nine, so existing indices remain stable:

   ```python
   TOKEN_TYPES = ["keyword", "type", "function", "variable", "number", "string",
                  "comment", "operator", "arrow",
                  "opcodeStart", "opcodeHalt", "opcodeStack", "opcodeSynthesis",
                  "opcodeBehavior", "opcodeMorphology", "opcodeRegulation",
                  "opcodeCall", "opcodeArithmetic"]
   ```

3. **`server.py`** — publish the same list in the `initialize` legend
   (`semanticTokensProvider.legend.tokenTypes`) so the client and server
   negotiate the identical vocabulary.

4. **`features/semantic_tokens.py`** — replace the coarse codon classification
   in `_classify_codon`:

   - `OP_START` → `opcodeStart` **with the `defaultLibrary` modifier** (keeps
     the start codon visually distinct beyond color, e.g. bold);
   - `OP_HALT` → `opcodeHalt`;
   - every other opcode → `opcode_family(op)` (falling back to
     `opcodeArithmetic` for opcodes outside the table);
   - unknown codon → `string` (unchanged).

   The `_BUILD_OPS`/`_BEHAVIOR_OPS`/`_OPERATOR_OPS` sets are removed in favor
   of the single `OPCODE_FAMILY` map.

### 3.3 Client changes (`src/main/kotlin/…/lsp/handlers/HelixSemanticTokensAnnotator.kt`)

1. Extend `TOKEN_TYPE_NAMES` with the nine `opcode*` names (same order as the
   server) and extend `KEY_FOR_TYPE`:

   ```kotlin
   "opcodeStart"      to CodonColorKeys.START,       // HELIX_CODON_START
   "opcodeHalt"       to CodonColorKeys.HALT,
   "opcodeStack"      to CodonColorKeys.STACK,
   "opcodeSynthesis"  to CodonColorKeys.SYNTHESIS,
   "opcodeBehavior"   to CodonColorKeys.BEHAVIOR,
   "opcodeMorphology" to CodonColorKeys.MORPHOLOGY,
   "opcodeRegulation" to CodonColorKeys.REGULATION,
   "opcodeCall"       to CodonColorKeys.CALL,
   "opcodeArithmetic" to CodonColorKeys.ARITHMETIC,
   ```

2. Introduce a single registry `syntax/CodonColorKeys.kt`:

   ```kotlin
   object CodonColorKeys {
       val START       = TextAttributesKey.createTextAttributesKey(
           "HELIX_CODON_START", DefaultLanguageHighlighterColors.KEYWORD)
       val HALT        = … "HELIX_CODON_HALT"
       val STACK       = … "HELIX_CODON_STACK"
       val SYNTHESIS   = … "HELIX_CODON_SYNTHESIS"
       val BEHAVIOR    = … "HELIX_CODON_BEHAVIOR"
       val MORPHOLOGY  = … "HELIX_CODON_MORPHOLOGY"
       val REGULATION  = … "HELIX_CODON_REGULATION"
       val CALL        = … "HELIX_CODON_CALL"
       val ARITHMETIC  = … "HELIX_CODON_ARITHMETIC"
       val ALL: List<Pair<Family, TextAttributesKey>> = …
   }
   enum class CodonFamily(val id: String, val label: String, val key: TextAttributesKey) {
       START("opcodeStart", "Start (ATG)", …), HALT("opcodeHalt", "Halt (TAA/TAG/TGA)", …), …
   }
   ```

3. **Effective-attributes resolution.** The annotator still stores the key in
   `HelixSemanticRange`, but in `apply()` it resolves the *effective*
   attributes: read the scheme attributes for the key, then override the
   foreground with the user's configured hex from `HelixSettings` (if set):

   ```kotlin
   val effective = effectiveAttributes(range.attributesKey, family)
   holder.newSilentAnnotation(HighlightSeverity.INFORMATION)
       .range(TextRange(start, end))
       .textAttributes(effective)   // TextAttributes instance, not key
       .create()
   ```

   Resolution order: **settings override** → **IDE Color Scheme value** →
   built-in fallback. Scheme value read via
   `EditorColorsManager.getInstance().getGlobalScheme().getAttributes(key)`.

4. **Display correctness ("确保能正常显示"):** because the annotator's
   text attributes are applied *on top of* the lexical layer for the covered
   range, the 3-character codon span wins over the per-base `HELIX_BASE_*`
   colors, and unclassified tokens return `null` so the lexical colors show
   through — the existing layering contract (doc/04 §5.2) is unchanged. Codons
   split across a line boundary or mid-edit garbage simply keep the lexical
   base colors until the next successful server pass.

### 3.4 Color scheme registration

The `HELIX_CODON_*` keys must be theme-aware (light + dark):

1. **Create `src/main/resources/colorSchemes/HelixLangDefault.xml`** — lift the
   existing draft from `build/` into source, keeping one `<scheme>` per theme
   (`Default` and `Darcula`, as already drafted). This satisfies the
   `<additionalTextAttributes scheme="Default" file="colorSchemes/HelixLangDefault.xml"/>`
   extension already present in `plugin.xml`.

2. **Register a `ColorSettingsPage`** so the keys appear, named, in
   **Editor → Color Scheme → HelixLang**:

   - `syntax/HelixColorSettingsPage.kt` implements
     `com.intellij.openapi.options.colors.ColorSettingsPage`
     (`getDisplayName() = "HelixLang"`, `getAttributeDescriptors()` returns the
     nine `CodonColorKeys` descriptors with human labels, `getIcon()` =
     `HelixIcons`, `getHighlighter()` = `HelixSyntaxHighlighter`,
     `getDemoText()` includes the §1.1 gene example, and
     `getAdditionalHighlightingRangesToRender()` marks the demo codons with the
     family keys so the preview colors them).
   - `plugin.xml`:

     ```xml
     <colorSettingsPage implementation="com.helixlang.plugin.syntax.HelixColorSettingsPage"
                        id="HelixLangColors"/>
     ```

   This is the canonical IntelliJ configuration surface and works identically on
   the 222 baseline.

### 3.5 User configuration in the HelixLang settings page

In addition to the native Color Scheme, the HelixLang settings page gains a
**Codon colors** section (§4.3) with:

- a master `JBCheckBox` **"Custom codon colors"** (default off → the IDE Color
  Scheme wins);
- one row per `CodonFamily`: family label, live color swatch (click → `ColorPicker`),
  and a per-row **reset** button that clears that family's override;
- a **Reset all** button;
- a live **preview** line rendering `ATG GCT GGT GTA TAA` with the current
  effective colors.

Persistence in `HelixSettings.State` (applies immediately, `helixlang-ide.xml`):

```kotlin
@OptionTag("codonColorCustom") var codonColorCustom: Boolean = false,
@OptionTag("codonColorOverrides") var codonColorOverrides: Map<String, String> = emptyMap(),
// family.id -> "#RRGGBB" (only families the user changed)
```

The XML serializer on 222 handles `Map<String, String>` fields directly (no
`@OptionTag` on the map itself). Values are validated `#RRGGBB` on read;
malformed entries are dropped.

### 3.6 Offline fallback (colors without the server)

"确保能正常显示" includes the server-offline case. `HelixSemanticTokensAnnotator`
currently returns `null` when `!manager.isReady`, leaving only the per-base
lexical colors. Add a fallback path:

1. If the server is not ready (or semantic tokens are disabled), compute codon
   ranges locally: iterate the mini-PSI `HelixAnnotation` blocks (`kind ==
   "gene"`), collect the DNA body lines, split into 3-base codons, and decode
   each against the bundled `STANDARD_TABLE` copy (the same table the inlay
   hints already use for rendering, doc/04 §5.9).
2. Map each decoded opcode through `opcode_family` → `CodonFamily` → key.
3. Feed the resulting `HelixSemanticRange`s through the identical
   `apply()`/effective-attributes path, so online and offline rendering are
   pixel-identical for files using the standard table.

The client-side `opcode→family` table is a rendering-only mirror of
`server/…/codons.py`; the offline pass is deliberately non-authoritative (a file
using `#config table=mito_vertebrate` may color marginally differently offline,
which is accepted and documented, exactly like the existing inlay-hint fallback).

### 3.7 Refresh on color change

When the user edits a codon color in the settings page and clicks **Apply**:

1. `apply()` writes `codonColorCustom`/`codonColorOverrides`.
2. The configurable fires a refresh: for every open editor on a `.helix` file,
   `DaemonCodeAnalyzer.getInstance(project).restart()` triggers a new highlight
   pass, which re-reads `HelixSettings` in `apply()`. Optionally, also
   invalidate `manager.semanticTokensCache` to force a fresh server round-trip
   when the server is online.
3. No editor restart and no server restart are required — colors are picked up
   on the next highlight pass.

### 3.8 End-to-end flow (online, `#gene name=hello`)

```
editor: type/load file                      client: didChange
   │                                          server: re-analyze (debounced 200 ms)
   │                                          server: textDocument/semanticTokens/full
   │                                                  → data = [ … {ATG: opcodeStart},
   │                                                  {GCT: opcodeSynthesis}, {GTA: opcodeBehavior},
   │                                                  {TAA: opcodeHalt}, … ]  (delta-encoded)
   │  (highlight pass)                        client: decode relative delta
   │                                          client: type name → CodonColorKeys (3.3.1)
   │                                          client: effective attributes (scheme ∨ settings override)
   ▼
render: ATG=green·bold  GCT=blue  GGT=blue  GTA=orange  TAA=red   ✓
```

---

## 4. Part B — Settings page UI redesign

### 4.1 Root cause of the over-stretched heights

`createComponent()` returns a `VerticalBox` whose children are
`BorderLayout` rows. `BoxLayout` distributes *leftover* vertical space to every
child whose `maximumSize` allows growth; `JBTextField`,
`TextFieldWithBrowseButton`, and `JComboBox` report an effectively unbounded
maximum height under the current LaF, so the dialog's empty space is spread
across all input rows, stretching each one. The fix has two parts:

1. **Stop stretching:** switch to a grid layout whose row weights are all `0`
   (components keep their preferred heights). `FormBuilder.createFormBuilder()`
   (`com.intellij.ui.components.panels.FormBuilder`, available on 222) with
   `verticalGap` default is the chosen layout; belt-and-braces, cap
   `maximumSize` height on the tall widgets:

   ```kotlin
   fun compact(c: JComponent): JComponent {
       c.maximumSize = Dimension(Int.MAX_VALUE, c.preferredSize.height)
       return c
   }
   ```

2. **In-row test button:** wrap the interpreter field and the button in a
   `HorizontalBox` and put *that* in the interpreter row:

   ```kotlin
   val interpreterRow = HorizontalBox().apply {
       add(interpreter, 1f)          // field takes the free width
       add(UIUtilx.BorderLayout.HGAP / 2)  // small gap
       add(testButton)               // fixed, right of the field
   }
   formBuilder.addLabeledComponent("Interpreter:", interpreterRow)
   ```

The status label moves to a sub-line under the interpreter row (small, gray,
inline) instead of being a full row.

### 4.2 New layout (single column, grouped)

```
Languages & Frameworks → HelixLang

┌─ General ────────────────────────────────────────────────┐
│ Interpreter:  [/path/to/python ........] [Test interpreter] │
│               · status: OK — helixlang 2026.8.2 importable │
│               · (leave empty for auto-detection)           │
├─ Language server ────────────────────────────────────────┤
│ Transport:     [stdio ▾]   TCP port:  [8123    ]           │
│ ☐ Write --trace transcript                                 │
├─ Features ────────────────────────────────────────────────┤
│ ☑ Diagnostics         ☑ Semantic tokens                    │
│ ☑ Inlay hints         ☑ Completion fallback                │
│ ☑ Debounce (200 ms)   ☐ Validate by running the VM         │
├─ Codon colors ────────────────────────────────────────────┤
│ ☑ Custom codon colors                    [Reset all]       │
│ Family            │ Preview/swatch  │ Reset                │
│ Start (ATG)       │ [████████]      │ [↺]                  │
│ Halt (TAA/TAG/TGA)│ [████████]      │ [↺]                  │
│ … 7 more rows …                                            │
│ Preview:  ATG GCT GGT GTA TAA  (rendered with these colors)│
└────────────────────────────────────────────────────────────┘
```

Concrete rules:

- Each labeled row is a single `FormBuilder` grid row with `weightY = 0`; no
  component is ever taller than its preferred height.
- The **Test interpreter** button is the rightmost control of the interpreter
  row (§4.1). `isModified()`/`apply()`/`reset()` logic for the interpreter path
  is unchanged; the status line is a non-editable `JLabel` that does not count
  toward modification.
- The two feature checkboxes per row are placed in a `HorizontalBox`; the
  debounce control becomes a real slider row (`JBLabel` + `JSlider`, e.g.
  `50…2000 ms`) instead of a checkbox, since the value is already stored
  (`debounceMs`).
- Section headers use `JBTitledSeparator` (`com.intellij.ui.components.JBScrollPane`
  `com.intellij.ui.components.JBTitledSeparator`); the whole form is wrapped in a
  `JBScrollPane` (settings dialogs can be short on laptops) with `border = JBUI.Borders.empty()`.
- Keyboard order: tab order follows visual order; the interpreter row is first.

### 4.3 The Codon colors section

Built from `CodonFamily.ALL` (9 rows) — no hard-coded rows in the UI:

- Swatch control: a small `JButton` filled with the current color (or a
  checkerboard + `#RRGGBB` label when the override is unset = "scheme default").
  Clicking opens `com.intellij.util.ui.ColorPicker` (available on 222); the
  picked value is written into a pending override map, not yet persisted.
- Per-row reset clears the pending override; **Reset all** clears the whole map.
- The preview label re-renders on any change using the same effective-attributes
  logic as the annotator (scheme base + pending overrides).
- Overrides are only committed on **Apply**; **Reset** (the settings dialog's
  "Reset" button) restores persisted values from `HelixSettings`; **Cancel**
  discards pending changes. This matches the standard
  `Configurable`/`PersistentStateComponent` contract.

### 4.4 Run-configuration editor consistency

`HelixRunSettingsEditor` uses the same `VerticalBox` + `BorderLayout` rows and
suffers the identical over-stretch. Apply the same grid-based layout there
(`FormBuilder`, `weightY = 0`, compact heights, section separator above the
"Disassemble first" checkbox). No field semantics change; this is a pure layout
consistency pass (P1 if it delays the settings-page work).

---

## 5. Files affected

**Server (`server/helixlang_lsp/`)**

| File | Change |
|------|--------|
| `codons.py` | add `OPCODE_FAMILY` map + `opcode_family(op)` |
| `protocol.py` | extend `TOKEN_TYPES` with the 9 `opcode*` types |
| `server.py` | extend the `initialize` legend identically |
| `features/semantic_tokens.py` | `_classify_codon` emits family types; remove `_BUILD_OPS`/`_BEHAVIOR_OPS`/`_OPERATOR_OPS` |
| `tests/test_features.py` | update `test_semantic_tokens_start_modifier` (new index + modifier), add per-family assertions |
| `tests/test_analysis.py` / golden | no change expected (diagnostics untouched) |

**Client (`src/main/kotlin/com/helixlang/plugin/`)**

| File | Change |
|------|--------|
| `syntax/CodonColorKeys.kt` | **new** — family enum + `TextAttributesKey` registry |
| `syntax/HelixColorSettingsPage.kt` | **new** — `ColorSettingsPage` implementation |
| `lsp/handlers/HelixSemanticTokensAnnotator.kt` | extend `TOKEN_TYPE_NAMES`/`KEY_FOR_TYPE`; effective-attributes resolution; offline fallback (§3.6) |
| `settings/HelixSettings.kt` | add `codonColorCustom` + `codonColorOverrides` state + accessors |
| `settings/HelixSettingsConfigurable.kt` | full layout rework (§4); new Codon colors section; test button in interpreter row; apply-refresh hook (§3.7) |
| `run/HelixRunSettingsEditor.kt` | grid layout consistency (P1) |
| `resources/META-INF/plugin.xml` | add `<colorSettingsPage …/>` (keep existing `<additionalTextAttributes …/>`) |
| `resources/colorSchemes/HelixLangDefault.xml` | **new (in source)** — lifted from the stale build artifact, Default + Darcula |

**Tests**

- Kotlin: unit tests for `CodonColorKeys` label/order, the offline codon
  splitter/decoder, and effective-attributes resolution (override ∨ scheme ∨
  fallback); a platform fixture test asserts that opening the §1.1 example
  produces one `INFORMATION` annotation per codon with the expected key.
- UI: platform test instantiates `HelixSettingsConfigurable`, asserts
  `component.size.height == preferred height` for the input rows (regression
  guard for the over-stretch bug) and that the test button's x-center lies
  inside the interpreter row's bounds.

---

## 6. 222-compatibility notes

| API | Build availability | Guard |
|-----|--------------------|-------|
| `ColorSettingsPage` | since 3.0 | none — safe on 222 |
| `additionalTextAttributes` extension | since 3.0 | none |
| `FormBuilder.createFormBuilder()` | since 2021.x | none — safe on 222 |
| `ColorPicker` / `ColorPickerUtil` | since 2020.x | none |
| `JBTitledSeparator` | since 2019.x | none |
| `HorizontalBox` / `VerticalBox` | since 2019.x | none |
| `Annotation.textAttributes(TextAttributes)` | legacy | none |

The semantic-token legend change is **backward compatible by construction**: new
types are appended after the existing nine, so indices for all previously
emitted tokens are unchanged; a client on an older plugin build simply ignores
unknown types and keeps the old coarse colors.

---

## 7. Testing plan

1. **Server (pytest, `server/tests/test_features.py`):**
   - the 9 `opcode*` types appear in `protocol.TOKEN_TYPES` and in the
     `initialize` legend;
   - `ATG→opcodeStart(+defaultLibrary)`, `TAA→opcodeHalt`,
     `GCT/GGT→opcodeSynthesis`, `GTA→opcodeBehavior` for a
     `#gene name=hello` sample;
   - family correctness across `standard`/`mito_vertebrate`/`ciliate`
     (`TGA`, `ATA`, `AGA`, `AGG` under mito; `TAA/TAG` under ciliate);
   - unknown codon (e.g. `XYZ`) → `string`.
2. **Golden:** existing snapshots are diagnostics/hover-only — unchanged;
   regenerate only if any hover text references token types (none do).
3. **Client (Kotlin):** as listed in §5; plus a round-trip decode test that
   exercises the full 64-codon standard table and asserts exactly one range per
   codon with the right family key.
4. **E2E/manual:** open `01_hello_dna.helix` (server on) and the §1.1 example —
   each codon colored by family; kill the server → offline fallback shows the
   same colors; change a family color in the settings page → Apply → editor
   recolors without a restart; change theme Default→Darcula → colors switch to
   the dark palette; set a custom color → overrides the scheme for that family.

---

## 8. Acceptance criteria

| # | Criterion |
|---|-----------|
| A1 | `#gene name=hello\nATG GCT GGT GTA TAA\n#end` renders 5 codons with 4 distinct colors (START green·bold, SYNTHESIS blue ×2, BEHAVIOR orange, HALT red) in both Default and Darcula. |
| A2 | Every one of the 64 standard-table codons gets the family color of its decoded opcode; the same file renders identically online and offline (standard table). |
| A3 | All nine family colors are editable in **Editor → Color Scheme → HelixLang** **and** in the settings page's Codon colors section; changes take effect on Apply without editor/server restart. |
| A4 | Settings page: no input/dropdown/select row is taller than its preferred height; **Test interpreter** sits to the right of the interpreter field in the same row and still runs the importability check. |
| A5 | `HelixSettingsConfigurable`/`HelixRunSettingsEditor` have no vertical stretch on a 1280×720 dialog; tab order and Apply/Reset/Cancel semantics intact. |
| A6 | Server: semantic-token legend + `_classify_codon` updated; existing pytest, ruff, mypy, and Kotlin suites green on the 222 baseline. |

---

Next: back to [00 — Index](./README.md).

*End of document 08 — Configurable Codon Colors & Settings UI Redesign.*
