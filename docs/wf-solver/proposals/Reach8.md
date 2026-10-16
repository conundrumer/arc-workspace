# `Reach8<Key>` — seeded connectivity under 8-adjacency

The union of the 8-connected components a key's seeds select: `Reach` over the full Dir8 step set, so a flood crosses a diagonal contact. It stands beside `Components8` and `Rim8`, the extensions lib already holds for the same step set.

```
.comp Reach8<Key> : Reach<Key> {
    step(S) :- dir8_elem(D), step_delta(D, S).
}
```

Not: `Components8` (the components under the same steps, with no seed to select among them); `Reach` (the cardinal steps).

Match: a `Reach` instance whose `step` relation is fed from `dir8_elem`, in any layout of the feeding rule, and through any comp that inherits `Reach`; also the same flood written over `Components8`, where a distinguished cell picks the component and its id reaches nothing else. Match with the parser: an instance of `Reach` or of a comp extending it, beside a rule whose head is that instance's `step` with `dir8_elem` in its body; and a `Components8` instance whose `label` or `conn` carries a cell of a distinguished relation to a domain cell, with the component id in neither the rule head nor another atom.

Survey: 2026-09-11 08:36 — the whole corpus.

Callers:
88207623 blob — a `Reach<Ident>` whose step rule is fed from `dir8_elem`, giving the shape cells reached over 8-adjacency from each line; the one site in the corpus that writes the seeded 8-connected flood through `Reach`.
48d8fb45 marked — the cells of the blob the mark sits in, selected from the mark cell.
5034a0b5 blocked — the cells of each object that holds a cell facing the frame, selected from those facing cells.
137eaa0f obj_off — the cells of the mark's object, as offsets from the mark.
414297c0 glyph — the cells of the key cell's object, as displacements from the key.
3e980e27 footprint — the cells of the shape that holds a marker-colored cell, as displacements from that cell, in the Parse comp.
409aa875 box.cell — the cells of the launching mark's object, in the Determine comp; that instance is already keyed by [example, mark].
0962bcdd star_cell — the cells of the star that holds the input marker, as offsets from it, in the Determine comp.

Seven of these eight write the flood as a `Components8` `label` or `conn` join against a distinguished cell, and the component id serves that join alone. Each migrates by feeding `seed` and reading `reach`; where the site pairs every cell with its own seed (137eaa0f, 414297c0, 3e980e27, 409aa875, 0962bcdd), the key becomes the seed.

Negative evidence over the whole corpus of 749 solvers: the signature matched 3 rules that feed a step relation from `dir8_elem`, of which one is 88207623 and two are the near-misses below. The corpus holds 31 `Reach` instances and 64 `Components8` instances across 61 solvers; the callers above are the `Components8` instances that a seed picks from.

Near-misses:
36fdfd69 cluster.step and 6ffbe589 cluster.step — each feeds a `Components8` step from `dir8_elem`, then composes two such steps, so the step set joins cells across a one-cell gap rather than by contact, and no seed picks among the components.
0ca9ddb6 star_cell, 1da012fc marker, 2c737e39 drawing, 39a8645d copy, 62593bfd dest, 6d58a25d scattered, 6e4f6532 has_body, 6ecd11f4 shape_id, 72322fa7 untouched, 753ea09b rail, 8b7bacbf circuit — the component id is compared, counted, or keys per-component data, so these sites want component identity, which is the `Components8` exclusion.
239be575 apart and 5545f144 sym_cell — read `conn` over the whole node set, with every cell its own seed, so there is no seed set to flood from.
3befdf3e fig, 5117e062 region, 696d4842 crawl.init_untaken, 8a371977 ring_cell, b60334d2 template, d364b489 template — the same seeded selection over `Components`, the cardinal step set, which the `Reach` exclusion covers; the 30 `Reach` instances that keep the cardinal steps, among them 00d62c1b outside and 8b7bacbf box, fall under that exclusion too.
5207a7b5 region — a seeded flood whose step set comes from the parameters, a slant delta and a base direction, not the Dir8 unit steps.

Spec:
The interface needs no change. Every caller feeds `seed` and `node` and reads `reach`, and the keys they need — `Unit`, a color, a mark position, a record — are what the inherited `Reach<Key>` already takes; 409aa875 already carries the [example, mark] key the migration wants.

The `Match:` line does need to widen. As written it matches a `Reach` instance whose `step` is fed from `dir8_elem`, and that form stands at 88207623 alone, so on the current line the operation reads as caller-only. Seven further sites compute the same seeded 8-connected flood through `Components8`, and no survey of the current line reaches them. The added shape: a `Components8` instance whose `label` or `conn` carries a cell of a distinguished relation to a domain cell, with the component id appearing in neither the rule head nor another atom.

Reimplementations:
137eaa0f obj_off — two `label` atoms joined on one id; `Components.conn`.
3befdf3e fig — `Components.conn`.
3e980e27 footprint — `Components.conn`.
409aa875 box.cell — `Components.conn`.
5117e062 region — `Components.conn`.
696d4842 crawl.init_untaken — `Components.conn`.
72322fa7 untouched — `Components.conn`.
72322fa7 template — `Components.conn`.
8a371977 ring_cell — `Components.conn`.
b60334d2 template — `Components.conn`.
d364b489 template — `Components.conn`.

At each of these the id joins two cells and reaches nothing else, so one `conn` atom replaces the pair. Five further label-pair sites keep the id in the head (0ca9ddb6 star_cell, 1190bc91 seq, 2c737e39 drawing, 4b6b68e5 outline) and are not listed. Method: four matchers over the parsed corpus — a step relation fed from `dir8_elem` (3 hits), a recursive head with `dir8_elem` (0 hits), a `Components8` `label` pair or `conn` read in one rule (19 hits), and a cross-rule chain where one rule exports a component id read off a cell and another consumes it beside a `label` read (9 hits) — plus a scan of the 85 recursive rules that step by `neighbor`, `compose`, or `jump`, none of which floods over 8-adjacency. Each hit was read in its rule.
