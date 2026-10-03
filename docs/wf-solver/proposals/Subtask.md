# `Subtask<Rule, Object, Index, Value>` — the candidate rules a train pair of objects fits

The candidate rules, out of a catalog, whose prediction for the first object of a caller-supplied train pair equals the second object at every index. Each object is an indexed family: its value at each index. The program states each candidate rule's prediction under that rule; the train pairs say which rule the input teaches, so nothing about the rule is stored. Which pairs are train pairs, whether every train pair must fit, and what a fitting rule is then applied to, are the caller's: a caller that knows a pair but not its direction supplies both orders, and a caller that wants every pair of a chain to fit negates `fits` over its own train relation.

Code form:

```
.comp Subtask<Rule, Object, Index, Value> {
    // Each object's value at each index, total over the object's index set.
    .decl value(o: Object, i: Index, v: Value)  // @input

    // Each candidate rule's prediction for each object.
    .decl prediction(r: Rule, o: Object, i: Index, v: Value)  // @input

    // The pairs the rules are tested on: o is the pair's input, o2 its output.
    .decl train(o: Object, o2: Object)  // @input

    // Rule r's prediction for o differs from o2 at some index.
    .decl counterexample(r: Rule, o: Object, o2: Object)
    counterexample(R, O, O2) :-
        train(O, O2), prediction(R, O, I, V),
        value(O2, I, V2), V != V2.                            // a different value
    counterexample(R, O, O2) :-
        train(O, O2), prediction(R, O, _, _),
        value(O2, I, _), !prediction(R, O, I, _).             // an index left out

    // Rule r carries o exactly onto o2.
    .decl fits(r: Rule, o: Object, o2: Object)
    fits(R, O, O2) :-
        train(O, O2), prediction(R, O, _, _), !counterexample(R, O, O2).
}
```

The catalog may hold distinct rules or one rule's parameters; both are the same operation. A catalog of distinct rules names them with a solver-defined ADT filling `Rule`:

```
.type Rule = Extend {} | Span {} | Reflect {}
```

That ADT is this comp's own override of the style rule that an ADT lives inside `Choice` alone: the branch names carry the catalog members' identity the way `Choice` case names carry peer models', and a record of fabricated numbers would be an enum in disguise.

Not: a rule the task's own train pairs fix, which is stored as a parameter; `Choice` cases, which are peer models of one task rather than a catalog the input picks from; a best-match or closest rule, where counterexamples are counted instead of negated; matching by resemblance (`Occurrences`, `D4Map`); `KeyedSetCompare.equals`, which states the exact match of one set against one pattern and stops there; a candidate tested against the one object it then renders, with no second object.

Match: a site that tests several candidate rules' predictions for one object against a second object, index by index, and keeps the rules no index contradicts. In the shape above the test is a counterexample relation negated inside a pair rule; a site may instead compare through `KeyedSetCompare.equals` over `[i, v]` members, or carry the pair as a record. Grep: a negated per-index mismatch between two object-keyed valued relations; `.equals(` beside an object inequality; the solvers whose `@keywords` line holds `induce`.

Survey: 2026-09-03 15:39

Result: two callers beside the surfacing solver, both keying the catalog by a parameter rather than by distinct rules — a Shift in 351d6448, a period number in 20a9e565 — so the `Key` column carries the catalog at every site. 20a9e565's `period_defect` is the two defect clauses verbatim. Both callers want every consecutive pair of an ordered chain to carry, which is one caller-level universal over `demo`; 20a9e565 then takes a minimum over the survivors, which is tie-resolution after the negation and stays outside the operation.

~~The survey settled the interface at `demo`.~~ The surfacing solver's `answer` — the object left over by the demonstrated pair, read under that parse — presumed exactly three objects and one demonstration, and neither other caller has a leftover object: in both, the further object is one that demonstrated the rule.

Near, all ruled out: a candidate tested against the single object it then renders (3345333e's `contradicted`, with an inexact carry that an occluded cell upholds; 7b7f7511's `dup_mismatch`, self-consistency of one object under `Unanimous.clash`); one parse rather than a catalog, with the negation selecting which objects match (321b1fc6's `unmatched`) or which fit criterion holds as a `Choice` case (bbb1b8b6's `unfit`); a global covering condition in place of a cell-by-cell carry (50846271's `span`); a best match by count (2ccd9fef's `miss`/`fewest` — its split pick; its velocity site is a caller — and 1b60fb0c's `restored`); the uniqueness selectors, which stop at picking the object with no equal (38007db0, a87f7484, 15660dd6); a rule read off the input with no candidate tested against another (4c416de3, 39e1d7f9). Thirty-odd `Determine` comps hold defect relations of the same shape and are all excluded: there the rule is fixed by the train pairs.

Callers:

- 4c7dc4dd (`extend`, `span`, `reflect` — three parses of a panel, a `Rule` ADT as the keys)
- 351d6448 (`refuted` — candidate wave velocities, the parse repainting each animation frame)
- 20a9e565 (`period_defect` — candidate growth periods, the parse replaying each layer one period on)
- 2ccd9fef (candidate end velocities — read off the last step today; a chain carry over `demo` validates them throughout, as in 351d6448)
