# solvers

ARC-AGI-2 solver work, ascending in complexity. TypeScript reference solvers
live in a sibling repo at `../arc-synth-bun/programs/solvers/`. Python ports
go in `programs/solvers/<task_id>.py`; shared primitives accumulate in
`programs/lib.py`. Eventual target: Souffle.

Each solver is `solve(grid: Grid, c: Consts) -> Grid`, called by
`programs/run.py`. Materialized tasks (upstream + patches applied) load via
`arc.task.load`.

## Process

### Cadence

Translate solvers in ascending TS line-count, skipping any with an "incorrect"
header tag (rule produces correct output but doesn't match the conceptual rule
— needs revision). Find candidates by line count
(`wc -l ../arc-synth-bun/programs/solvers/*.ts | sort -n`); inspect the file
for an "incorrect" tag in its header comment before translating.

For each solver:

1. Draft the Python solver from the TS reference.
2. Run it against materialized train+test pairs.
3. Surface candidate primitives, friction, and hesitations in the file's
   docstring.
4. User reviews; gives feedback or directives.
5. Acknowledge feedback (don't act yet); user confirms; revise.
6. Repeat until the solver is settled, then proceed.

### Triggers

- `next` — proceed to the next solver.
- `go` — execute the proposed plan or refactor.
- `ack` — acknowledge a directive or feedback by restating understanding,
  without making changes. User confirms before action.
- `htt` — "help me think this through" — exploratory back-and-forth, not a
  directive to act.

### Session ending

The handoff target is that a new session can bootstrap from this doc,
`programs/lib.py`, and exemplar solvers — no conversation history needed.

Procedure:

1. Distill new principles, patterns, and deferred items into this doc.
2. Lift any new primitives into `programs/lib.py`; update the deferred list.
3. Audit per-task notes — strip session-order references, "we"-framing,
   anchored-in-time evaluations. A first-time reader should pick up any
   solver cold.
4. Verify all solvers pass (`uv run python programs/run.py`); pytest green.
5. Confirm exemplars (named below) are still representative.

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
   cross-entity. Mirrors how Souffle would express it.

8. **No corner privileging unless the rule has a corner.** "TL 2×2 crop"
   picks a corner — TL-privilege is the rule. Comparing rows via
   `dist(p, TOP)` arbitrarily picks TOP over BOTTOM — both define
   same-row equally. Use `split(p, axis)`'s across-component, which
   carries grid-bound info.

### Meta-process — about how the work is done

1. **Process evolves with the work.** The rules, conventions, and principles
   themselves are subject to revision. When the work surfaces something the
   principles don't accommodate, change the principles. This doc is a
   snapshot — revise it as the work pushes back.

2. **Sticky instruction-following is a hazard.** When a convention feels like
   it's forcing a wrong shape, that's signal to revise — not signal to grind
   through. Drift from the work pushing back is how the doc earns its shape.

3. **Draft, review, iterate.** Don't try to one-shot a clean version. The
   value is in what surfaces during review.

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

## Vocabulary

Types and primitives live in `programs/lib.py` — read it. A few load-bearing
rules:

- **Position** is a 4-tuple `(top, right, bottom, left)` of distances from
  edges (Principle 4).
- **Color** is opaque (Principle 5).
- **Grid** is `set[tuple[Position, Color]]` — unordered relation of cells.
- **D4** elements are named by *what swaps* (`FLIP_LR`, `FLIP_TB`), not by axis
  of reflection ("flip horizontally" is ambiguous between L↔R and T↔B). Values
  are 4-tuples of indices into Position; every d4 element is a pure index
  permutation, so `apply(d, p)` is a gather.
- **Dir** values match Position indices (`TOP=0`, `RIGHT=1`, `BOTTOM=2`,
  `LEFT=3`) so `dist(p, d) = p[d.value]`.

## Conventions

Concrete file-level specifics. (The "why" lives in Principles.)

- **Solver shape.** `def solve(grid: Grid, c: Consts) -> Grid:` — always.
  `Consts` is a per-task `@dataclass(frozen=True)` with a module-level
  `CONSTS` instance. Both primitive constants (colors, dirs, axes, transforms,
  numbers) and task-specific compounds (templates, etc.) go inside.
- **Solver file structure.** Module docstring with: title (rule one-liner),
  Souffle form, Datalog-lite Python form (when they differ), Notes section.
  Notes record primitives leaned on, friction, candidate primitives.
- **Two-form documentation when host adds rules.** When the Python rule has
  extra structure (projections, derived relations) that collapses on Souffle
  port, show both forms with a note explaining the collapse.
- **Placeholder marker.** When a solver uses raw Position destructure (or any
  other deferred-primitive placeholder), put a one-liner near the top of its
  docstring:
  ```
  Status: placeholder — <shape> (would lift to <name> primitive).
  ```
  `Status: placeholder` is the grep target. `grep -l "Status: placeholder"
  programs/solvers/*.py` enumerates the placeholder set; cross-check against
  Deferred / provisional during session-end audits.
- **Testing.** Lib primitives are validated through solver outputs
  (`programs/run.py` runs every solver against materialized train+test pairs).
  No unit tests for primitives directly — the smallest solver that exercises
  a primitive is its test. The 69 pytest tests under `tests/` cover the patch
  DSL and materializer (`src/arc/`), not `programs/`.
- **Type checking.** `programs/` is excluded from pyright (see
  `pyproject.toml`). The solver subtree is exploratory; type signals come
  from runtime. Lib primitives carry annotations for editor hints only.

## Souffle alignment

Everything must be representable in Souffle.

- Sets of tuples → relations. No Python dicts.
- Substitution is a *rule pattern*:
  ```
  out(p, y) :- in(p, x), mapping(x, y).
  out(p, x) :- in(p, x), !mapping(x, _).
  ```
  Souffle's `!mapping(x, _)` is existential negation with anonymous variable,
  built in. Python set comprehensions only test membership in a pre-built set,
  so the projection `mapping_keys(x) :- mapping(x, _).` is materialized as an
  extra rule — host-language overhead that collapses on a Souffle port.
- Variable binding handles "same row / same column" in Souffle (two literals
  sharing a variable). In Python, `split(p, axis)` returns `(along, across)`
  sub-positions; equality on the across-component plays the role of the
  shared variable.

## Patterns

Recognizable shapes that recur across solvers:

- **`matched | unmatched`.** A Datalog rule with multiple alternatives over
  disjoint cell subsets. Two parallel set comprehensions, set-union.
- **Set dedup as semantics.** When many input cells project to the same
  output cell with the same color, set semantics keeps one. Load-bearing in
  inverse-of-tile and projection operations.
- **Body-literal binding via `for x in [expr]`.** Python idiom for a Datalog
  "let" binding inside a comprehension. Use when an intermediate expression
  needs to be named for a subsequent join or filter.
- **Anchor cells as a derived relation.** Cells satisfying a single-edge
  condition (`dist(p, c.anchor) == 0`) precomputed once, joined per cell.
- **Input as shape provider.** Rule reads `in(p, _)` only to enumerate
  positions; colors are discarded. Output dims come from input dims.
- **Output-dimension classes.** Same-as-input (color rewrites, d4),
  scaled-up (tile_d4 outputs), scaled-down (crop, untile). Useful taxonomy
  for picking primitives.

## Exemplars

Canonical solver per pattern. Read these to calibrate; skip the duplicates.

- **67a3c6ac** — simplest case (apply, single-rule, single-field Consts).
- **6d0aefbc** — `tile_d4` with a non-IDENTITY template.
- **332efdb3** — placeholder destructure + candidate-primitive flagging.
- **b1948b0a** — mapping-as-relation; two-form (Souffle vs Python) docstring.
- **c7d4e6ad** — Dir/Axis/`split`, derived relation, `matched | unmatched`.
- **d10ecb37** — crop placeholder, dimension-changing output.
- **2dee498d** — set-dedup as semantic tool (untile via component-wise modulo).

## Deferred / provisional

Decisions held open until more data points land:

- **`tile`** (without `_d4` suffix) — reserved for a more general operation if
  templates of other value types appear.
- **`untile_d4`** — currently inlined for IDENTITY-only templates. Generalizing
  to non-IDENTITY needs per-tile inverse-d4 application. Lift on second
  occurrence.
- **Crop family** — crops can be corner-anchored, center-anchored,
  region-defined, bounding-box-of-pattern. Don't factor a `crop` primitive
  yet — too varied.
- **Wallpaper / tile-with-margin** — a 2×2 motif tiled and truncated.
  `wallpaper` would duplicate `tile_d4` plus a crop step and inherits
  TL-privilege from truncation. Pending more data points.
- **Layout family** — rectangles, borders, tiling-with-margin, margins.
  Cluster of related concepts. Leaning toward small composable primitives over
  one parameter-rich one. Pending more tasks.
- **`recolor` (rejected).** Substitution is a cross-entity rule pattern, not a
  Color-specific primitive. The rule pattern is what's primitive.
- **`Consts` shape.** Currently per-task `@dataclass(frozen=True)`; field
  names by role. Convention will firm up under more variety.
- **Builders for non-D4 templates.** `d4_template_from_rows` exists because
  hand-writing 4-distance position literals is noisy even at small sizes.
  Similar builders if other template-typed value relations appear.

## Resume

Refresh at session end. State as of last update: 13 solvers complete (all 12
three-line TS solvers plus `2dee498d`, the first 4-line). Next candidates in
line-count order:

- `59341089` — `[flipped, original, flipped, original]` per row (4× width
  with alternating horizontal flips).
- `5bd6f4ac` — first 3 rows × last 3 cols (TR 3×3 crop; sibling of `d10ecb37`).
