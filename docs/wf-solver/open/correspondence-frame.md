# Correspondence frame: a derived extent, and a stored frame beside a decomposition

Open question in `principles.md`, Invariance — Stored or derived: the Unwitnessed derivation and Correspondence frame bullets.

## The question

Unwitnessed derivation says a derivation the pairs never separate from a constant stands only beside the stored case. Correspondence frame exempts "a frame built as a correspondence over input cells", by the form of the encoding. Two gaps:

- A derived extent that is constant on every example owes the stored case or not by how it is written: as a correspondence (`concat_2d` over reads of `in`) it is exempt; as a number passed to a decomposition comp it is not. 363442ee cuts its canvas by the key box's extent (3 on every example); 19bb5feb's output frame is the product of its two rank sets (2 on every example); 79cce52d's is an axis frame from a line count (6).
- The panel-combine fold takes its output cell from the intile position of `decompose`, a correspondence over tile cells, and fifteen approved files store the frame's extent beside it as `frame_dim` and range the fold over `params.frame`. Under the count branch, `divisor` and the input extent fix the tile extent, and the stored frame states it a second time; the two disagree on any input whose tile extent is not the stored one.

## The text

> - **Unwitnessed derivation.** An unwitnessed derivation stands only as a case beside the stored case.
>     - 3b4c2228
> - **Setup derivation.** Setup gets no case, so it cannot include an unwitnessed derivation.
> - **Correspondence frame.** Because the pairs witness a correspondence cell by cell, a frame built as a correspondence over input cells (007bbfb7) derives no number.

## Candidate text

> - **Correspondence frame.** A frame built as a correspondence over input structures, cells, tiles, lines, or ranks, derives no number: the pairs witness the correspondence cell by cell, so no stored case stands beside it, and a parameter that states its extent admits values that contradict it on the inputs where the structures differ.
>     - 007bbfb7
>     - 19bb5feb
> - **Cut by a number.** A number that cuts a given frame into structures is a derivation, whatever fixes its value inside the program, and Unwitnessed derivation decides its stored case.

The contradiction clause is Invariance's "No two parameters admit values that contradict" under the count branch, and Redundant values (`style.md`, Params) under the table and size branches.

## Where the approved corpus stands

- Fifteen files store the frame beside the decomposition: f2829549, 0c9aba6e, 1b2d62fb, 6430c8c4, 5d2a5c43, 195ba7dc, 506d28a5, 66f2d22f, d19f7514, cf98881b, 3428a4f5, 31d5ba1a, 34b99a2b, 99b1bc43, e3497940. Seven siblings in the same families take the output cell from `decompose` and hold no frame: 0520fde7, 94f9d214, e133d23d, ce4f8723, dae9d2b5, e345f17b, fafffa47. The change in the fifteen is one mechanical edit: the fold's output cell comes from `decompose`, `frame` and `dec_choice` go, and `frame_dim` stays as the tile extent under the Table and Size marker. In 31d5ba1a, 3428a4f5, 34b99a2b, and 99b1bc43 the edit sits at `filled.domain`.
- 19bb5feb, 79cce52d, f8b3ba0a carry a constant derived extent and no stored case. Under the candidate text their frames are correspondences over ranks and lines, and they stand. Under the text as written, 19bb5feb owes a `Stored` case (its stored candidate returns a bare background grid, a valid divergence under `unchanged-output.md`), while 79cce52d's and f8b3ba0a's stored candidates are partial and Ill-formed divergence removes them.
- 4522001f (a stored canvas that holds boxes at any extent), 3b4c2228, 137eaa0f, a6953f00, bc1d5164, be03b35f, 5bd6f4ac, d10ecb37 stand under both texts: their frames are stored windows that ground the output cell, not correspondences.
- 103eff5b is no precedent for a constant derived extent: `run_dl.py derived-constant 103eff5b` reports no constant relation, so its derivation is witnessed.

## Solvers

- 363442ee (draft) — `cvt.dim` reads the key box's extent and is 3 on every example. The number cuts a given canvas, so under both texts the stored case is owed: a third case with a stored `tile_dim`. Its report's grounds against it were the pin inside the program (which the candidate text sets aside), the untransformed output (`unchanged-output.md`), and 103eff5b (above).
- 48f8583b (draft) — its frame is `concat_2d` over two reads of `in`, exempt under both texts; nothing changes.

## Witnesses

6430c8c4, a 7×4 input, divisor 2 with a gap, stored extent 4; two cases of one file emit two frames:

```
7 . . .      [Count, Lookup], from the decomposition:   [Count, Nor], the stored frame:
. . . .      . 3 3 3                                     3 3 3 3
. . . 7      3 3 . 3                                     3 3 3 3
4 4 4 4      3 3 3 .                                     3 3 3 3
. . . .                                                  3 3 3 3
. . 2 .
. . . .
```

99b1bc43 on the same grid reports inconsistent grid bounds for `[Count, Xor]`.

19bb5feb, three markers; the derived frame against a stored 2×2:

```
2 . . . .        derived 3×3:    stored 2×2:
. . . . .        2 . .           . .
. . 3 . .        . 3 .           . .
. . . . .        . . 4
. . . . 4
```

363442ee, a 3×2 key on an 8-wide canvas:

```
4 2 5 . . . . . . .    derived extent: the key stamps at the mark's 3×2 tile
2 6 5 . . . . . . .    stored extent 3: no key cell meets a tile cell, the input returns
6 4 5 . . . . . . .
. . 5 . . 1 . . . .
```
