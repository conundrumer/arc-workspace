# incidents — session 7e4d4f7c

## 2026-05-03 — ring_spiral named without shape (ca8de6ea)

**What happened:** In the docstring for `ca8de6ea`, I wrote "Lift
candidate: ring-spiral primitive that handles N-ring traversal mappings.
Pending more samples." I had not worked out the primitive's signature
or what operation it would actually capture. The structural observation
(input cells form concentric rings; CW traversal maps to CW traversal of
output) was real, but "ring_spiral primitive" was an invented name to
fill the lift-candidate slot, not a worked-out abstraction.

**What should have happened:** The structural observation should have
been left as the observation. No primitive name, no "pending more
samples" gesture. If I can't state the primitive's signature and the
trigger condition for lifting it, there isn't a candidate yet — there's
just a structural pattern I noticed.

**Likely cause:** The convention "flag lift candidates in Notes" got
performed rather than served. The slot was there, so I filled it. The
discipline that's missing: distinguishing structural-observation-worth-
recording from primitive-candidate-worth-naming, and only doing the
latter when shape and trigger are concrete.

## 2026-05-03 — corner_view used where edge_view fit (f25ffba3)

**What happened:** The rule extracts the bottom half of the input
(edge-anchored, full width). I used `corner_view(grid, DiagDir.BL,
h, w)` because that's the lifted primitive that exists. I noticed that
BL and BR gave content-equivalent results (because `w_extract == w_input`,
the horizontal anchor did no work) and noted this in the docstring as a
"choice doesn't matter; sibling task with column-narrower data would
force it." I treated the equivalence as a tiebreak detail.

**What should have happened:** The BL/BR equivalence was a signal that
`corner_view`'s interface is over-specified for this rule — the rule
picks one edge (BOTTOM), not a corner. The right primitive would be
an edge analog: `edge_view(cells, dir, n) -> Cells` (keep cells within
distance n of edge dir; recompute opposite distance against new bound).
The solver should have been marked `Status: placeholder` with
`edge_view` named as the candidate (it has a worked-out signature, so it
qualifies, unlike ring_spiral). The body would still call corner_view
as a stopgap, but the disposition would be honest about the
primitive-shape mismatch.

**Likely cause:** I treated "available primitive" as the question and
"does it produce correct output" as the test. The actual test is
whether the primitive's interface matches the rule's degrees of freedom.
I also missed the structural-signal-vs-curiosity distinction: parameters
that don't affect output are a tell, not a tiebreak.
