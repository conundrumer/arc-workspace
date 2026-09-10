# `Checkerboard<Key>` — the two shades of a cell set's 2-coloring

The parity class of each cell of a keyed cell set, read against a seed cell: `light` is the seed's shade, the cells an even count of unit steps from it, and `dark` is the rest. The seed fixes the phase, so a solver keys data by shade without a number: the seed is the corner the phase is anchored at, or the mark whose class the output follows.

```
.comp Checkerboard<Key> {
    // The cell set the 2-coloring covers, per key.
    .decl cell(key: Key, p: Position)  // input

    // The cell whose shade is `light`, per key.
    .decl seed(key: Key, p: Position)  // input

    .decl light(key: Key, p: Position)
    .decl dark(key: Key, p: Position)

    light(K, P) :- seed(K, P), cell(K, P).
    dark(K, Q) :- light(K, P), dir_elem(D), neighbor(P, D, Q), cell(K, Q).
    light(K, Q) :- dark(K, P), dir_elem(D), neighbor(P, D, Q), cell(K, Q).
}
```

Solver-local form (7ec998c9), the shade carried as a payload that swaps each step:

```
.decl shade(p: Position, s: Sense)
shade(P, S) :-
    in(P, _), params.corner(Diag), corner_dist(P, Diag, 0),   // the anchor corner cell
    params.corner_sense(S).
shade(Q, S2) :-
    shade(P, S), sense_elem(S2), S2 != S,   // the other sense
    dir_elem(D), neighbor(P, D, Q), in(Q, _).
```

The closure reaches the seed's connected part of the set. A parity test over corner distances (`same_phase` at period 2) reaches every cell of the set, connected or not, and needs no seed cell, only a corner; which reading the callers need is the spec question.

Not: a lattice of stored period reached by period-sized jumps (`LatticeOrbit`), whose period-2 class on both axes is a quarter of the cells, not a half; alternation along one line (d492a647, 834ec97d, 3ac3eb23 `$Parity`); the residue of one distance read into a table (`stride`); a tiling of 2×2 blocks (`divide_by_size_2d`).

Match: a recursive relation over positions whose step is one cardinal `neighbor` and whose head value or membership swaps each step — a payload swapped through an `alt` relation or a `!=` over a two-element class, or two heads that feed each other. Also a rule testing two cells' corner distances for equal residue at period 2, through `stride` or `same_phase`. Grep `neighbor(` in rules whose head the rule reads, and `stride(.*2,`; match the shape with the parser (`tests/test_ast_match.py`).

Survey: 2026-09-10 06:44

The survey read the whole corpus (690 solvers): a grep for `stride(.*2,`, `same_phase`, and checker/parity/shade names; a parser match for a self-recursive rule that steps by `neighbor`/`jump`/`compose` and changes a non-position argument (43 hits, each read), and for two relations feeding each other through a step (no hits); and every rule where `corner_dist` and `stride` co-occur.

Callers:

- `programs/solvers/7ec998c9.dl` — `shade`: closure over the whole grid from the anchor corner, a `Sense` payload swapped each step; read once, at the mark, to choose the turn sense.
- `programs/solvers/2072aba6.dl` — `checker` under `$Checker`: closure over the output frame from the corners of a stored DiagAxis, a `Color` payload swapped each step through a stored 2-cycle `alt`; read per output cell, masked to the ink silhouette.
- `programs/solvers/5e6bbc0b.dl` — `block_cell` under `$Parity`: the corner-distance parity test at a stored `period(2)`, from every corner, seeded at the mark; membership only, with `!block_cell` as the fill.

Near-misses:

- The same corner-distance residue form at period 4: c1990cce `echo` under `$Stripe` and `Determine.striped` — diagonal stripes, one class of four.
- A seeded 2-coloring by even-length walks over region `Ident`s with `across` edges: 3bd292e8 `same_side`. The nodes are not cells and the step is not `neighbor`; it reads both shades as membership and negation.
- A period-2 lattice or one line, by two unit steps in one direction per closure step: d492a647 `lattice` and 834ec97d `beam` under `$Parity`.
- Alternation along one line or along erosion depth: 3ac3eb23 `walk`, 0a938d79 `line`, 1e97544e `flow`, 97999447 `$Toggle`, 759f3fd3's ring cycle.
- A D4 pose composed per tile step, whose classes are per-axis parity, a quarter of the tiles: the reflect-unfolds (`unfold_val` in 0c786b71, 3af2c5a8, 4c4377d9, 59341089, 62c24649, 67e8384a, 6d0aefbc, 6fa7a44f, 833dafe3, 8be77c9e, 8d5021e8, bc4146bd, c48954c1, c9e6f938, eb281b96; 47c1f68c `unfold`; 8e5a5113 `content`).
- A payload that advances rather than swaps: the walks, beams, spirals, and dilation depths of 08573cc6, 195c6913, 212895b5, 28e73c20, 351d6448, 4acc7107, 4e34c42c, 508bd3b6, 60d73be6, 69889d6e, 6df30ad6, 72207abc, 7d419a02, 7e2bad24, e179c5f4, 20a9e565.

Spec:

- Closure or parity test. At every caller the cell set is a connected rectangle and the seed lies in it, so the two readings coincide. The parity test needs a corner, which 5e6bbc0b takes from `diag_dir_elem`, so neither form adds an orientation choice. Only the closure reading states the near-miss 3bd292e8, which has no coordinates: with the step as a caller-supplied edge over a generic `T`, and `Checkerboard<Key>` as the cardinal-neighbor Position subclass (as `Components8 : Components` is built), 3bd292e8 becomes a caller and the three cell callers supply one cardinal edge each.
- Payload or membership. 5e6bbc0b needs membership only. 7ec998c9 and 2072aba6 carry a payload whose per-step swap is the `other` operation over a two-member class (`proposals/other.md`); with `light`/`dark` membership, each reads its payload once at the consumer through a two-branch disjunction. Membership serves all three callers.
- 5e6bbc0b's `period` parameter admits values that leave the checkerboard family (c1990cce's stripes at 4). Under the comp the 2 is structural and the parameter goes.

Reimplementations: none of `programs/lib.dl`.
