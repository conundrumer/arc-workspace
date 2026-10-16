# override-input-defaults — caller-replaceable defaults on `@input` relations

A change to the comps whose `@input` relations carry default facts: each such comp, where justified, gains a form in which the caller supplies that relation in full. Souffle's `.override` is the mechanism — a derived comp marks the relation `.override` and gives it no clauses, and that drops the inherited defaults:

```
.comp <name><Key> : <comp><Key> {
    .override <relation>
}
```

Today one relation qualifies: `Components.step`, the four cardinal steps, inherited by `Components8` and `Reach`. A caller whose step set excludes the units carries the defaults as dead facts it cannot remove. An override in a grandchild (`: Reach<Key>`) must drop the grandparent's facts; before promotion, verify that with a step set that excludes the units over two adjacent nodes.

Not: a derived comp that adds to a base's `@input` (`Components8.step`; `Between.dir`, derived from `axis`); an internal relation with baked-in values (`Rim._dir`), which no caller populates; an `@input` with no default facts.

Match: an instance of a comp whose `@input` carries default facts, where the instance's feed of that relation holds only values outside the defaults — for `step`, offsets that are all non-unit: `jump_offset` at k >= 2, a composed step, or a stored offset; a comment beside such a feed saying the defaults never fire; a local recursive relation written in place of a Components-family instance, whose recursive clause steps by any set other than the four cardinals — `jump` or `jump_offset` at k >= 2, `neighbor` under a restricted or keyed direction set, or `compose` with a stored offset. A frame walk with no node set, and a step that carries state, are not that statement. Match with the parser.

Survey: 2026-09-18 11:38 — every solver.

Callers:
9ba4a9aa trail — a `Reach<Color>` over the dots, seeded beside the source square, whose `step` feed is `jump_offset` on each cardinal at `params.spacing` (2); the comment above the instance says the inherited unit steps never fire because dots are never adjacent. This is the override-input-defaults site: the feed holds only non-unit offsets, and the four default facts of `Components.step` are dead facts the caller cannot remove. The instance is a grandchild (`Reach`), so the promotion check the entry names (an override in `: Reach<Key>` dropping the grandparent's facts) is what this caller needs.

No second caller. Across the 806 solvers, 339 instances of the family were found (233 `Components`, 72 `Components8`, 34 `Reach`), and four of them feed `step` at all; the other three keep the defaults live (below). No solver declares a comp derived from the family, and no solver uses `.override`.

Near-misses:
36fdfd69 cluster and 6ffbe589 cluster — `Components8<Unit>` whose `step` feed composes two `dir8_elem` unit steps, so marks cluster across a one-cell gap. The composed set contains every unit step (a diagonal plus a perpendicular cardinal is a cardinal), so the feed does not hold only values outside the defaults; the defaults fire. Excluded by the match condition. The two feeds are identical text (the GapComponents proposal's shape).
88207623 blob — `Reach<Ident>` whose `step` feed adds the eight `step_offset` directions, so a line's attached shape floods over 8-adjacency. The cardinals fire; the feed adds to the defaults rather than replacing them. Excluded by the match condition (the Reach8 proposal's shape).
Local recursion stepping by `jump` at a stored or derived count, over the frame rather than a node set, with a seed and `in(Q, _)` or a frame relation as the only membership test: 017c7c7b fill, 332efdb3 out, 53b68214 out, 53fb4810 pattern, 6a980be1 strip_out, 7447852a mark_cell, 834ec97d beam, 8eb1be9a out, 92e50de0 copy_tile and paint, 963e52fc out, 9b30e358 fill, d492a647 lattice, 0b17323b walk, 12422b43 copy. Each is a period continuation or lattice closure, the LatticeOrbit proposal's shape, which itself excludes a flood over adjacency (`Reach`). They are not written in place of a Components-family instance, so the match's last clause rules them out.
Local recursion stepping by `jump` at a count that varies per member (a box extent, a tally, a shape size): 447fd412 carry, 4acc7107 lane and slot, 20a9e565 slot, 9b2a60aa slot, 58e15b12 trace. These are placement walks, not floods over a node set; same exclusion as the class above.

Spec:
No change to the operation's interface or definition follows from the sites. The one match is the surfacing solver, so the evidence for the override form is caller-only. The three other `step` feeds in the corpus all add to the defaults and want them live, which agrees with the entry's boundary (a derived comp or caller that adds to a base's `@input` is not the operation). The entry leaves the name of each derived comp open; the only instance the evidence justifies is a `Reach` form, since the surfacing site is `Reach<Color>`, and the promotion check the entry states (a grandchild override dropping the grandparent's facts) is the check that site needs. The non-unit-step recursions found outside the family (the two near-miss classes) run over the frame with no node set, and the LatticeOrbit proposal addresses them; they give the override form no callers unless that proposal were built on `Reach`, which its own entry excludes.

Reimplementations: none.
Search method: a parser script over `each_solver()` collected every `.init` whose comp is `Components`, `Components8`, `Reach`, or a solver comp derived from one (none exist), then every rule whose head is `<instance>.step` in that instance's scope (4 hits, all read above); every local recursive rule (head bare, same relation positive in the body) whose body holds `jump` or `jump_offset` with a count other than the literal 1 (24 hits in 21 solvers, all read above); and a text grep for `.override` (0 hits) and for comments about defaults not firing (1 hit, 9ba4a9aa).
