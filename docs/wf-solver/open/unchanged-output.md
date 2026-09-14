# Unchanged output: an output equal to the input as a divergence

Open question in `principles.md`, Coverage — Subsumption, the Ill-formed divergence bullet.

## The question

Ill-formed divergence names two defects of an output, multiple values and not total. It says nothing about an input at which a hypothesis's rules fire nowhere and a passthrough rule returns the input. That output reads either as total and single-valued, so a valid divergence, or as an absence of transformation, so no divergence and no prior of its own.

## The text

> - **Ill-formed divergence.** When every divergence of a hypothesis from a peer is ill-formed (the output has multiple values or is not total), the hypothesis never fits a task that the peer misses, at any assignment of its parameterization. The peer subsumes it, and it gets no case. The subsumption is refuted when there is a divergence where the hypothesis is total and the peer is ill-formed.
>     + (∀θ ∃θ′ ∀x. M(θ, x)↓ ⇒ M(θ, x) = M′(θ′, x)) ⇒ fam(M) ⊆ fam(M′)

## Candidate text

A sub-bullet above Refused input:

> - **Unchanged output.** An output equal to the input is total and single-valued, so a divergence at it does not establish subsumption. The test is the output, not whether the hypothesis's rules fire. Where the hypothesis derives no output at all, the output is not total, and that divergence is ill-formed.
>     - 41e4d17e
>     - f25ffba3

The formal line already reads `M(θ, x)↓` over the output. Eight tasks under `data/tasks/` hold a train pair whose output equals its input, so the identity is a fit ARC does pose.

The refuse reading stands beside it:

> A hypothesis whose rules fire nowhere transforms nothing, and it names no prior of its own. A divergence where its output equals the input does not refute subsumption.

Under it such a peer is removed at Subsumption, before Evidence and Peer priors are reached, and the cases 41e4d17e `Hole` and f25ffba3 `Stamp` lose their only divergence.

## Where the approved corpus stands

41e4d17e keeps `Object` beside `Hole` on a solid block, where `Hole` finds no closed region and returns the input while `Object` casts. 4c416de3 and 928ad970 each met a peer that returns the input, treated the divergence as real, and dropped the peer under an earlier rule. The approved subsumption findings (0dfd9992, 981571dc, 30f42897, 2c181942, 99b1bc43, e345f17b, fafffa47, 3b4c2228, 0934a4d8) all turn on an empty or multi-valued output.

## Solvers

- 363442ee (draft) — the stored tile-extent peer returns the input at a key of another extent; that was the ground for giving it no case. Under the candidate text the divergence is valid, and whether the case is owed is `correspondence-frame.md`'s question.
- 48f8583b (draft) — its stored stamp-color peer fits no assignment, so it is no peer; the empty output its report shows is not a subsumption ground.
- 9841fdad (draft) — the create pass left the contact-anchoring peer undecided on this question, and the refine pass admitted it as `$Extreme()`.
- 992798f6 (draft) — the question is recorded as the part its pass left unsettled.

## Witnesses

41e4d17e, a solid 3×3 block of 6 in a 7×7 field of 8; `Hole` returns the input and `Object` casts a full cross:

```
input            $Hole            $Object
8 8 8 8 8 8 8    8 8 8 8 8 8 8    8 8 8 6 8 8 8
8 8 8 8 8 8 8    8 8 8 8 8 8 8    8 8 8 6 8 8 8
8 8 6 6 6 8 8    8 8 6 6 6 8 8    8 8 6 6 6 8 8
8 8 6 6 6 8 8    8 8 6 6 6 8 8    6 6 6 6 6 6 6
8 8 6 6 6 8 8    8 8 6 6 6 8 8    8 8 6 6 6 8 8
8 8 8 8 8 8 8    8 8 8 8 8 8 8    8 8 8 6 8 8 8
8 8 8 8 8 8 8    8 8 8 8 8 8 8    8 8 8 6 8 8 8
```

f25ffba3, a top-bottom symmetric 5×4 input; `$Stamp` returns it and `$TileSize` gives a 10×4 grid:

```
input      $Stamp     $TileSize
2 4 3 9    2 4 3 9    2 4 3 9
. . 3 9    . . 3 9    . . 3 9
. . . 9    . . . 9    . . . 9
. . 3 9    . . 3 9    . . 3 9
2 4 3 9    2 4 3 9    2 4 3 9
                      2 4 3 9
                      . . 3 9
                      . . . 9
                      . . 3 9
                      2 4 3 9
```
