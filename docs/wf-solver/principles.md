# Principles

A solver models an ARC task as an instance of a task family. The body encodes the family — structure shared by every task in it. Consts holds the task's coordinates within the family — the free data a sibling task would refill. Sibling tasks under family F are the other tasks in F.

Generalization happens at the family level. Bodies are the reusable inventory the corpus accumulates; Consts is the per-task residue. The goal is a model of ARC tasks usable for synthesis — recombining bodies over new Consts values yields new tasks — and potentially for training a solver.

Each principle guards the model claim against one failure:

- **Fidelity** — the body carries structure the task doesn't have.
- **Invariance** — the body carries data that belongs in Consts.
- **Coverage** — the solver commits to one family where the train pairs support several.

## Fidelity

The body is faithful to the concept of the task — the actual task, not an artifact of how the data or the medium encodes it.

**Relational form.** ARC concepts are relations between cells, regions, and properties; encode them as relations. Dictionaries and imperative loops carry ordering and indexing the concept doesn't have; ordered iteration belongs only to tasks with ordered structure. Arithmetic in a rule is usually a relational operation in disguise — a wraparound shift is a cycle walked (6d1d5c90), and mod is its numeric shadow. When arithmetic seems necessary, the lib wants a new primitive (see style doc).

**ARC values.** Work in the task's own values — colors, directions, axes, D4 elements. Projecting them into bools or ints adds structure (ordering, arithmetic) they don't have. Numbers are one indirection from the concept; arithmetic on them is a second.

**Zero is absence.** In spatial data, zero means no gap, no offset, no distance — the lack of structure. It is never task data and earns no Consts slot; a body may say `0` directly.

## Invariance

The task at hand is one member of a family symmetric under ARC's transformations — rotations, mirrorings, recolorings, re-anchorings. The body is the part that survives those variations; each variation becomes a Consts value the body parameterizes over. The failure mode: tying the body to the one member in front of you.

**Scope.** Invariance ranges over ARC's symmetry group — orientation, color, placement. It does not extend to the rule algebra: an OR fold is existence and an XOR fold is exact count — two concepts, two families, never one count-thresholded body awaiting a Consts value (dae9d2b5 vs 34b99a2b). Parameterizing past the task's own symmetry trades fidelity for a super-family the task doesn't claim.

**Color.** Colors have identity and nothing else. Structure over colors — an ordering, a mapping, a partition — is task data and lives in Consts. Comparing by enum ordinal or iterating C0..C9 in the body invents structure.

**Orientation.** A task may privilege a direction, axis, or transformation; absent that, no choice is privileged. Position's four edge distances remove the corner origin; Dir, Axis, DiagDir, and D4 make orientation choices values, so the mirrored sibling is a Consts edit, not a body restructure.

**Equivariance.** A lib primitive may read specific Position slots internally iff the choice washes out: `f(apply(D, P)) = apply(D, f(P))` for every D in D4. Equivariant primitives are safe to parameterize from Consts. A non-equivariant one — a `T mod period` intile mapping, observable on non-divisible extents — silently leaks an orientation into a body that believes it is symmetric. The remedy is an explicit anchor parameter, or an equivariant encoding: 332efdb3 models its period-2 pattern with `divide_by_size` K=1 G=1 in place of mod. The diagnostic is the equality itself: any (D, P) where it fails means non-equivariant.

## Coverage

A handful of train pairs underdetermines the family. Each model is a claim — this task is an instance of family F — and coverage is one model per plausible claim, carried as cases of `Choice` in one file. ARC training tasks are intended to teach core knowledge priors in pure form; coverage surfaces which prior the task could be teaching. A record-typed Choice crosses independent decision points (87ab05b8: three locate families × two fill-color claims).

**Data vs ops.** The main axis along which claims differ. Any relationship can flatten into Consts data — a table, claiming a lookup prior — or expose as composed primitives, claiming a compositional prior. 3b4c2228 renders its count both ways: `$Tally` composes marks down a diagonal; `$Lookup` selects a stored grid. Data-leaning models grow Consts and shrink the body; their siblings vary the table. Ops-leaning models put structure in the body; their siblings vary the parameters.

**Same model or different.** Two candidates are the same model iff both hold:

- same Consts shape — the free data a sibling would refill; derived or materialized helper relations don't count
- same outputs for every input under every Consts value of that shape

Different on either makes them different models; each earns a case. Same on both makes them alt impls of one model; a second impl adds nothing — same family, same prior, same generalization — so don't propose alt impls. Output divergence settles the question when it fires; Consts-shape divergence catches candidates that coincide on today's task but parameterize different families. One shared Consts slot across two claims asserts they are the same parameter. The test is whether some task both claims fit pulls the values apart: 87ab05b8 keeps `divisor`, `tile_dim`, `block_dim` separate, all [2,2] — a 6×6 sibling splits them into [2,2] and [3,3]. When no such task exists, the parameter is the same and shares one slot: d23f8c26's `axis` is read by its equidistance case and its divide case alike, and any task both fit pins them to the same value.

The criterion compares maps, not swept sets: a body that relabels its own coordinates — measuring from `opposite(D)` where another measures from `D` — sweeps the same tasks at different Consts values, so the checklist counts it as a different model. The relabeled twin adds no coverage; don't write one.

**Concept vs setup.** Cases are claims about the prior the task teaches. Setup is structure every candidate claim stands on: whichever selection rule 662c240a teaches, it reads the same stack of three tiles. Setup has variants of its own — the stack pins by tile count, by tile size, or by squareness with no datum, and the same-model test separates the three by Consts shape — but they invoke one segmentation prior and differ only in which datum pins it: coordinates within a prior, not rival priors. Together they earn one case, written in the corpus's settled shape (2dee498d, f25ffba3); coverage goes to the rival priors — a privileged reflection ($Shared) against symmetry-existence ($Asym). A same-model separation earns a case only when it separates priors. A layout new to the corpus has no settled shape; the solver introducing it settles it.

**Claims are evidence-gated.** Claims the data cannot distinguish all stay — that is what coverage is for (a passthrough interior vs a repainted one, 6f8cd79b). A claim the data barely instantiates doesn't earn a case: a mapping table wants multiple entries exercised (44f52bb0's groups both fire; a one-entry ring table over a plain border sits unexercised), and an identification rule dies when some pair defeats it (87ab05b8 train 0 defeats count-based marker identification — every noise color is a singleton). Data-leaning Consts must be refillable from the train pairs alone — the test pairs are held out. A test key absent from the train-exhibited entries defeats the table claim, and the correct output at that unseen key is evidence the prior is compositional (1fad071e: test count 3 over train's {2, 4} kills its lookup render; 3b4c2228's test counts stay inside train's set, so its table stands).

## Examples

- 44f52bb0 — alt models by Consts shape: `$Direct` (one sym set + two grids; binary classification family) vs `$GroupMatch` (group→grid table; multi-class family). Outputs coincide on every input; sibling families diverge. Its three unwritten `$Direct` bodies (orbit walk, group closure, pattern enumeration) share one Consts shape — alt impls, no cases.
- 34b99a2b / dae9d2b5 — one layout, different folds: `$Xor` (exact count) and `$Or` (existence), each in its concept's own form, beside a data-leaning `$Lookup` table.
- 3b4c2228 — data/ops on the render node; on the detect node, `$Object` (components) vs `$Placement` (occurrences) diverge on touching copies.
- 87ab05b8 — locate families coinciding on 4×4 and diverging on larger siblings: `$Div` (arrangement), `$Block` (tiling), `$Corner` (corner-seated block); fill color propagated vs fixed.
- 6f8cd79b / 1e81d6f9 — underdetermined content: what the border overwrites, what the erase spares.
- 662c240a — setup vs concept: three tile-stack pinnings, one segmentation prior, one case in the settled shape; coverage goes to $Shared vs $Asym.
