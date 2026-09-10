# `Shared<Key, Member>` — the members every key's set holds

The intersection of keyed member sets: a member that no key's set lacks. A task
whose parts each carry one common thing — the color every object marks itself
with, the color every block borders itself with — finds that thing here, and
the whole finding is stated over the parts rather than over a candidate and its
counterexample.

```
.comp Shared<Key, Member> {
    .decl item(key: Key, m: Member)  // input
    .decl domain(key: Key)           // input

    // Some key's set lacks m.
    .decl absent(m: Member)
    absent(M) :- item(_, M), domain(K), !item(K, M).

    .decl shared(m: Member)
    shared(M) :- item(_, M), !absent(M).
}
```

`domain` makes the finding total over the keys: a key with no items empties
`shared`, which the `item`-only reading would miss.

Not: `Unanimous` (the one value each key's own set holds); `Mode` (the
commonest member per key); a member one key holds and no other holds (the dual,
which separates the keys instead of joining them); `KeyedSetCompare.covers` (an
observed set against a catalog of patterns).

Match: the two-rule pair — a defect relation over the member, from `item(_, M)`
with a key ranging and `!item(K, M)`; then the result, from `item(_, M)` and the
negated defect. Grep: `!\w+\(\w*[Kk]\w*, ` alongside a positive atom on the same
relation in the same rule.

Survey: 2026-09-08 23:27

## Callers

Unkeyed — one intersection per file, which a `Unit` instance holds:

- 57aa92db — `unshared`/`mark_col` (`:31`, `:34`): the color every object carries.
- 1be83260 — `absent`/`border` (`:67`, `:70`): the color every block is drawn in.
- 11e1fe23 — `unseen`, read at `mini` (`:75`, `:77`): the cells every mark's diagonals reach.
- 0962bcdd — Parse `mismatch`/`marker` (`:57`, `:61`): the color all four arms of a center hold; the keys are the four dirs, and the center position folds into the member.
- 642d658d — `mismatch`/`ring` (`:46`, `:50`) and `fp_mismatch`/`plus` (`:71`, `:73`): the color every cardinal arm holds, and the color every footprint offset holds.
- d9fac9be — `defect`/`out` under `$Ring` (`:53`, `:58`): the ink every one of a cell's eight neighbors carries.
- af902bf9 — `open_quad`/`quad_interior` (`:63`, `:66`): the empty cells with a marker in every quadrant.
- 77fdfe62 — `unscreened`/`fenced` (`:63`, `:67`), and again in Determine `unscreened`/`interior` (`:120`, `:124`): the cells a separator screens from every edge.
- 0a938d79 — `off_axis_edge`/`step_axis` (`:36`, `:41`): the axis whose edge every mark sits on.
- 2601afb7 — Determine `anchor_bad`/`anchor_sense` (`:156`, `:160`): the edge every bar touches.
- 18447a8d — `unmatched`/`pair` under `$Common` (`:100`, `:102`): the margin every band admits a piece at.
- 16b78196 — `refuted`/`filled` (`:150`, `:153`): the placement every other piece can stand beside.
- 3345333e — `contradicted`/`frame` under `$Fitted` (`:127`, `:130`): the mirror candidate every figure cell upholds.
- 66e6c45b — Determine `broken`/`pair` (`:91`, `:95`): the input-output cell pairing every example holds.
- 68b67ca3 — Determine `broken`/`pair` (`:69`, `:73`): the same, over its own correspondence candidates.
- e633a9e5 — Determine `broken`/`pair` (`:136`, `:140`): the same.
- 49d1d64f — Determine `broken`/`ring_width` (`:44`, `:50`): the seat every train pair takes.
- 0dfd9992 — Determine `missing`, read at `named.observed_member` (`:164`, `:169`): the D4 kinds every example admits.
- 11852cab — Determine `missing`, read at `named.observed_member` (`:93`, `:98`): the D4 transforms every output figure holds.
- 47c1f68c — Determine `broken`, read at `sym_id.observed_member` (`:136`, `:141`): the transforms every output holds.
- 291dc1e1 — Determine `unseen`/`rot` (`:179`, `:182`): the D4 every turnable object seats.
- 136b0064 — Determine `side_defect`/`legend_dir` (`:225`, `:228`) and `step_defect`/`advance` (`:238`, `:241`): the direction every drawn example admits.

Keyed — one intersection per outer value, whose key domain varies with that value:

- 342dd610 — Determine `broken`/`move` (`:44`, `:50`): per ink color, the displacement every example carrying that color seats.
- 8618d23e — Determine `broken`/`slab_disp` (`:128`, `:134`): per slab, the displacement every example's slab seats.
- 1e5d6875 — Determine `mark_missing`/`mark` (`:179`, `:184`): per source color, the color every piece of that color shows.
- 47c1f68c — Determine `tile_broken`/`tile_d4` (`:169`, `:172`): per tile position, the transform every example's quadrant holds.
- 2faf500b — `uncut_cell`/`cut_axis` (`:47`, `:50`): per shape, the axis whose mark lines every cell of the shape lies on.
- 136b0064 — `count_defect`/`count_move` (`:286`, `:291`), `glyph_defect`/`glyph_move` (`:312`, `:317`), `color_defect`/`color_move` (`:325`, `:330`): per count, per glyph, and per color, the move every occurrence drew.
- 409aa875 — `no_arm`/`apex` (`:71`, `:74`): per aim direction, the cells whose two flanks of that aim both carry ink.

Several sites seed the member from a candidate relation rather than from `item` — `d4_elem` in 0dfd9992, `margin_cand` in 18447a8d, `cand` in 3345333e, `count_cand` in 136b0064. Each agrees with the `item(_, M)` seeding, because a member no key holds drops either way.

## Near-misses

- The dual — the member one key holds and another does without, with the holder kept: 4c7dc4dd `own` (`:74`), 2037f2c7 `only_in` (`:42`).
- A key domain that excludes the member itself, which a fixed `domain` cannot state: 2dc579da `matched`/`special` (`:57`, `:60`).
- A pairwise difference between two named keys, not a fold over a domain: 3a25b0d8 `class_differs` (`:107`).
- An existential second key, which reads "some other key holds it": 3de23699 `escapes`/`mark` (`:27`, `:31`).
- The candidate-and-counterexample form, where the two atoms are different relations — a grid against `ex_out`, `ex_out` against `ex_in`, or a grid against a computed image — so no part carries a member set: 4c5c2cf0, 20fb2937, 1c56ad9f, 3979b1a8, 44f52bb0, b1fc8b8e, 3bd67248, 412b6263, 5521c0d9, c1990cce, 6e02f1e3, 4364c1c4, 3f23242b, 4c3d4a41, 3eda0437, 3ac3eb23, 20a9e565.
- Solidity and completeness universals with no member column, whose domain belongs to the one key under test: 22806e14, 264363fd, 2ba387bc, 538b439f, 14b8e18c, 44d8ac46, 0a1d4ef5, 1c786137, 3eda0437, 20270e3b, 446ef5d2, 470c91de, 42f14c03, 50846271, 228f6490, 77fdfe62 `cut.divider`.
- An emptiness test at one key, where the negated atom wildcards the member: 57edb29d `target_cell` (`:41`).
- The complement idiom, where the negation removes one key's cells from the grid: 0a2355a6, 37d3e8b2, 2d0172a1, 320afe60, 4b6b68e5, 15660dd6.
- Geometric universals whose per-key set is composed inside the rule from `neighbor`, `nearer`, or a cell pair: 46c35fc7, 2b83f449, 3d588dc9, 695367ec, 22425bda.
- Proper-superset tests already built on `KeyedSetCompare.covers`: 14754a24 `dominated` (`:100`), 50846271 `dominated` (`:62`).
- 0934a4d8 `nonuniform.cand` (`:129`) writes the defect half over an outer key and then drops the member, asking only whether the intersection is proper. It reads `absent` and never `shared`.

## Spec question

- **Outer key.** The keyed callers each need one intersection per outer value, and in every one the inner key domain depends on that value — the examples carrying a given ink color (342dd610), the pieces of a given source color (1e5d6875), the cells of a given shape (2faf500b), the flanks of a given aim (409aa875). A single `domain(key)` states none of them, and folding the outer value into the member would let a key with no item under that value empty the wrong intersection. The evidence stands apart from the surfacing solver: the keyed sites are seven separate tasks.
- **Naming.** The entry spends `Key` on the inner key, which is the thing ranged over, against style.md's reading of `Key` as the instance's outer key. `Shared<Key, Part, Member>` with `item(key, part, m)`, `domain(key, part)`, `absent(key, m)`, and `shared(key, m)` gives every unkeyed caller a `Unit` instance and every keyed caller a direct one.
- **`absent` in the interface.** 0934a4d8 reads the defect half alone, so `absent` belongs in the interface under the outer key.
- **Two instances in one file.** 77fdfe62 holds the operation unkeyed in the program (`:63`, `:67`) and keyed by Example in Determine (`:120`, `:124`). With an outer key those are one comp instantiated twice, on `Unit` and on `Example`.
