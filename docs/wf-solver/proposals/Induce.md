# `Induce<Key, Obj, Val>` — the parse a pair of objects demonstrates

The parse, out of a keyed catalog of them, that carries one object's cells exactly onto a second object's. The program states each candidate parse as `render` under its own key; the objects themselves say which parse the input teaches, so nothing about the rule is stored. This is the `induce` prior at object scale, with the demonstration inside one input. Which pairs must carry, and what the surviving parse is then applied to, are the caller's: a caller wanting one demonstrating pair reads `demo` directly, and one wanting a chain to carry throughout negates `demo` over its own successor relation.

Code form:

```
.comp Induce<Key, Obj, Val> {
    // Each object's cells, total over its frame.
    .decl cell(o: Obj, p: Position, v: Val)  // input

    // The rule's parse of an object, per key.
    .decl render(key: Key, o: Obj, p: Position, v: Val)  // input

    // The rule does not carry o onto o2.
    .decl defect(key: Key, o: Obj, o2: Obj)
    defect(Ky, O, O2) :-
        render(Ky, O, P, V),                          // a cell the rule reads
        cell(O2, P, V2), V != V2.                     // against the second object
    defect(Ky, O, O2) :-
        render(Ky, O, _, _),
        cell(O2, P, _), !render(Ky, O, P, _).         // a cell the rule leaves unread

    // The pair the input demonstrates the rule on.
    .decl demo(key: Key, o: Obj, o2: Obj)
    demo(Ky, O, O2) :-
        render(Ky, O, _, _), cell(O, _, _), cell(O2, _, _), O != O2,
        !defect(Ky, O, O2).
}
```

The catalog's keys may be distinct rules or one rule's parameters; both are the same operation. A catalog of distinct rules names them with a solver-defined ADT filling `Key`:

```
.type Rule = Extend {} | Span {} | Reflect {}
```

That ADT is this comp's own override of the style rule that an ADT lives inside `Choice` alone: the branch names carry the catalog members' identity the way `Choice` case names carry peer models', and a record of fabricated numbers would be an enum in disguise.

Not: a rule the train pairs fix, which is stored as a parameter; `Choice` cases, which are peer models of one task rather than a catalog the input picks from; a best-match or closest parse, where `defect` is counted instead of negated; matching by resemblance (`Occurrences`, `D4Map`); `KeyedSetCompare.equals`, which states the exact match of one set against one pattern and stops there; a candidate tested against the one object it then renders, with no second object.

Match: a site that tests several candidate parses of the same objects against each other and keeps the parse no cell of some object pair contradicts. In the shape above the test is a defect relation negated inside a pair rule; a site may instead compare through `KeyedSetCompare.equals` over `[p, v]` members, or carry the pair as a record. Grep: `!defect` or a negated per-cell mismatch between two object-keyed valued cell relations; `.equals(` beside an object inequality; the solvers whose concept line holds `induce`.

Survey: 2026-09-03 15:39

Result: two callers beside the surfacing solver, both keying the catalog by a parameter rather than by distinct rules — a Shift in 351d6448, a period number in 20a9e565 — so the `Key` column carries the catalog at every site. 20a9e565's `period_defect` is the two defect clauses verbatim. Both callers want every consecutive pair of an ordered chain to carry, which is one caller-level universal over `demo`; 20a9e565 then takes a minimum over the survivors, which is tie-resolution after the negation and stays outside the operation.

The survey settled the interface at `demo`. The surfacing solver's `answer` — the object left over by the demonstrated pair, read under that parse — presumed exactly three objects and one demonstration, and neither other caller has a leftover object: in both, the further object is one that demonstrated the rule.

Near, all ruled out: a candidate tested against the single object it then renders (3345333e's `contradicted`, with an inexact carry that an occluded cell upholds; 7b7f7511's `dup_mismatch`, self-consistency of one object under `Unanimous.clash`); one parse rather than a catalog, with the negation selecting which objects match (321b1fc6's `unmatched`) or which fit criterion holds as a `Choice` case (bbb1b8b6's `unfit`); a global covering condition in place of a cell-by-cell carry (50846271's `span`); a best match by count (2ccd9fef's `miss`/`fewest` — its split pick; its velocity site is a caller — and 1b60fb0c's `restored`); the uniqueness selectors, which stop at picking the object with no equal (38007db0, a87f7484, 15660dd6); a rule read off the input with no candidate tested against another (4c416de3, 39e1d7f9). Thirty-odd `Determine` comps hold defect relations of the same shape and are all excluded: there the rule is fixed by the train pairs.

Callers:

- 4c7dc4dd (`extend`, `span`, `reflect` — three parses of a panel, a `Rule` ADT as the keys)
- 351d6448 (`refuted` — candidate wave velocities, the parse repainting each animation frame)
- 20a9e565 (`period_defect` — candidate growth periods, the parse replaying each layer one period on)
- 2ccd9fef (candidate end velocities — read off the last step today; a chain carry over `demo` validates them throughout, as in 351d6448)
