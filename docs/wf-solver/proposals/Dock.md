# `Dock<Key>` — a footprint's translation to first contact

The final displacement of a multi-cell mover that slides in a direction until its moved footprint covers a stopper cell, per key: a walk over the displacements the frame admits advances one step at a time, and the first reachable contact displacement is where the mover rests. The rest displacement is the contact itself, so a footprint that already covers a stopper rests at ORIGIN.

```
.comp Dock<Key> {
    // The contact footprint's cells, per key.
    .decl mover(key: Key, p: Position)  // input

    // Contact cells — the mover arrives when it covers one.
    .decl stopper(key: Key, p: Position)  // input

    // The travel direction, per key.
    .decl dir(key: Key, d: Dir)  // input

    // The frame the travel crosses.
    .decl cell(p: Position)  // input

    // The displacements the frame admits toward the key's direction.
    .decl shift(key: Key, delta: Shift)
    shift(Ky, ORIGIN) :- dir(Ky, _).
    shift(Ky, Delta) :-
        cell(P), dir(Ky, D),
        axis_of(D, A), sub_extent(P, A, K), jump_delta(D, K, Delta).

    .decl halted(key: Key, delta: Shift)
    halted(Ky, Delta) :-
        shift(Ky, Delta), mover(Ky, P), compose(P, Delta, P2), stopper(Ky, P2).

    .decl reach(key: Key, delta: Shift)
    reach(Ky, ORIGIN) :- dir(Ky, _).
    reach(Ky, Delta2) :-
        reach(Ky, Delta), !halted(Ky, Delta),
        dir(Ky, D), neighbor(Delta, D, Delta2), shift(Ky, Delta2).

    // Where the mover comes to rest: the first reachable contact displacement.
    .decl rest(key: Key, delta: Shift)
    rest(Ky, Delta) :- reach(Ky, Delta), halted(Ky, Delta).
}
```

`shift` derives inside the comp: every caller writes the same derivation, two of them character-for-character, so a caller adds only a frame cell. `rest` is the sole output: what rides the rest displacement differs by caller — 05f2a901's `$Extent` case halts on its box interior while it paints the mover cells, 11dc524f composes a box Position, and 17829a00 carries each cell's color. What rides the rest displacement stays the caller's.

Not: lib `Slide` (a point mover standing in a free-node set, resting on the last free node — a dock rests at the first contact displacement, which is not a free node, and a footprint already in contact rests at ORIGIN, which no free-node set states); `Ray.stop` (a cast's first blocked cell, with no footprint); a translation stored as data or read off the target with `displacement`.

Match: `!halted` — a recursion over a Shift domain that steps by `neighbor` or `step_delta`+`compose` toward a move direction and is negated on a contact test composing a footprint against a stopper set. The `shift`/`halted`/`reach` names are corpus-wide (patterns.md "Slide until halted"). At survey time, `!halted` matched exactly the callers.

Survey: 2026-09-08 17:10

Callers:

- 05f2a901 — keyed by `Choice`: three contact cases feed one walk three (footprint, stopper) pairs.
- 11dc524f — the shape's bounding box docks against the block's box; the rest displacement carries the box home.
- 17829a00 — keyed by object `Ident`, each object with its own travel direction.

Near-misses:

- 56dc2b01 — a footprint that rests on the last displacement short of a line, not on the first contact displacement. It derives the contact set and hands lib `Slide` the complement, so where a task wants the step before contact, the free-node set is what states it.
- 332f06d7 — lib `Slide` over a Shift domain, the corpus's one Shift-typed `node` feed. The node set is the piece's fitting displacements, so the piece rests on the last free displacement, and its journey chains stops in four directions.
- 271d71e2 — contact-determined travel, but arrival is a universal over the moving face (the whole line ahead is marker), and the travel is picked by `Extremes` against a gauge count, with no walk. It would need the travel as a scalar step count, which `rest` does not expose.
- 16b78196 — flush seats between two footprints, enumerated as offsets and picked by interlock, with no travel direction.
- 16de56c4 — structurally the nearest `reach` match, but the mover is a single cell over Positions and the step is the rhythm's stride.
- 9c56f360 — `Ray` finds each line's free run, and the movers re-seat by rank within it.
- 1b8318e3 — a single dot's contact slide, chosen by a min over step counts; the contact test is a cell test, not a footprint cover.
- 320afe60, 05a7bcf2 — a body flush to the frame edge by `box.edge_min` + `jump`: no stopper set, no walk.
- 1caeab9d, 234bbc79, 2c181942 — translation by `displacement` onto a named target cell or line: no travel.

Spec question: does `dir` stay cardinal? The `shift` derivation reads `axis_of`, and every caller travels on a cardinal; a Dir8 dock would need a diagonal displacement domain the corpus has not written.

Survey: 2026-09-08 22:35, over the solvers at or after the first survey's time

That pass read the fifty solvers whose file time is at or after 17:10. It found no caller: `!halted` matched nothing, and no recursion over a Shift domain tests a footprint against a stopper set. Every near-miss falls in a class the `Not:` line or the list above already names, except `54dc2872` `$Slide`, whose L-shaped footprint moves onto a mark along a diagonal. That one bears on the spec question: it is the corpus's first footprint travelling toward a stopper on a diagonal, and `displacement` onto the mark gives it the translation directly, so it asks for no Dir8 form. A Dir8 `shift` would need the sub-extents of both of a corner's axes, which no solver writes.

Closed: 2026-09-09 23:05

Lib already holds the operation. A dock is `Slide` over a Shift domain: the node set is the displacements at which the footprint lies clear of the obstacle's cells, with ORIGIN added as a node, and `rest` from ORIGIN is the last clear displacement, which is the contact displacement the `Not:` line names as no free node — the obstacle's cells are the blocked set, and the stopper set of cells one step short of them is not needed. A footprint already in contact rests at ORIGIN, since `rest` returns the start when it cannot step. The three callers write that form now (`05f2a901`, `11dc524f`, `17829a00`), beside `56dc2b01`, which wrote it first.
