# `dir8_flank` — the two Dir8 an eighth-turn away

The two directions that straddle d: a corner's two cardinals, or the two corners that hold a cardinal. It is the Dir8 peer of `perp_dir`, which states the quarter turn over Dir, and it needs both readings of `dir_of` at once because a Dir8 domain mixes the two kinds.

```
.decl dir8_flank(d: Dir8, e: Dir8)
dir8_flank(D, E) :- dir_of(D, _, E).
dir8_flank(D, E) :- dir_of(E, _, D).
```

Not: a source direction whose kind the rule fixes — `dir_of` states that reading alone, in one atom; `dir_of` with the axis tag read; `diag_dirs` (a corner's two cardinals laid out wide); `perp_dir` and `turn` (the quarter turn, over Dir); `dir8_opposite` (the half turn).

Match: a rule that leaves the source direction's kind open — a `dir8_elem` or other mixed domain — and pairs it with the directions an eighth-turn away. Grep `dir_of(`, `diag_dirs(`, `diag_axis_of(`, then keep the rules whose source kind is not fixed.

Survey: 2026-09-02 02:32

Result: over 472 solvers the operation holds at one site. The signature returns 86 hits in 53 files; the discriminator that separates them is whether the rule fixes the source direction's kind. Where it does, the second rule adds nothing and `dir_of` states the site in one atom, which is the whole of the other 85 hits. D4 acts in quarter turns, so `apply_dir8` cannot state the eighth turn; `dir_of`'s two readings are what reach it.

Spec: no change to the interface. The union's content beyond `dir_of` is observable only where the source kind is open, which the corpus does once.

Callers:

- 409aa875 — declared as `dir8_flank`, read by `no_arm` and by `arrow_cell`'s arm branch. `apex(P, G)` ranges G over `dir8_elem`, so an arrowhead's two arms are the two directions an eighth-turn from G: cardinals when G is a corner, corners when G is a cardinal. Both readings fire under one variable.

Near: 142ca369 (`no_arm` and `elbow` — the same defect-negation over two arms, with G ranging over `diag_dir_elem`); 3d6c6e23, 3ac3eb23, 8618d23e, c1990cce, a6953f00, 2546ccf6 (the corners holding a cardinal, source kind fixed); 08573cc6, 14b8e18c, 15663ba9, 1e81d6f9, 291dc1e1, 3979b1a8, 695367ec, a406ac07, 21897d95 (a corner's two cardinals); 35ab12c3 (`straddled` over a mixed Dir8 domain, but by a quarter turn).
