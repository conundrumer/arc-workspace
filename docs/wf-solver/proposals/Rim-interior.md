# `Rim.interior` — the cells a set does not expose

A per-cell readout on `Rim`: a cell of the keyed set that no step of the instance's own adjacency leaves — the set with its rim taken off. A solver reading a blob's core, one erosion step, or a cell flanked on every side names that set directly, in place of negating the boundary beside a re-stated domain atom.

```
.decl interior(key: Key, p: Position)
interior(Ky, P) :- cell(Ky, P), !rim(Ky, P).
```

Not: `rim` itself (the boundary); `depth` (how far in a cell sits, whose nonzero test this is); `Bbox.inside` (the cells a box encloses, not a set's own); the cells a set encloses, where the tested cell is not a member of the set that judges it.

Match: `!\w*\.rim(` over `programs/solvers/`. Also the hand-rolled form with no `Rim` instance: a cell of a set whose neighbors all lie in that set, stated as a negated defect rule over `dir_elem` and `neighbor`.

Survey: 2026-09-08 21:34

Spec: the readout names the instance's own step set, not the cardinals. `Rim8` overrides `dir`, and two callers read the 8-adjacency reading, so the index sentence carries that wording and the code form needs no edit. The interface takes no extra column: five callers keep their domain atom for a key or a join it carries, so `interior` drops the negation there rather than the whole atom.

Callers, fifteen after folding one family into its representative:

- 1818057f, with its sibling 7e02026e — `flanked`, a field cell with field cells on all four sides.
- 55059096 — `span.mark`, the center of a plus mark.
- 3befdf3e — `core`, the square inside an object's one-cell wall. The Determine comp repeats the rule.
- 09c534e7 — `fill`, an ink cell with all eight neighbors on the ink. `Rim8`.
- 4347f46a, 50cb2852, bb43febb — `interior`, a rectangle's inside under the `$Erode` reading.
- 522fdd07 — `shrunk`, a square redrawn one ring smaller.
- 3bdb4ada — `dash_cover`, the cells off a rectangle's rim.
- 135a2760 — `interior`, a panel's inside.
- 1d398264 — `center`, the one interior cell of a 3x3 block. `Rim8`.
- 2c0b0aff — `cross`, a mark whose four cardinal neighbors are marks.
- 58f5dbd5 — `inside_box.cell`, the inside of a solid block, which a key punches into.
- 5b37cb25 — `diamond`, a background cell whose four cardinal neighbors are background: the center of the five-cell diamond a bite takes out of a blob.
- 800d221b — `hub_center`, the one wire cell the wire does not expose: the center of a 3x3 block. `Rim8`.

The hand-rolled arm of the match found no caller. Every other `Rim` and `Rim8` instance in the corpus reads `rim`, `rim_dir`, or `depth` positively.

Near-misses:

- `516b51b7` reads `depth(P, K, _), K != 0` and then consumes K, so the interior falls out of a value the rule needs anyway.
- `15663ba9` negates `rim_dir` per direction and keeps the direction. The fold of that over every direction is this readout.
- `0962bcdd`, `46c35fc7`, `d9fac9be`, `3ad05f52` test a cell whose neighborhood lies in a set the cell is not a member of. `rim_dir` starts from `cell`, so none of them reaches `Rim` at all; serving them needs a domain input separate from `cell`, which is another operation.
- `409aa875`, `142ca369` negate a defect over the two directions of one corner, so the cell they name is still on the rim.
- `1b8318e3` reads the rim from outside the set, and diverges off the grid edge.

Survey: 2026-09-09 00:41

The second survey read the 28 solvers whose file time is at or after the first survey's dispatch. It found no caller beyond 522fdd07 and 55059096, both edited after that dispatch with the operation unchanged, and no near-miss beyond the classes the `Not:` line already names. The two callers differ in what their domain atom carries: 522fdd07 keeps `comps.label` for the `Id` join, so `interior` drops the negation alone, and 55059096's domain atom is the instance's own `cell` input, so `interior` replaces both atoms. The scope holds no `Rim8` instance, so it bears on neither the adjacency wording nor the interface.

Survey: 2026-09-09 01:01

The third survey read the seven solvers whose file time is at or after the second survey's dispatch. It found no caller, no reimplementation, and no near-miss outside the classes the `Not:` line names. `409aa875` joins `15663ba9` and `142ca369` in a class that folds `rim_dir` over a caller-supplied subset of directions and keeps or discards the direction; a readout over a direction subset is another operation, whose fold is not total over the instance's step set. The scope's one `Rim8` instance sits in that class, so it bears on neither the adjacency wording nor the interface.

Survey: 2026-09-09 02:04

The fourth survey read the nine solvers whose file time is at or after the third survey's dispatch. It found one caller, 58f5dbd5, which the first survey already lists; the scope places it in the arm where `interior` replaces both atoms, because its domain atom `block(Col, P)` is the instance's own `cell` input and its key is the `Rim` key already. The scope holds no other `Rim` or `Rim8` instance and no hand-rolled form, and no near-miss outside the classes the `Not:` line and the earlier results name. The one instance reads a solid rectangular block, on which the cardinal rim and the 8-adjacency rim coincide, so it bears on neither the adjacency wording nor the interface.

Survey: 2026-09-09 02:26

The fifth survey read the three solvers whose file time is at or after the fourth survey's dispatch. It found no caller, no reimplementation, and no near-miss outside the classes the `Not:` line and the earlier results name. The scope holds no `Rim` or `Rim8` instance and no `rim`, `rim_dir`, or `depth` reference, so it bears on neither the adjacency wording nor the interface. `5ad4f10b`'s `figure` joins `409aa875` and `142ca369` in the class that folds over one corner's directions; being existential over corners, the cell it names is still on the rim. `5adee1b2`'s `grown_box` is the outward operation, a dilation whose added cells are not members of the set that judges them.

Survey: 2026-09-09 21:19

The sixth survey read the 96 solvers whose file time is at or after the fifth survey's dispatch. It found one caller, 2c0b0aff, which the first survey already lists, edited since with the operation unchanged: its domain atom is the instance's own `cell` input, so `interior` replaces both atoms, and the `panel` join stays. No other caller, no hand-rolled form, and no near-miss outside the classes the `Not:` line and the earlier results name: 516b51b7 and 639f5a19 consume `depth`'s value, 142ca369 and 409aa875 fold over one corner's directions, 60a26a3e tests a cell against a set it is not a member of, and 4c3d4a41's `refuted_dir` names a direction, not a cell. The scope's `Rim8` instances read `depth` and `rim_dir`, so it bears on neither the adjacency wording nor the interface.

Survey: 2026-09-10 07:02

The seventh survey read the 373 solvers whose file time is at or after the sixth survey's dispatch. It found four callers not yet listed, each with the instance's own `cell` input as its domain atom, so `interior` replaces both atoms:

- 689c358e — `center`, the one cross cell off the cross's rim, where the bars cross.
- 694f12f3 — `interior`, a rectangle's inside under the `$Erode` reading.
- 759f3fd3 — `rings.seed` inside `Parse`, the crossing of a cross, the seed the rings grow from.
- 7d7772cc — `thick`, a color some cell of which is off its rim; the head projects the cell away, so this is the existential read of the readout.

Nine listed callers were edited since with the operation unchanged: 1d398264, 2c0b0aff, 3bdb4ada, 3befdf3e (program and Determine), 522fdd07, 55059096, 58f5dbd5, 5b37cb25, and 800d221b. The `!\w*\.rim(` arm matched exactly these thirteen solvers. The hand-rolled arm found no caller: every negated defect rule over `dir_elem`/`dir8_elem` and `neighbor` in the scope tests a cell against a set it is not a member of (46c35fc7 `gap`, 54d82841 `walled`, 60a26a3e `ring_gap`, 6c434453 `open`, d9fac9be `defect` and `gap`, where `$Full` reads `!gap(P)` with no membership test on P), or is the outward dilation (71e489b6 `halo`).

No near-miss outside the classes the `Not:` line and the earlier results name. The per-direction class grows: 264363fd `attached`, 696d4842 `link`, 71e489b6 `figure_nbr`, and 7f4411dc `support` negate `rim_dir` and keep the direction; 264363fd and 696d4842 fold it through `Unanimous` to one direction, and 71e489b6 `continued` and 7f4411dc `support_kept` fold it to two distinct directions, so the cell they name is still on the rim. 7b80bb43 `flanked` hand-writes the fold over one axis's two directions, beside the corner folds of 142ca369 and 409aa875. 13e47133, 3ee1011a, 4290ef0e, 45a5af55, 516b51b7, 5751f35e, 639f5a19, and 85c4e7cd consume `depth`'s value; 1190bc91, 2b83f449, 465b7d93, 4c3d4a41, 5e6bbc0b, 692cd3b6, 142ca369, and 409aa875 read `rim_dir` positively; d9fac9be `outline` reads `rim` positively as a shape.

The scope holds four `Rim8` instances: 1d398264 and 800d221b read `rim` negatively and are listed already, and 13e47133 and 409aa875 read `depth` and `rim_dir`. The four new callers are cardinal `Rim` instances and take no extra column, so the scope bears on neither the adjacency wording nor the interface.
