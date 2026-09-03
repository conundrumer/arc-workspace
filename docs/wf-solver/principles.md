# Principles

A solver models an ARC task as an instance of a task family. The body encodes the family: the structure shared by every task in it. Consts holds the task's position within the family: the free data that a sibling task would refill.

Generalization happens at the family level. Bodies accumulate across the corpus as reusable inventory; Consts data stays specific to each task. The goal is a model of ARC tasks usable for synthesis, where recombining bodies over new Consts values yields new tasks.

## Fidelity

The body is faithful to the concept of the task: the actual task, not an artifact of how the data or the medium encodes it.

**Relational form.** ARC concepts are relations between cells, regions, and properties; encode them as relations. Arithmetic in a rule usually stands in for a relational operation: a wraparound shift is a walk along a cycle. When arithmetic seems necessary, add a lib primitive instead (see style doc).

**ARC values.** Work in the task's own values: colors, directions, axes, D4 elements. Projecting them into bools or ints adds structure (ordering, arithmetic) that they do not have.

**Indirection.** Data enters in the form its consumer reads, keyed by objects already in play. The test: when a rule's only function is to convert one representation of a thing into another, one of the two representations is unjustified. Examples: renaming keys into a second vocabulary (a 2×2 tile position as its corner name); routing a flat correspondence through intermediate coordinates; storing an order as successor edges, which closure must expand before a comparison can read it. Conversion is justified when the two sides differ in content, as with a sparse set and its ranking (`Ordinal`).

**Derived vs stored.** A value the pairs exhibit directly is task data: store it in Consts. A body derivation instead claims that the value depends on its source, and the claim needs a witness: some pair varies the source and the value follows. A value that is the same in every pair has no witness, and a derivation that reproduces it makes a claim the data does not support (4522001f stores its 9×9 canvas; N·N of the 3×3 input would reproduce it). An unwitnessed derivation stands only as a case beside the data case, never in its place (3b4c2228's count render); setup has no case to carry one. A frame built as a correspondence over input cells (007bbfb7) derives no number; the pairs witness the correspondence cell by cell.

**Zero is absence.** In spatial data, the number 0 means no gap, no offset, no distance: the lack of structure. It is never task data; a body may write `0` directly.

## Invariance

The task at hand is one member of a family symmetric under ARC's transformations: rotations, mirrorings, recolorings, re-anchorings. The body is the part that stays the same across those variations; each variation becomes a Consts value the body parameterizes over. The failure mode is a body tied to the one member at hand.

**Scope.** Invariance ranges over ARC's symmetry group: orientation, color, placement. It does not extend to the rule algebra. An OR fold is existence and an XOR fold is exact count — two concepts and two families, not one count-thresholded body with the threshold in Consts (dae9d2b5 vs 34b99a2b).

**Color.** Colors have identity and nothing else. Structure over colors — an ordering, a mapping, a partition — is task data and lives in Consts. Comparing by enum ordinal or iterating C0..C9 in the body adds structure the task does not have.

**Orientation.** A task may privilege a direction, axis, or transformation; without that, no choice is privileged. Position's four edge distances remove the corner origin. Dir, Axis, DiagDir, and D4 make orientation choices values, so a mirrored sibling needs a Consts edit, not a body restructure.

**Closure.** A Consts slot can carry structure: a membership set whose rows are exactly a structural class — every cardinal, a D4 orbit — with no payload that varies across them. No sibling fills a proper subset. The test is which members fire. Every member fires: the class is structural; the body enumerates it (`dir_elem`, `diag_dir_elem`) and Consts keys the datum by class (0ca9ddb6 stores `arm_paint` and `diag_paint`, one color per kind). One member fires and another must not: a slot holds the member. A task firing a peer class (cardinals against diagonals) is another body, not a refill (1f876c06, dbc1a6ce). When the values vary per row (d364b489's per-direction arm colors), the rows are data and the class is just the domain. Closure settles encoding, not coverage: it removes no case. A membership set some sibling refills is task data even when this task's fill coincides with a structural class (14754a24's plus footprint is the anchor plus every cardinal step; a T-completing sibling refills it, so its `shape` case stands beside the structural one).

**Underdetermined choices.** A body choice every fill passes is not task data: a slot for it is unwitnessed, and a literal hides it. The body enumerates its class and derives `out` per member, so the output is defined where the members agree (28a6681f runs both lateral pour orders).

**Equivariance.** A lib primitive may read specific Position slots internally iff the choice is unobservable: `f(apply(D, P)) = apply(D, f(P))` for every D in D4. Equivariant primitives are safe to parameterize from Consts. A non-equivariant primitive, such as a `T mod period` intile mapping (observable on non-divisible extents), adds a hidden orientation to a body that is otherwise symmetric. The remedy is an explicit anchor parameter, or an equivariant encoding: 332efdb3 models its period-2 pattern with `divide_by_size` K=1 G=1 in place of mod.

## Coverage

A few train pairs underdetermine the family. Each model is a claim that the task is an instance of family F; coverage is one model per plausible claim, carried as cases of `Choice` in one file. ARC training tasks are intended to teach core knowledge priors in pure form; coverage surfaces which prior the task could be teaching. A record-typed Choice crosses independent decision points (87ab05b8: three locate families × two fill-color claims).

**Data vs ops.** The main axis along which claims differ. Any relationship can be flattened into Consts data (a table, claiming a lookup prior) or written as composed primitives (claiming a compositional prior). 3b4c2228 renders its count both ways: `$Tally` composes marks down a diagonal; `$Lookup` selects a stored grid. Data-leaning siblings vary the table; ops-leaning siblings vary the parameters.

**Same model or different.** Two candidates are the same model iff both hold:

- same Consts shape — the free data a sibling would refill; derived or materialized helper relations do not count
- same outputs for every input under every Consts value of that shape

Candidates that differ on either are different models, and each gets a case. Candidates that match on both are alt impls of one model; do not propose them. Consts-shape divergence catches candidates that coincide on the current task but parameterize different families: 44f52bb0's `$Direct` (one sym set plus two grids) and `$GroupMatch` (a group→grid table) agree on every input, and their sibling families diverge. One shared Consts slot across two claims asserts that they are the same parameter. The test is whether some task that fits both claims pulls the values apart: 87ab05b8 keeps `divisor`, `tile_dim`, `block_dim` separate, all 2, because a 6×6 sibling splits them into 2 and 3. When no such task exists, the parameter is the same and shares one slot: d23f8c26's `axis` is read by its equidistance case and its divide case alike, and any task that fits both pins them to the same value.

A shared slot also requires a shared form: both claims read the datum in the same vocabulary. When the consumers differ, each claim stores the datum in its consumer's form, in a per-case slot; a shared slot that a case must convert fails the Indirection test. 2013d3e2 stores the output's location per case: $Half's `out_tile` is the tile position its divide produces; $Window's `corner` is the DiagDir that `corner_anchor` reads.

The criterion compares maps, not swept task sets. A body that relabels its own coordinates — measuring from `opposite(D)` where another measures from `D` — sweeps the same tasks at different Consts values, so the checklist counts it as a different model. The relabeled twin adds no coverage; do not write one.

Divergence must also be valid to count. When every divergence of a claim from a sibling is ill-formed — the output multivalued or short of total — the claim never fits a task the sibling misses, at any fill of its Consts shape; the sibling subsumes it, and it gets no case (99fa7670's line fill: an unblocked ray diverges from the stepwise flow only by claiming two colors on one cell). Partiality alone is not subsumption: a model that fails on some inputs but validly diverges on others is still a rival. An ops claim whose inputs a co-chosen decision pins to stored data computes a function of Consts; its tabulation is a fill of the data rival, so it gets no case (21897d95: the bracket sweep stands only under structural identification).

**Concept vs setup.** Cases are claims about the prior the task teaches. Setup is structure that every candidate claim stands on: whichever selection rule 662c240a teaches, it reads the same stack of three tiles. Setup has variants of its own. That stack pins by tile count, by tile size, or by squareness with no datum, and the same-model test separates the three by Consts shape; but all three invoke one segmentation prior and differ only in which datum pins it. Together they get one case: the pin whose facts the body already reads (1190bc91), written in the corpus's settled shape (2dee498d, f25ffba3). Coverage goes to the rival priors: a privileged reflection ($Shared) against symmetry-existence ($Asym). A same-model separation gets a case only when it separates priors, wherever the node sits. A variant that stands on different input structure is a different reading and gets a case; a variant that finds the same structure another way is a pin (17b80ad2's mark edge — c.dir against the edge the marks sit on — parameterizes the transformation and gets cases). The settled shape ranks below fidelity and reuse; a solver that introduces or improves a shape settles it.

**Claims are evidence-gated.** A rival that reads the task differently gets a case. A rival whose added machinery no pair exercises gets no case. A claim with no relational form gets no case: when its encoding rests on arithmetic and the lib addition protocol closes the primitive, the claim goes with it (`proposals/MinHops.md`). A mapping table needs multiple entries exercised (44f52bb0's groups both fire; a one-entry ring table over a plain border sits unexercised). An identification rule is out when some pair contradicts it (87ab05b8 train 0 contradicts count-based marker identification: every noise color is a singleton). Data-leaning Consts must be refillable from the train pairs and test inputs; the test outputs are held out. A test key absent from the train-exhibited entries rules out the table claim, and the correct output at that unseen key is evidence that the prior is compositional (1fad071e: test count 3 over train's {2, 4} rules out its lookup render; 3b4c2228's test counts stay inside train's set, so its table stands).
