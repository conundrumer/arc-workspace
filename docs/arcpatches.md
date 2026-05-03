# Arcpatches

An `.arcpatch` is a diff against an upstream ARC task. The upstream submodules stay pinned and read-only; patches carry every correction. `scripts/materialize.py` composes them into `data/tasks/<id>.json`.

## Layout

- `data/patches/<id>.arcpatch` — canonical patch, against upstream.
- `data/patches/<id>_A.arcpatch`, `_B.arcpatch`, `_C.arcpatch` — variant patches; each diffs against the next-lower level present (else canonical).

Materialization applies every level present in order; the output reflects the highest. A task may have any subset, including none.

## File format

Line-by-line. Authoritative grammar lives in `src/arc/patch.py`.

```arcpatch
comment: rectangle grazed vs pierced
issue: https://github.com/fchollet/ARC-AGI/issues/123

@branch test 0 rule
0   0   1   0
0   1~2 1~2 0
0   0   1   0
```

- `key: value` — metadata, before the first section. Free-form; `comment` and `issue` are the conventions.
- `@verb args` — section header.
- Grid rows — whitespace-separated cells.
- Blank lines decorate; ignored.

Cells:

- `N` — plain. Asserts the prior value at this position.
- `N~M` — change. Left is prior, right is new. The verb decides what "new" means.

Indices are 0-based and refer to pre-patch state.

## Verbs

### `@diff <set> <idx> <input|output>`

Edit cells in place. Plain cells assert; `N~M` flips `N` → `M`. Dimensions preserved.

```arcpatch
@diff train 1 output
0   0   3   0
0   0~7 2   2
0~7 0   2   2
```

### `@replace <set> <idx> <input|output>`

Swap a whole grid. Body is the old grid, `---`, then the new grid; both plain. Dimensions may change.

```arcpatch
@replace train 0 output
0 0 0
0 1 0
0 0 0
---
1 1
1 1
```

### `@delete <set> <idx>`

Drop an example. Body is its input, `---`, then its output; both plain — the full assertion of what's being removed. Deletes apply last in reverse-index order, so earlier sections' indices stay stable.

```arcpatch
@delete train 4
5 0 0
0 5 0
---
5 1 1
1 1 5
```

### `@branch <set> <idx> <rule|tiebreak>`

Declare an alt for an example. The body overlays the alt onto the base output: plain cells assert the base, `N~M` cells declare `N` (base) and `M` (alt) both valid. At least one `N~M` is required. Each example carries at most one alt.

```arcpatch
@branch test 0 rule
0   0   8   0
0   1~0 1~0 0
0   0   8   0
```

## Variants (A / B / C)

Sibling levels of increasing rule-consistency over canonical:

- **A** — incidental noise removed. Rule preserved.
- **B** — overly complicated rules removed. Symptom: people disagree over the rule, or the complexity isn't justified for what the task suggests.
- **C** — rule exceptions removed. Symptom: the solver has code dedicated to a single example.

## Alts (rule / tiebreak)

An alt is an alternative valid output for one example, declared with `@branch`. ARC scoring is pass@2; the solver passes if its output matches base or alt.

- **rule** — a different rule interpretation yields a different output. The solver should commit to one consistent reading.
- **tiebreak** — one rule, multiple valid outputs. Typically arises when the rule is symmetric or order-independent.

## Authoring

```sh
uv run python scripts/patch_stub.py <task_id>   # dump grids in column form
# hand-edit data/patches/<task_id>.arcpatch
uv run python scripts/materialize.py            # regenerate data/tasks/
```
