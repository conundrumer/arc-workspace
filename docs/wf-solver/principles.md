# Principles

A solver models an ARC task as an instance of a task family. The body encodes the family: the structure shared by every task in it. Consts holds the task's position within the family: the free data that a sibling task would refill. Sibling tasks under family F are the other tasks in F.

Generalization happens at the family level. Bodies accumulate across the corpus as reusable inventory; Consts data stays specific to each task. The goal is a model of ARC tasks usable for synthesis, where recombining bodies over new Consts values yields new tasks, and potentially for training a solver.

Each principle guards the model claim against one failure:

- **Fidelity** — the body carries structure the task does not have.
- **Invariance** — the body carries data that belongs in Consts.
- **Coverage** — the solver commits to one family where the train pairs support several.

## Fidelity

The body is faithful to the concept of the task: the actual task, not an artifact of how the data or the medium encodes it.

**Relational form.** ARC concepts are relations between cells, regions, and properties; encode them as relations. Dictionaries and imperative loops add ordering and indexing that the concept does not have; ordered iteration fits only tasks with ordered structure. Arithmetic in a rule usually stands in for a relational operation: a wraparound shift is a walk along a cycle (6d1d5c90), and mod is a numeric encoding of that walk. When arithmetic seems necessary, add a lib primitive instead (see style doc).

**ARC values.** Work in the task's own values: colors, directions, axes, D4 elements. Projecting them into bools or ints adds structure (ordering, arithmetic) that they do not have. Numbers are one indirection from the concept; arithmetic on them is a second.

**Indirection.** Data enters in the form its consumer reads, keyed by objects already in play. A layer that only re-encodes content is structure the task does not claim. Examples: renaming keys into a second vocabulary (a 2×2 tile position as its corner name); routing a flat correspondence through intermediate coordinates; storing an order as successor edges, which closure must expand before a comparison can read it. Conversion is justified when the two sides differ in content, as with a sparse set and its ranking (`Ordinal`); it is not justified when they differ only in encoding. The test: when a rule's only function is to convert one representation of a thing into another, one of the two representations is unjustified. Direct forms: a68b268e keys precedence by the tile positions its divide produces; e633a9e5 stores its correspondence flat, cell to cell.

**Zero is absence.** In spatial data, the number 0 means no gap, no offset, no distance: the lack of structure. It is never task data and needs no Consts slot; a body may write `0` directly.

## Invariance

The task at hand is one member of a family symmetric under ARC's transformations: rotations, mirrorings, recolorings, re-anchorings. The body is the part that stays the same across those variations; each variation becomes a Consts value the body parameterizes over. The failure mode is a body tied to the one member at hand.

**Scope.** Invariance ranges over ARC's symmetry group: orientation, color, placement. It does not extend to the rule algebra. An OR fold is existence and an XOR fold is exact count — two concepts and two families, not one count-thresholded body with the threshold in Consts (dae9d2b5 vs 34b99a2b). Parameterizing past the task's own symmetry trades fidelity for a super-family the task does not claim.

**Color.** Colors have identity and nothing else. Structure over colors — an ordering, a mapping, a partition — is task data and lives in Consts. Comparing by enum ordinal or iterating C0..C9 in the body adds structure the task does not have.

**Orientation.** A task may privilege a direction, axis, or transformation; without that, no choice is privileged. Position's four edge distances remove the corner origin. Dir, Axis, DiagDir, and D4 make orientation choices values, so a mirrored sibling needs a Consts edit, not a body restructure.

**Equivariance.** A lib primitive may read specific Position slots internally iff the choice is unobservable: `f(apply(D, P)) = apply(D, f(P))` for every D in D4. Equivariant primitives are safe to parameterize from Consts. A non-equivariant primitive, such as a `T mod period` intile mapping (observable on non-divisible extents), adds a hidden orientation to a body that is otherwise symmetric. The remedy is an explicit anchor parameter, or an equivariant encoding: 332efdb3 models its period-2 pattern with `divide_by_size` K=1 G=1 in place of mod. The equality is also the diagnostic: any (D, P) where it fails shows non-equivariance.

## Coverage

A few train pairs underdetermine the family. Each model is a claim that the task is an instance of family F; coverage is one model per plausible claim, carried as cases of `Choice` in one file. ARC training tasks are intended to teach core knowledge priors in pure form; coverage surfaces which prior the task could be teaching. A record-typed Choice crosses independent decision points (87ab05b8: three locate families × two fill-color claims).

**Data vs ops.** The main axis along which claims differ. Any relationship can be flattened into Consts data (a table, claiming a lookup prior) or written as composed primitives (claiming a compositional prior). 3b4c2228 renders its count both ways: `$Tally` composes marks down a diagonal; `$Lookup` selects a stored grid. Data-leaning models grow Consts and shrink the body, and their siblings vary the table. Ops-leaning models put structure in the body, and their siblings vary the parameters.

**Same model or different.** Two candidates are the same model iff both hold:

- same Consts shape — the free data a sibling would refill; derived or materialized helper relations do not count
- same outputs for every input under every Consts value of that shape

Candidates that differ on either are different models, and each gets a case. Candidates that match on both are alt impls of one model. A second impl adds nothing — same family, same prior, same generalization — so do not propose alt impls. Output divergence settles the question when it occurs; Consts-shape divergence catches candidates that coincide on the current task but parameterize different families. One shared Consts slot across two claims asserts that they are the same parameter. The test is whether some task that fits both claims pulls the values apart: 87ab05b8 keeps `divisor`, `tile_dim`, `block_dim` separate, all 2, because a 6×6 sibling splits them into 2 and 3. When no such task exists, the parameter is the same and shares one slot: d23f8c26's `axis` is read by its equidistance case and its divide case alike, and any task that fits both pins them to the same value.

The criterion compares maps, not swept task sets. A body that relabels its own coordinates — measuring from `opposite(D)` where another measures from `D` — sweeps the same tasks at different Consts values, so the checklist counts it as a different model. The relabeled twin adds no coverage; do not write one.

Divergence must also be valid to count. When every divergence of a claim from a sibling is ill-formed — multivalued or empty — the claim never fits a task the sibling misses; the sibling subsumes it, and it gets no case (99fa7670's line fill: an unblocked ray diverges from the stepwise flow only by claiming two colors on one cell). Partiality alone is not subsumption: a model that fails on some inputs but validly diverges on others is still a rival.

**Concept vs setup.** Cases are claims about the prior the task teaches. Setup is structure that every candidate claim stands on: whichever selection rule 662c240a teaches, it reads the same stack of three tiles. Setup has variants of its own. 662c240a's stack pins by tile count, by tile size, or by squareness with no datum, and the same-model test separates the three by Consts shape; but all three invoke one segmentation prior and differ only in which datum pins it — coordinates within a prior, not rival priors. Together they get one case, written in the corpus's settled shape (2dee498d, f25ffba3). Coverage goes to the rival priors: a privileged reflection ($Shared) against symmetry-existence ($Asym). A same-model separation gets a case only when it separates priors. The boundary runs along consumption: variants whose output every rival claim reads identically are setup; a node that parameterizes the transformation itself splits data vs ops and gets cases (17b80ad2's mark edge — c.dir against the edge the marks sit on). A layout new to the corpus has no settled shape; the solver that introduces it settles it.

**Claims are evidence-gated.** Claims the data cannot distinguish all stay; that is what coverage is for (a passthrough interior vs a repainted one, 6f8cd79b). A claim the data barely instantiates gets no case. A mapping table needs multiple entries exercised (44f52bb0's groups both fire; a one-entry ring table over a plain border sits unexercised). An identification rule is out when some pair contradicts it (87ab05b8 train 0 contradicts count-based marker identification: every noise color is a singleton). Data-leaning Consts must be refillable from the train pairs alone; the test pairs are held out. A test key absent from the train-exhibited entries rules out the table claim, and the correct output at that unseen key is evidence that the prior is compositional (1fad071e: test count 3 over train's {2, 4} rules out its lookup render; 3b4c2228's test counts stay inside train's set, so its table stands).

## Examples

- 44f52bb0 — alt models by Consts shape: `$Direct` (one sym set + two grids; binary classification family) vs `$GroupMatch` (group→grid table; multi-class family). Outputs coincide on every input; sibling families diverge. Its three unwritten `$Direct` bodies (orbit walk, group closure, pattern enumeration) share one Consts shape — alt impls, no cases.
- 34b99a2b / dae9d2b5 — one layout, different folds: `$Xor` (exact count) and `$Or` (existence), each in its concept's own form, beside a data-leaning `$Lookup` table.
- 3b4c2228 — data/ops on the render node; on the detect node, `$Object` (components) vs `$Placement` (occurrences) diverge on touching copies.
- 87ab05b8 — locate families coinciding on 4×4 and diverging on larger siblings: `$Div` (arrangement), `$Block` (tiling), `$Corner` (corner-seated block); fill color propagated vs fixed.
- 6f8cd79b / 1e81d6f9 — underdetermined content: what the border overwrites, what the erase spares.
- 662c240a — setup vs concept: three tile-stack pinnings, one segmentation prior, one case in the settled shape; coverage goes to $Shared vs $Asym.
