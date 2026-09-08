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
