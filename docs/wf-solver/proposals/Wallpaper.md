# `Wallpaper<Key, Val>` — lattice-quotiented isometry detection

The isometry peer of `ShiftInvariance`: which isometries of the frame — a
D4 element composed with a shift — fix a keyed valued cell set, given the
set's per-axis periods. Candidates are quotiented by the translation
lattice: one representative per coset, its shift drawn from the lattice's
fundamental domain, and square-checked against the lattice where the kind
squares to the identity (a symmetry's square is a translation, and the
group's translations are the lattice). `ShiftInvariance.period` feeds the
`period` input directly. Lib target: program comp beside `ShiftInvariance`;
`Gen` moves beside it.

```
.type Gen = [d: D4, delta: Shift]

.comp Wallpaper<Key, Val> {
    .decl kind(d: D4)                           // input
    .decl cell(key: Key, p: Position, v: Val)   // input
    .decl grid(key: Key, p: Position)           // input
    .decl period(key: Key, a: Axis, k: number)  // input

    // Witnessed, uncontradicted coset representatives.
    .decl sym(key: Key, g: Gen)

    // Kinds with an admitted representative; the identity kind whenever a
    // lattice exists. A Sym-naming determination reads this.
    .decl kind_used(key: Key, d: D4)

    // One step along an admitted isometry or a lattice shift, over the
    // full grid — the map an orbit closure walks.
    .decl step(key: Key, p: Position, q: Position)
}
```

- A representative needs a witness — some cell pair it maps one onto the
  other; vacuous overlap is no evidence. The rest of its coset arrives by
  composition with the lattice in the caller's closure.
- The internal canonical corner for fundamental-domain shifts is
  unobservable: every corner yields the same cosets and maps.
- An axis without a period contributes only the zero shift, so an
  aperiodic grid degrades to center-anchored D4 detection.

**Caller.** 0dfd9992: wallpaper repair —
`Parse` feeds detected per-axis periods and the stored point group's
kinds; `out` closes survivor colors over `step`; its determination names the
kinds every example uses as a `point_group` Sym value.

Not: translation periodicity alone (`ShiftInvariance`); a fixed-frame symmetry (`D4Map`); a reflection about a line the data names.

Match: `ShiftInvariance`, `sym_member`, `apply(D`, `mismatch`, `witnessed`, `period`.

Callers: 0dfd9992 alone. Near: af22c60d, 981571dc with its twin 47996f11, 0934a4d8 (determination), 1b60fb0c search a mirror line or rotation center over an aperiodic pattern, where the comp tries no shift; the determination sites factor the search per axis over line indices.

Interface: `step` would carry its generator, `step(key, g, p, q)`; `period` stays an input; an aperiodic axis contributing its full extent would serve the four sites, but their per-axis factoring reads as a separate reflection-axis primitive.

Verdict: park. 2026-08-29.

Survey: 2026-10-05 17:22 — every solver.

Callers:
0dfd9992 wp — this is the surfacing solver, which holds the proposal comp Wallpaper itself. It feeds the intact cells as `cell`, every D4 element as `kind`, and `si.min_period` as `period`, and `out` closes the intact colors over `wp.step` so that each hole takes its orbit's color.
abbfd121 parse.near / parse.contradicted / parse.map (the `$IsometryOrbit` branch) — over the visible cells, this finds the maps that apply a D4 element and then a translation. A map counts when it carries some visible cell onto a visible cell of its color, its frame image lies within an axis period (`period.min_period`) of every edge, and it carries no cell's period-propagated color (`axis_color`) onto a different one. `parse.map_link` and `parse.color` then close those colors into the hidden cells.

Near-misses:
47996f11 Determine.mirrored / mirror_mismatch / axis_center, and its twin 981571dc Determine.mirrored / mirror_mismatch / axis_center — over an aperiodic pattern, these search a mirror line per axis as an offset from the grid center, and then run D4Map in the frame of the center found. Wallpaper rules them out because an axis with no period contributes only the zero shift. The runtime half (`counterpart`) is a fixed-frame symmetry about a stored center (Not: D4Map).
af22c60d Determine.band_map / broken / witnessed / mirror_band, and its representative-twin 3631a71a Determine.band_map / broken / witnessed / mirror_band — these find a mirror band per axis (a flip, then a jump of k) over an aperiodic pattern, factored over axis positions. Wallpaper tries no shift on an aperiodic axis. The runtime `mirror` reads a stored band.
0934a4d8 Determine.ext_map / ext_mismatch / ext_pair / axis_ext — this searches a one-sided frame extension per axis whose mirror is witnessed and unbroken, the same aperiodic per-axis shift search. The tile symmetry that follows is a fixed-frame D4Map (`inv`, `broken`, `cand_sym`) (Not: D4Map).
1b60fb0c placement / turn_step — the turn is stored (`params.sym`). `placement` is any shift that a single cell pair witnesses, with no contradiction test, and `turn_step` adds the cells the placed turn reaches. This is a generative orbit with no invariance detected, and there is no lattice.
8e5c0c38 mirrored — this finds a flip plus shift per shape, chosen as the placement that lands the most cells, which is a majority and not an uncontradicted symmetry. The axis is stored, and there is no lattice.
abbfd121 clash / parse.map (the `$LatticePeriod` branch) — `kind` here is the identity alone, with any witnessed, unclashed oblique translation (Not: translation periodicity alone). Its witness `lattice-no-axis` relaxes the per-axis periods that Wallpaper's `period` input presumes.
1d0a4b61 si, 29ec7d0e si, 484b58aa si, c3f564a4 si, ca8f78db si, 135a2760 si — wallpaper repair through OffsetInvariance, translation alone (Not: translation periodicity alone). The other OffsetInvariance solvers (017c7c7b si_line, 332efdb3 si, 50a16a69 si, 53b68214 si, 53fb4810 shift, 6a980be1 strip_shift, 7447852a si, 8403a5d5 si, 92e50de0 repeat, 963e52fc si_line) fall under the same exclusion.
b8825c91 sym (D4Map `compatible`), 47c1f68c grid_map / tile_map / broken / tile_broken, 21897d95 broken, 3e980e27 refuted, 73251a56 mirror, 5751f35e orbit_color, ce039d91 symmetric — each is a fixed-frame symmetry, detected through D4Map or a refutation over d4_elem, or stored, with no shift (Not: D4Map).
5b692c0f mirror (fold line of mark cells), 2b01abd0 mirror (line cell), 2bcee788 mirror (wall box), 3345333e mirror (`mirror_frame`), e729b7be image `$Marker` (crossing) — each is a reflection or turn about a line or point that the data names (Not: a reflection about a line the data names).

Spec:
- The entry's code form no longer matches its one source.
  - 0dfd9992's comp declares `sym(key, d, delta)` with no `Gen` type, and it declares no `kind_used`.
  - Its `kind` is fed from `d4_elem` and not from a stored point group, and the solver has no determination naming a `point_group` Sym.
  - The entry's Caller paragraph is contradicted on each of these points.
  - The code form also uses `Shift`, whose current name is `Offset`.
- The Match line uses `ShiftInvariance`, which the lib no longer declares (now `OffsetInvariance`), so it needs restating.
  - The shape is a variable D4 `apply` on a cell, whose image feeds `compose` or `relative` with an offset, under a negated contradiction over a valued cell set.
  - That shape is better stated in prose and matched with the parser than by the tokens `mismatch`, `witnessed`, `period`, which match broadly.
- Period input: both callers feed `min_period` (0dfd9992 `wp.period`, abbfd121 `axis_link` and `far`), and neither feeds `OffsetInvariance.period`. The entry's statement that `period` feeds the input directly does not hold at either site.
- Aperiodic behaviour: the two callers diverge.
  - With an axis that has no period, Wallpaper degrades to center-anchored D4.
  - abbfd121 reads no map at all (`aperiodic`, gating `near`).
  - Serving abbfd121 needs either a gate on that degradation or a caller-side filter.
- Contradiction set: abbfd121 takes its witness from the raw visible cells and tests contradiction against the period-closed colors (`axis_color`). Wallpaper reads one `cell` input for both, so serving abbfd121 needs a separate contradiction input.
- Quotient: abbfd121 bounds a map's translation by keeping its frame image within one axis period of every edge. It keeps several representatives per coset and has no square check. Wallpaper's fundamental-domain representatives with a square check are stricter, and whether the two give the same closure has not been shown.
- `step`: abbfd121 closes only into hidden cells, and 0dfd9992 closes over the full grid. Neither site needs the generator on `step`, so no site supports the earlier proposal `step(key, g, p, q)`.
- Unkeyed `kind` serves both sites.
- The six aperiodic per-axis mirror searches (47996f11, 981571dc, af22c60d, 3631a71a, 0934a4d8, and 1b60fb0c's placement) are the recurring pattern this survey found.
  - Each factors the shift search per axis over line positions, with a witnessed-and-unbroken test.
  - That pattern reads as a separate reflection-axis operation and not as a Wallpaper extension.

Reimplementations:
abbfd121 moves / kind `$LatticePeriod` — `d4_elem(D), !moves(D)` with `moves(D) :- apply_dir(D, X, Y), X != Y` picks out the identity, which the lib provides as `D4_ID`.
The parser matcher found 196 rules (122 solvers) whose `apply` takes a variable D4 argument; 48 of those rules (35 solvers) feed the image into `compose` or `relative`. A grep found 18 OffsetInvariance solvers and 17 solvers using `sym_member`. The symmetry, D4 and wallpaper solvers among those hits were read in their clauses.
