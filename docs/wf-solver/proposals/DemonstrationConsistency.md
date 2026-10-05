# `DemonstrationConsistency<Demonstrated, Object, Index, Value>` — the choices consistent with a demonstrated pair of objects

The choices, out of a catalog, whose prediction for the first object of a caller-supplied demonstrated pair holds the second object's value at every index of the second object. Each object is an indexed family: its value at each index. The program states each choice's prediction under that choice; the demonstrated pairs say which choice the input teaches, so nothing about the choice is stored. Which pairs are demonstrated, whether every demonstrated pair must agree, and what a consistent choice is then applied to, are the caller's: a caller that knows a pair but not its direction supplies both orders, and a caller that wants every pair of a chain to agree negates `consistent` over its own demonstration relation.

Code form:

```
.comp DemonstrationConsistency<Demonstrated, Object, Index, Value> {
    // Each object's value at each index, total over the object's index set.
    .decl value(o: Object, i: Index, v: Value)  // @input

    // Each choice's prediction for each object.
    .decl prediction(c: Demonstrated, o: Object, i: Index, v: Value)  // @input

    // The demonstrated pairs: o is the pair's input, o2 its output.
    .decl demonstration(o: Object, o2: Object)  // @input

    // Choice c's prediction for o differs from o2 at some index of o2.
    .decl counterexample(c: Demonstrated, o: Object, o2: Object)
    counterexample(C, O, O2) :-
        demonstration(O, O2), prediction(C, O, I, V),
        value(O2, I, V2), V != V2.                            // a different value
    counterexample(C, O, O2) :-
        demonstration(O, O2), prediction(C, O, _, _),
        value(O2, I, _), !prediction(C, O, I, _).             // an index left out

    // Choice c is consistent with the pair: its prediction for o holds o2.
    .decl consistent(c: Demonstrated, o: Object, o2: Object)
    consistent(C, O, O2) :-
        demonstration(O, O2), prediction(C, O, _, _), !counterexample(C, O, O2).
}
```

A prediction that reaches an index the second object lacks is not contradicted: the comp reads consistency at the second object's indices.

Why it is lib. The operation is not a property over a domain; it is the structure of a task kind. In a subtask task each input holds the observed data of a task of its own, a demonstrated pair and an object left to complete, and the output is that inner task's test output. The handbook's determination, which keeps the values no example contradicts, runs inside the program on the pair the input carries, and the catalog is the inner task's choice, settled by the demonstration instead of left open. The comp is that inner determination. It stands with `TiebreakResolutions` as what a task kind needs: a comp, a solver-declared type, and solver-file rules, justified together by the kind and not by a count of callers. In the chain callers the input holds a sequence instead of a pair and a remainder: every consecutive pair demonstrates one value, and nothing is held out. The operation is the same.

The catalog may hold distinct rules or one parameter's values; both are the same operation, and in the second the type argument is the parameter's type. Distinct rules are named by a solver-declared ADT, `DemonstratedChoice`, the second solver-declared ADT beside `Choice`:

```
.type DemonstratedChoice = Extend {} | Span {} | Reflect {}
```

The solver-file rules for it, under a section "Demonstrated choice" beside "Alt outputs": the constructors of `DemonstratedChoice` name the rules the input may demonstrate; each rule's prediction is written under its constructor; no parameter stores which rule applies; the choice is derived from the pair it is consistent with. An ADT whose constructors are joined to predictions with no demonstration selecting among them is a disjunction, and is written as one.

Not: a rule the task's own train pairs fix, which is stored as a parameter; `Choice` cases, which are peer models of one task rather than a catalog the input selects from; a best-match or closest choice, where counterexamples are counted instead of negated; matching by resemblance (`Occurrences`, `D4Map`); `KeyedSetCompare.equals`, which states the exact match of one set against one pattern and stops there; a candidate tested against the one object it then renders, with no second object; a catalog ADT that dispatches a disjunction, with nothing demonstrated.

Match: a site that tests several candidate choices' predictions for one object against a second object, index by index, and keeps the choices no index contradicts. In the shape above the test is a counterexample relation negated inside a pair rule; a site may instead compare through `KeyedSetCompare.equals` over `[i, v]` members, or carry the pair as a record. Grep: a negated per-index mismatch between two object-keyed valued relations; `.equals(` beside an object inequality; the solvers whose `@keywords` line holds `induce`.

Survey: 2026-09-03 15:39

Result: two callers beside the surfacing solver, both keying the catalog by a parameter rather than by distinct rules — a Shift in 351d6448, a period number in 20a9e565 — so the `Key` column carries the catalog at every site. 20a9e565's `period_defect` is the two defect clauses verbatim. Both callers want every consecutive pair of an ordered chain to carry, which is one caller-level universal over `demo`; 20a9e565 then takes a minimum over the survivors, which is tie-resolution after the negation and stays outside the operation.

~~The survey settled the interface at `demo`.~~ The surfacing solver's `answer` — the object left over by the demonstrated pair, read under that parse — presumed exactly three objects and one demonstration, and neither other caller has a leftover object: in both, the further object is one that demonstrated the rule.

Near, all ruled out: a candidate tested against the single object it then renders (3345333e's `contradicted`, with an inexact carry that an occluded cell upholds; 7b7f7511's `dup_mismatch`, self-consistency of one object under `Unanimous.clash`); one parse rather than a catalog, with the negation selecting which objects match (321b1fc6's `unmatched`) or which fit criterion holds as a `Choice` case (bbb1b8b6's `unfit`); a global covering condition in place of a cell-by-cell carry (50846271's `span`); a best match by count (2ccd9fef's `miss`/`fewest` — its split pick; its velocity site is a caller — and 1b60fb0c's `restored`); the uniqueness selectors, which stop at picking the object with no equal (38007db0, a87f7484, 15660dd6); a rule read off the input with no candidate tested against another (4c416de3, 39e1d7f9). Thirty-odd `Determine` comps hold defect relations of the same shape and are all excluded: there the rule is fixed by the train pairs.

Callers:

- 4c7dc4dd (`extend`, `span`, `reflect` — three parses of a panel, a `Rule` ADT as the keys)
- 351d6448 (`refuted` — candidate wave velocities, the parse repainting each animation frame)
- 20a9e565 (`period_defect` — candidate growth periods, the parse replaying each layer one period on)
- 2ccd9fef (candidate end velocities — read off the last step today; a chain carry over `demo` validates them throughout, as in 351d6448)

Survey: 2026-10-05 17:21 — the solvers since 2026-09-03 15:39.

Callers:
351d6448 refuted — DemonstrationConsistency would serve this site. The catalog is the candidate wave velocities `cand`. Each velocity's prediction is the `paint` the wave makes on a frame. Each consecutive frame pair in `succ_panel` demonstrates that velocity, and `out` keeps the velocity no step refutes and renders the last frame under it.
4c7dc4dd defect — the solver-local `Induce<Key, Obj, Val>` comp holds the operation. Its `defect` clauses are the code form's two counterexample clauses verbatim, keyed by the `Rule` ADT (`Extend`, `Span`, `Reflect`), and its `demo` is the code form's `consistent`.
No other solver in the scope states the operation.

Near-misses:
3345333e contradicted — a candidate mirror box is tested against the figure that box then completes. Exclusion: a candidate tested against the one object it then renders, with no second object.
8a6d367c contradicted — a candidate shape pattern is tested against the fill of the frame's inside, and that same shape then renders the inside, through `blocks.tile`. Exclusion: a candidate tested against the one object it then renders. The test is also one-sided: a fill cell in a block the pattern leaves empty contradicts the shape, and nothing checks the reverse.
abbfd121 clash — a candidate lattice translation is tested against the visible cells of the one grid it then repairs. Exclusion: a candidate tested against the one object it then renders, which here is self-consistency under the translation.
846bdb03 defect — a catalog of D4 transforms is tested against the bars, a second object, but the test is a contact condition: each bar must touch a cell of its color. It is not a carry compared index by index, so the site fails the Match shape. No `Not:` clause names this case.
50846271 span — the arm read off the marks is a global covering condition (`orphan`, `unmatched` against `covers`), not a cell-by-cell carry. Like 846bdb03 defect, no `Not:` clause names it.
5dbc8537 congruent, 88a62173 alike, 66ac4c3b line_set, 38007db0 band_peer and grid_peer — each uses `.equals(` beside an object inequality, as the exact match of one set against another with no catalog of choices. Exclusion: `KeyedSetCompare.equals` stops at the exact match. 38007db0 is also a uniqueness selector that picks the object with no equal.
776ffc46 same_shape, 845d6e51 onto (`cong.map` from `D4Map`) — the `induce`-keyword solvers match shapes by congruence. Exclusion: matching by resemblance (`Occurrences`, `D4Map`).
72322fa7 template, 82819916 recolor, 2e65ae53 tile_color, 57edb29d design — the remaining `induce`-keyword solvers read the rule off the demonstrating object directly. Exclusion: a rule read off the input with no candidate tested against another object. The same exclusion covers 4c416de3 and 39e1d7f9.
1b60fb0c restored — exclusion: one parse per `Choice` case, which is a peer model and not a catalog the input selects from.
9b5080bb defect, a251c730 defect, aab50785 defect — each marks a `Choice` case undefined on the input. Exclusion: `Choice` cases, with nothing demonstrated.
2dc579da differs, 9a4bb226 shared, 358ba94e shared — each picks the tile or block that no other equals or ties. Exclusion: the uniqueness selectors.
90c28cc7 differ, 9b365c51 differ — these compare neighboring lines to find block cuts. There is no catalog of choices, and the comparison is one parse with nothing demonstrated.
a3325580 differ — this compares two open values' tiebreak resolutions with each other. It is the open-values join, and no demonstration selects a value.
Determine comps — 28 hits from the per-index defect matcher sit inside `.comp Determine`, for example 3e980e27 refuted, 5ecac7f7 refuted, 5a719d11 contradicted, 85fa5666 contradicted, and the `*_contradicted` relations in a09f6c25, a251c730, a2d730bd, aa62e3f4, aaef0977 and abc82100. Exclusion: there the task's own train pairs fix the rule.

Spec:
At 351d6448 refuted, the check runs at the prediction's indices, not at the second object's:
1. The first clause requires every cell the wave paints to be a change the next frame makes in that color.
2. The second clause refutes a velocity whose wave reaches a cell outside the panel.
3. No clause requires every change of the next frame to be painted.

The code form reads consistency only at o2's indices, and it states that a prediction reaching an index o2 lacks is not contradicted. 351d6448 makes the opposite choice on both points. The comp would therefore either need a direction for the check, at o2's indices or at the prediction's indices, with a reach past o2 counting as a counterexample; or it would need to drop the claim that one direction is the operation. This signal comes from 351d6448, a caller other than the surfacing solver.

The code form's `demonstration` relation is an `@input`, and 4c7dc4dd's `demo` instead derives the pair inside the comp, from any O != O2 with no defect. That signal is caller-only.

846bdb03 defect and 50846271 span are two sites where a candidate is tested against a second object by a contact or covering condition, not by an index-by-index carry. The `Not:` line could name that case, which would replace the near-miss class the earlier survey stated without a `Not:` clause.

Reimplementations:
ac0c5833 rival and reading — in its first clause, `rival` with `reading` (a candidate kept where no candidate of another color stands at the same key) is `Unanimous` over `reading_cand`. The `$DerivedStride` clause of `rival` adds a clash across N, and `Unanimous` does not cover that clause.
8b7bacbf multi_cell and marker — `marker` keeps the color with exactly one ink cell, which `Tally` gives as a size of 1.
The parser matcher looked for two positive atoms that share a variable, with a disequality between their bindings, under a head that some other rule negates. It ran over the solvers' own units and gave 83 hits across 56 solvers, 28 of them inside Determine comps. A grep for `.equals(` gave 41 lines across 31 solvers. A grep for relations named for refuting, contradicting or defects outside Determine comps found 7 relations in 7 solvers. Nine solvers in scope have `induce` on their `@keywords` line.
