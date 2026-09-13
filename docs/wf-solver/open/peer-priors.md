# Peer priors: what separates two candidates that parse the task alike

Open question in `principles.md`, Coverage — Prior or setup, the Peer priors bullet, read with Subsumption — Refused input.

## The question

The rule gives a case to two candidates that parse the task alike only when they "separate priors", and no rule says when two candidates do. The rule came in as a bound on setup variants: tiles by count against tiles by size invoke one prior and share one case, and coverage goes to rival concepts. The approved corpus since grants cases at every kind of separation the Same model test makes, tiles by count against tiles by size included, in 662c240a, the rule's own citation.

## The text

> - **Peer priors.** The cases go to the peer priors. Two candidates that parse the task alike get a case only when they separate priors, regardless of their choice point.
>     - 662c240a
>
> - **Refused input.** A divergence at an input the hypothesis's premise excludes does not establish subsumption. A strict hypothesis and a tolerant peer that fold the same evidence differently are two families under Invariance scope, and each gets a case.

## Where the approved corpus stands

Cases granted, one parse between them:

- a measure: ac0a08a4 (`Cells | Colors`), 00dbd492 (`Size | Count`)
- a strength of one test: 05f2a901 (`Block | Touch | Extent`), 23581191 (`Color | Mark`), 9c56f360 (`Wall | Solid`), 42a50994 (`Ink | Self`)
- a rendering of the cells the model does not draw: 6f8cd79b, a406ac07 (`Passthrough | Repaint`)
- a parameterization of one layout: 662c240a (`Count | Size`), 8e5a5113 (`StepCount | StepSize`), 5d2a5c43 and its siblings (`Table | Count | Size`), 87ab05b8 (three ways to locate the region)
- a cut position: 9caf5b84 (`Keep | Drop`)

Cases refused: 0dfd9992 (repair from the translation lattice alone), 4c416de3 (a stricter demonstration test; a narrower color search), 928ad970 (the rectangle drawn under existing ink). No approved solver holds a case for the join that forms objects, the cardinal join against the corner join, although in about forty solvers that instantiate `Components` no pair holds a corner-only contact, so the other join fits every pair.

## Candidate rules

1. **Same model alone.** Two candidates that parse the task alike are peers when Same model separates them, and a peer gets a case unless Evidence or Subsumption removes it. Approved gains: 0dfd9992, 4c416de3, 928ad970, 150deff5 (`params.bg` at every uncovered cell against the input cell), and a join field in up to forty solvers where the other adjacency fits every pair. No approved losses.
2. **Setup encoding by precedent; parameterization and output rules as hypotheses.** Two encodings of one setup structure, over the same cells and with one parameterization, are one setup, and Setup priority picks the encoding. A difference in parameterization is a hypothesis, in the rules that find the setup as in the output rules. A difference in a rule that derives the output is a hypothesis: a measure, a strength, a rendering. Approved gains: 4c416de3, 928ad970, 150deff5, and 0dfd9992 if its peer sits in the output rules. Approved losses: 8e5c0c38 (`ByObject`: a connected piece against a color class over the same cells). No join fields.
3. **A keyword gate.** Two candidates separate priors when their claims differ in a Prior keyword of `keywords.md`. Approved losses: every pair listed above under a measure, a strength, a rendering, a cut, and 8e5a5113, 662c240a, 87ab05b8; no gains.

## Solvers

Drafts, with the case at stake:

- 20818e16 — rectangles rank by cell count; rank by perimeter and by extent along a stored axis were dropped as one prior. Rules 1 and 2 give `Count | Perimeter | Extent`; rule 3 keeps one case.
- 28e73c20 — `Passthrough | Repaint` kept on the shared data; nested rings, dropped as "where the spiral stops". Rules 1 and 2 add a drawing field; rule 3 keeps `Repaint` alone.
- 39e1d7f9 — six variants of `[sp: Span, st: Seat]`; dropped as one prior: the paint order of a copy over the ink it lands on, the seat cell's survival, the cardinal join against the corner join, which object is the motif. Rule 1 adds every field; rule 2 adds the paint order and the seat survival and leaves the join to precedent; rule 3 adds none.
- 4e7e0eb9 — `Ink = Whole | Any`: a halving line divides its section when it is drawn end to end, or when it carries one mark. Rule 1 keeps both; rule 2 keeps one, since the divider is a structure found two ways over the same cells; rule 3 keeps one.
- 67e490f4 — the exact congruence test kept; the into-reading (each square holds the plus, and the squares outvote the plus) dropped. Rules 1 and 2 add `Onto | Into`; rule 3 adds nothing.
- 54dc2872 — `Slide` kept beside `Translate` on the Exercised finding alone. Rules 1 and 2 keep it, as an output rule that reads the L's own heading; rule 3 decides by whether travel and placement are two keywords.
- 8ba14f53 — `Shape | Hue | Region`, three groupings of the same cells. Rule 1 keeps all three; rules 2 and 3 keep one. The draft citation under Exercised in `principles.md` follows this ruling.
- 239be575, 62ab2642 — `Orth | Diag` over one node set. Rule 1 keeps both; rules 2 and 3 keep one.
- 60a26a3e (a color-blind ring test), 8a371977 (the ring as the tiles beside a missing tile), 90f3ed37 (the full shape as the largest), 8b9c3697 (what stops the mover), 67a423a3 (a line as one color's cells in a row, with no bg guard), 689c358e (the side reading) — each dropped one branch under the gate. Rules 1 and 2 add it; rule 3 does not.

Approved solvers a rule would change: listed under each rule.

## Witnesses

20818e16, three rectangles; rank by cell count against rank by perimeter or by extent along H:

```
5 5 5 5 5 5 . . 2 2 2 . . .
5 5 5 5 5 5 . . 2 2 2 . . .
5 5 5 5 5 5 . . 2 2 2 . . .
. . . . . . . . . . . . . .
1 1 1 1 1 1 . . . . . . . .

by cell count          by perimeter, or by H extent
1 1 1 1 1 1            2 2 2 1 1 1
2 2 2 5 5 5            2 2 2 5 5 5
2 2 2 5 5 5            2 2 2 5 5 5
```

39e1d7f9 in its lattice reading, a mark touching the motif at a corner alone:

```
2 2 2 . . .    corner join: the mark joins the motif, the input repeats
2 1 2 . . .    cardinal join: the mark stays apart, the block stamps on it
2 2 2 . . .      2 2 2 2 2 .
. . . 1 . .      . . 2 1 2 .
                 . . 2 2 2 .
```
