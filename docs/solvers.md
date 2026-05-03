# solvers

ARC-AGI-2 solver work, ascending in complexity. TypeScript reference solvers
live in a sibling repo at `../arc-synth-bun/programs/solvers/`. Python ports
go in `programs/solvers/<task_id>.py`; shared primitives accumulate in
`programs/lib.py`. Eventual target: Souffle.

Each solver is `solve(grid: Grid, c: Consts) -> Grid`, called by
`programs/run.py`. Materialized tasks (upstream + patches applied) load
via `arc.task.load`. The materialized JSON is the source of truth;
`data/patches/` is author-side.

## Process

### Cadence

Translate solvers in ascending TS line-count
(`wc -l ../arc-synth-bun/programs/solvers/*.ts | sort -n`). Skip any with
an "incorrect" header tag — rule fits the data but isn't the conceptual
rule; needs revision.

For each solver:

1. Draft the Python solver from the TS reference.
2. Run it against materialized train+test pairs.
3. Surface candidate primitives, friction, and hesitations in the file's
   docstring.
4. User reviews; gives feedback or directives.
5. Acknowledge feedback (don't act yet); user confirms; revise.
6. Repeat until the solver is settled, then proceed.

### Triggers

- `next` — proceed to the next solver. Only proceed when the user triggers this.
- `go` — execute the proposed plan or refactor.
- `ack` — acknowledge a directive or feedback by restating understanding,
  without making changes. User confirms before action.
- `htt` — "help me think this through" — exploratory back-and-forth, not a
  directive to act.
- `propose` — describe a plan or change in reply only; do not modify
  files. User reviews before any action.

### Per-task drain

Distill task observations into `docs/_session.md` (gitignored) before
moving to the next solver. Session ending drains and deletes it.

### Session ending

Handoff target: a new session bootstraps from this doc, `programs/lib.py`,
and exemplar solvers.

End-session work is multi-pass: drain, audit, polish. Three principles:

- **Single source of truth.** Each fact has one canonical home:
  `lib.py` docstrings for primitives, this doc for patterns and
  conventions, per-solver docstrings for task-specific reasoning. Don't
  duplicate across docs — cross-link instead.
- **Audit by reading.** The drain produces drafts. Reading end-to-end as
  a cold reader catches what keyword searches miss: implicit session
  references (working sketches, in-flight terminology, solver IDs cited
  without context), structural redundancies, drafts that didn't land.
- **Polish for tightness.** A separate pass after the audit. Drop
  content the reader doesn't need; trim qualifiers and asides from what
  remains. Each pass leaves the doc tighter, not longer.

Procedure:

1. Drain `docs/_session.md` — distill new principles, patterns, and
   deferred items into the appropriate sections of this doc.
2. Lift any new primitives into `programs/lib.py`; update the deferred list.
3. Audit per-task notes — strip session-order references, "we"-framing,
   anchored-in-time evaluations. A first-time reader should pick up any
   solver cold.
4. Audit this doc end-to-end — cold-read for leakage and redundancy.
5. Polish — drop content the reader doesn't need; trim qualifiers and
   asides from what remains.
6. Verify all solvers pass (`uv run python programs/run.py`); pytest green.
7. Confirm exemplars (named below) are still representative.
8. Delete `docs/_session.md`.

## Principles

### Object-level — about the work product

1. **No preemptive abstraction.** Add primitives only when a concrete task
   forces them. Resist designing for hypothetical future cases.

2. **Souffle representability.** Everything must be expressible in Souffle.
   Sets of tuples are relations; no Python dicts. Substitution is a rule
   pattern, not a primitive function. Existential negation is `!relation(x, _)`.

3. **Numbers are set cardinality.** Reach for sets first; arithmetic only as a
   fallback when no clean relational form exists. Where arithmetic does real
   conceptual work, lift it into a primitive so solver bodies don't carry it.

4. **Position is 4 distances; no corner privileged.** The redundancy of
   `(top, right, bottom, left)` is load-bearing. Don't destructure Position
   in solver bodies — use Dir-/Axis-parameterized primitives. Placeholder
   destructure is allowed when no primitive yet captures the pattern; mark
   it (see Conventions: Placeholder marker).

5. **Color is opaque.** Never compared by ordinal, never used in arithmetic,
   never iterated as `[C0, C1, ...]`. The int backing exists only for I/O.

6. **Orientation choices are values, not functions.** A function named `flip_h`
   bakes orientation into the body; use `D4.FLIP_LR` in `Consts` so a rotated
   variant swaps the const, not the body. Applies equally to `Dir` and
   `Axis`.

7. **Constants with multiplicity are relations.** A substitution table is a
   `set[tuple[Color, Color]]`, not a dict. Generalizes to multi-row,
   cross-entity, and higher arity (e.g., `set[tuple[Color, Color, Color]]`
   for a 2-input fold). Mirrors how Souffle would express it.

8. **No corner privileging unless the rule has a corner.** "TL 2×2 crop"
   picks a corner — TL-privilege is the rule. Comparing rows via
   `dist(p, TOP)` arbitrarily picks TOP over BOTTOM — both define
   same-row equally. Use `split(p, axis)`'s across-component, which
   carries grid-bound info.

9. **Stay close to ARC reality.** Mappings and relations key on actual ARC
   value types (Colors, Dirs, axes) rather than derived projections
   (bools, ints from arithmetic). Abstractions belong inside primitives,
   not at the Consts / relational interface. Example: a 2-input fold uses
   `mapping: set[tuple[Color, Color, Color]]` directly, not
   `set[tuple[bool, bool, Color]]` from a "filled" projection.

### Meta-process — about how the work is done

1. **Process evolves with the work.** When the work surfaces something
   the principles don't accommodate, revise them. This doc is a snapshot.

2. **Sticky instruction-following is a hazard.** When a convention feels
   like it's forcing a wrong shape, that's signal to revise, not to grind
   through.

3. **Draft, review, iterate.** The value is in what surfaces during review.

4. **Ack before acting on feedback.** When the user corrects or refines,
   confirm understanding (with a counter-proposal where appropriate) before
   changing things. The user's confirmation, not their initial input, is the
   trigger to act.

5. **Surface non-trivial choices.** When a decision has alternatives that
   matter (naming, abstraction shape, primitive form), list them with a
   recommendation; let the user choose. Auto-picking forecloses on the user's
   taste.

6. **Resist abstraction until forced.** Even when a primitive concept is
   *named*, don't commit. Wait for a second occurrence or an explicit user
   directive. Premature factoring over-fits one variant; the family's shape
   only becomes visible with multiple data points. (Object Principle 1 covers
   the "what" — this is the "when".)

7. **Distill upward over time.** Per-task notes are continual-learning seeds.
   As patterns recur, lift specifics from notes into this doc; lift
   conventions into `lib.py`. Notes themselves stay readable cold.

8. **Continuity through artifacts, not memory.** This doc + `lib.py` +
   exemplar solvers must be sufficient to bootstrap a new session.

## Datalog-lite Python style

Relations are `set`s of tuples. Each non-recursive rule is one set
comprehension. Each recursive rule uses an inline fixpoint:

```python
rel = set(base_facts)
while True:
    grew = {...}
    if grew <= rel: break
    rel |= grew
```

Comment each rule with its Datalog/Souffle form on the line above the
comprehension. Comprehension bodies can call any Python expression; equality
between body literals goes in the `if` clause. Order rules so each relation
is finalized before any rule that consumes it.

### Example

```python
edges: set[tuple[int, int]] = {(1, 2), (2, 3), (3, 1), (3, 4)}

# reach(a, b) :- edge(a, b).
# reach(a, c) :- reach(a, b), edge(b, c).
reach: set[tuple[int, int]] = {(a, b) for (a, b) in edges}
while True:
    grew = {(a, c) for (a, b) in reach for (b2, c) in edges if b == b2}
    if grew <= reach: break
    reach |= grew

# mutual(a, b) :- reach(a, b), reach(b, a), a < b.
mutual: set[tuple[int, int]] = {(a, b) for (a, b) in reach if (b, a) in reach and a < b}
```

## Conventions

Concrete file-level specifics. (The "why" lives in Principles.) Types and
primitives are documented in `programs/lib.py` — read it.

- **Solver shape.** `def solve(grid: Grid, c: Consts) -> Grid:` — always.
  `Consts` is a per-task `@dataclass(frozen=True)` with a module-level
  `CONSTS` instance; both primitive constants (colors, dirs, axes,
  transforms, numbers) and task-specific compounds (templates, mappings)
  go inside. Tiebreak solvers take a third arg `choice: ChoiceFn` (see
  Patterns: choice injection); body must be functionally pure since the
  framework re-runs it per branch.
- **Solver file structure.** Module docstring with: title (rule one-liner),
  optional `Status: placeholder` block, Souffle form, Datalog-lite Python
  form (when they differ), Notes section. Notes record primitives leaned
  on, friction, candidate primitives.
- **Two-form documentation when host adds rules.** When the Python rule has
  extra structure (projections, derived relations) that collapses on Souffle
  port, show both forms with a note explaining the collapse.
- **Placeholder marker.** When a solver uses an inline pattern that would
  lift to a primitive later, put a one-liner near the top of its docstring:
  ```
  Status: placeholder — <shape> (would lift to <name> primitive).
  ```
  `Status: placeholder` is the grep target — the only way to enumerate
  inline patterns when no lib fn exists to grep for. Canonical example:
  raw Position destructure where a Dir-/Axis-parameterized primitive
  would sit.
- **Const-name honesty.** When a magic number sneaks into Consts (e.g.,
  `body_start = 2`), the name should reflect that it's a placeholder, not
  a primitive concept. Don't pretend a single-int field captures a
  structural shape that's still missing.
- **Orientation alert.** TOP/BOTTOM/TL/TR literals in solve bodies are
  suspect. If the rule needs a specific Dir, put it in Consts; if the
  literal hacks around a missing primitive, use raw Position destructure
  with `Status: placeholder`. (Object Principle 4 in practice.)
- **Forbidden naming.** Orientation-named accessors like `grid_h` /
  `grid_w` (same hazard as `flip_h`). If a dim accessor ever lifts, it
  must be axis-parameterized.
- **Lib docs are Python-only.** `programs/lib.py` documents primitives in
  Python terms. Relational/Souffle form notation lives in solver
  docstrings, not in primitive definitions.
- **Testing.** Lib primitives are validated through solver outputs
  (`programs/run.py` runs every solver against materialized train+test
  pairs). No unit tests for primitives directly — the smallest solver that
  exercises a primitive is its test. The pytest suite under `tests/`
  covers the patch DSL and materializer (`src/arc/`), not `programs/`.
- **Type checking.** `programs/` is excluded from pyright (see
  `pyproject.toml`). The solver subtree is exploratory; type signals come
  from runtime. Lib primitives carry annotations for editor hints only.
- **Same-rule witnesses.** When a new task's rule matches one already
  solved, share the body verbatim and reference the canonical
  implementation in the new solver's docstring. Don't remove duplicates.

## Souffle alignment

Everything must be representable in Souffle.

- Sets of tuples → relations. No Python dicts.
- Substitution is a *rule pattern*:
  ```
  out(p, y) :- in(p, x), mapping(x, y).
  out(p, x) :- in(p, x), !mapping(x, _).
  ```
  Souffle's `!mapping(x, _)` is built-in existential negation with
  anonymous variable. Python set comprehensions only test membership in
  a pre-built set, so the projection `mapping_keys(x) :- mapping(x, _).`
  materializes as an extra rule — host-language overhead that collapses
  on a Souffle port.
- Variable binding handles "same row / same column" in Souffle (two literals
  sharing a variable). In Python, `split(p, axis)` returns `(along, across)`
  sub-positions; equality on the across-component plays the role of the
  shared variable.
- Non-determinism via Souffle's `choice-domain` is mirrored in Python by the
  injected `ChoiceFn` (see Patterns: choice injection).

## Patterns

Recognizable shapes that recur across solvers:

- **`matched | unmatched`.** A Datalog rule with multiple alternatives over
  disjoint cell subsets. Two parallel set comprehensions, set-union.
- **Set dedup as semantics.** When many input cells project to the same
  output cell with the same color, set semantics keeps one. Load-bearing in
  symmetric-collapse and projection operations.
- **Body-literal binding via `for x in [expr]`.** Python idiom for a
  Datalog "let" binding inside a comprehension; use when an intermediate
  expression needs a name for a subsequent join or filter.
- **Anchor cells as a derived relation.** Cells satisfying a single-edge
  condition (`dist(p, c.anchor) == 0`) precomputed once, joined per cell.
- **Input as shape provider.** Rule reads `in(p, _)` only to enumerate
  positions; colors are discarded. Output dims come from input dims.
- **Output-dimension classes.** Same-as-input (color rewrites, d4),
  scaled-up (tile_d4 outputs), scaled-down (corner_view, symmetric collapse).
  Useful taxonomy for picking primitives.
- **N-input color mapping.** Extension of b1948b0a's `mapping` shape with
  more arity: `mapping: set[tuple[Color, Color, Color]]` for a 2-input
  fold. Keys are actual cell colors, not boolean projections — the fold
  pattern (XOR/OR/etc.) is implicit in the table's rows. Examples:
  34b99a2b (XOR), 5d2a5c43 (OR).
- **Choice injection** (tiebreak meta-primitive). Tiebreak solvers take
  `choice: ChoiceFn` as a third arg; the body declares ambiguity via
  `choice(s)` over a candidate set. Framework discovers each call's set
  in one pass, enumerates the cartesian product across choice points,
  and verifies coverage of `{base, alt}` for `kind: "tiebreak"` examples.
  Mirrors Souffle's `choice-domain`. Example: a6953f00.

## Layout

Spatial structure of a grid along an axis. Two modes per axis:

- **Anchored** (Dir-parameterized): tile pattern from a privileged edge.
  Subsumes stride / cycle. The intended tagging shape is
  `Cells[*Xs, local, tile]` — local position within tile, plus tile index.
  Margins recovered via set diff.
- **Symmetric** (Axis-parameterized): N congruent parts along an axis,
  no Dir privileged. Same `(local, tile)` tagging shape. Margins (dividers
  between parts) are part of the shape, not recovered by set diff.

2D structure (e.g., `tile_d4`'s 2D template) is handled by composition
of per-axis primitives — no separate 2D primitive needed.

**Affected solvers** (12 total).

Using lifted layout primitives:
- `d10ecb37` — `corner_view` (TL 2×2 crop).
- `5bd6f4ac` — `corner_view` (TR 3×3 crop).
- `a6953f00` — `corner_view` + `choice` (TL or TR 2×2 tiebreak).
- `6d0aefbc` — `tile_d4` (1×2 IDENTITY+FLIP_LR).
- `59341089` — `tile_d4` (1×4 alternating IDENTITY/FLIP_LR).
- `c9e6f938` — `tile_d4` (same template as 6d0aefbc).

Placeholder (no primitive lifted yet):
- `332efdb3` — wallpaper (2×2 motif tiled and truncated).
- `2dee498d` — symmetric N-fold collapse (3 IDENTITY parts → one).
- `ba26e723` — stride (every-Nth column from edge).
- `34b99a2b` — split halves with margin (XOR fold).
- `5d2a5c43` — split halves with margin (OR fold).
- `bd4472b8` — header + body sections, body cycles header.

Primitive shape pending more samples. Working sketch:
`repeat_anchored(cells, dir, span, margin) -> Cells[*Xs, local, tile]`
and a symmetric counterpart taking `Axis`.

## Exemplars

Canonical solver per pattern. Read these to calibrate; skip duplicates.

- **67a3c6ac** — simplest case (apply, single-rule, single-field Consts).
- **6d0aefbc** — `tile_d4` with a non-IDENTITY template.
- **332efdb3** — placeholder destructure + candidate-primitive flagging.
- **b1948b0a** — mapping-as-relation; two-form (Souffle vs Python) docstring.
- **c7d4e6ad** — Dir/Axis/`split`, derived relation, `matched | unmatched`.
- **d10ecb37** — `corner_view`; dimension-changing output.
- **2dee498d** — set-dedup as semantic tool (symmetric collapse via
  component-wise modulo).
- **a6953f00** — choice injection / tiebreak.
- **34b99a2b** — N-input color mapping (2-input fold).

## Deferred / provisional

Decisions held open until more data points land:

- **Layout primitive cluster** — see Layout section. Pending more samples
  to commit to primitive shapes. Crops, splits, strides, sections, and
  the `tile_d4` factoring are all tracked here.
- **`tile`** (without `_d4` suffix) — reserved for a more general operation
  if templates of other value types appear.
- **Count aggregator** (`count_per` / `count_by`) — Souffle's
  `n = count : { body }`. Currently approximated in 25d8a9c8 via
  pair-existence (the >1 special case). Lift on a task needing ==N, >K
  with K≥2, or count-value filtering. 25d8a9c8's `Status: placeholder`
  is the grep hook.
- **Rule alts (`kind="rule"`)** — `run.py` matches single output against
  base only for non-tiebreak alts. Pass@2 (`actual ∈ {base, alt}`) not
  enforced. Add when a task forces it.
- **`recolor` (rejected).** Substitution is a cross-entity rule pattern,
  not a Color-specific primitive. The rule pattern is what's primitive.
- **`Consts` shape.** Per-task `@dataclass(frozen=True)`; field names by
  role. Convention may firm up under more variety.
- **Builders for non-D4 templates.** `d4_template_from_rows` exists because
  hand-writing 4-distance position literals is noisy even at small sizes.
  Similar builders if other template-typed value relations appear.

## Resume

Refresh at session end. State as of last update: 22 solvers complete (all
12 three-line, all 3 four-line, all 2 five-line, all 4 six-line; 1 of the
4 seven-line). Next candidates in line-count order:

- `7e4d4f7c` (7-line)
- `a85d4709` (7-line)
- `be03b35f` (7-line)
