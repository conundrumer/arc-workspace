# Equivariance

How the engine keeps every program equivariant by construction, at no cost at run time. It rests on the obligations below.

## What it means for the engine

- Equivariance is the property that [Invariance](../../docs/handbook/principles.md#invariance) defines, over ARC's symmetry group Γ. The handbook lines it rests on are [Orientation](../../docs/handbook/principles.md#orientation), [Color](../../docs/handbook/principles.md#color), [determination](../../docs/handbook/principles.md#models-and-tasks), [Fidelity](../../docs/handbook/encoding.md#fidelity), [Numbers](../../docs/handbook/encoding.md#numbers) and [Equivariant lib relations](../../docs/handbook/encoding.md#equivariant-lib-relations).
- The engine needs the action of Γ on each column type. An element γ acts on a row column by column:

| Type | Action of γ |
| --- | --- |
| Color | γ's color permutation |
| Dir, DiagDir, Dir8 | the D4 action on directions, `apply_dir` and its kin |
| Axis, DiagAxis, Axis4 | the swap that the action on directions induces |
| Sense | a reflection reverses it, a rotation keeps it |
| D4, C4 | conjugation, d ↦ g d g⁻¹, where g is γ's D4 part |
| Sym | conjugation of the subgroup |
| Box, Position, Offset | `apply` |
| Ident | the bijection that γ induces on the content an Ident labels |
| number, Example, Unit | none |

- Example labels have one more symmetry: a reorder of the train pairs changes no stored value and no output, since a task file's order is an encoding, as Fidelity gives.

## Why composition keeps it

A program is equivariant when each of these conditions holds:

- Each relation that the program reads from outside its clauses is equivariant. The grids are, by definition. The parameters are, since γ acts on the assignment. Each lib relation and component is, by the obligations below.
- Each clause is made of joins, projections, unions, negations, and the tests `=` and `!=`. Each of these commutes with every bijection that acts on the columns one by one, so each is equivariant under the action above. `IF` and `ALL` compile to these, as [Joins](evaluator.md#joins) gives.
- An order test, `<`, `<=`, `>` or `>=`, stands only on a type that every γ fixes element by element and whose order is not an encoding. Of the column types, only `number` is such a type.
- The only constant is `0`, and every γ fixes it: the number zero, and the zero box, which `apply` maps to itself. A constant of any other task type, such as `DIR_T` or a color, is moved by some γ.
- An instance applies a component to relations of the program. A composition of equivariant functions is equivariant.
- A chosen relation has the set of models that its constraints give, and no model is preferred. So γ maps the models on a task onto the models on the transformed task, and the output set, one grid per model, moves with the task.
- The stage after the determination keeps every value at which the case solves every train pair. The hypothesis is equivariant, so the case solves T's train pairs at θ exactly when it solves γ·T's at γ·θ, and the kept values move with the task. Where a parameter keeps more than one value, the values are its open values under `(ONE)`, and an error without it. They are never a pick, as [`DET`](determination.md#det) gives.
- A pose label of a `RIGID_DET` meets the type rule of [The RIGID_DET frame](#the-rigid_det-frame).

So equivariance follows from the checker's rules and the lib's definitions, and no run checks it.

## The obligations

### The types refuse order, and programs hold no task-type literals

- **Rule.** The type check refuses `<`, `<=`, `>` and `>=` on every type but `number`, as [Checker](reader.md#checker) gives. The grammar admits `0` as the one constant, as [Negation and constraints](../../docs/arclog/arclog.md#negation-and-constraints) gives.
- **Enforced by:** the checker, in step 1 of the [build order](overview.md#build-order). The token mask runs the same checks.
- **Cost:** one test per constraint atom when the program is checked. Nothing at run time.
- **Corpus:** every order test of `gen/` is on `number`. No clause body holds a constant of a task type.
- **What the check needs:** the type of a label at a column of a component's type parameter. Some of the tests compare such labels, each bound to a number. The checker takes the type through the instance's binding of the parameter.

### Each lib element has no free choice, or its choice is a model

- **Rule.** Each lib element is defined as a function of the rows of its inputs. Where an element's operation has more than one answer, it exports every answer, or the answers are the models of a chosen relation. No definition breaks a tie by an order of encodings: term ids, reading order, Example order or color numbers.
- **Enforced by:** the admission test of [lib-spec.md](../../docs/lib-spec.md), which each new element passes, and the startup check of the orientation tables, as [Lib](evaluator.md#lib) gives. The tables hold no color, so their invariance under D4, with the action above, is their invariance under Γ.
- **Cost:** nothing at run time. A review at each admission.

### Each native implementation matches its definition

- **Rule.** Each native element gives the rows that its definition gives.
- **Enforced by:** the [lib comparison](verification.md#lib-comparison), on small generated inputs.
- **Cost:** the existing command, outside every run.
- **Where the oracle departs:** the Souffle lib makes the free choices of the next section. At those elements the comparison expects the difference, and reports it as a fault of the Souffle lib, as the Principles requirement of [Requirements](overview.md#requirements) gives.

## Free choices

A survey of the lib, `programs/lib/` and `programs/proposers.dl` against `gen/`, found each element whose definition or present implementation makes a free choice, or reads an order of encodings.

### Settled

| Element | Choice | A reader in `gen/` | Resolution |
| --- | --- | --- | --- |
| Ident values: `Quotient.class`, `Connectivity.component`, `Enclosure.enclosed` | the number of an id; Souffle takes the least term id | 009d5c81, 00dbd492 and 00dbd492 | An Ident is interned by the content it labels, as [Terms](reader.md#terms) gives, and only equality on it reaches an output. Equality is kept by every bijection. |
| Periods, inside | one translation per magnitude, toward the bottom-right corner | 017c7c7b | An engine device behind the interface. The outputs pair the cells both ways, so they do not show the corner. The native form need not copy it. |
| `CoverForcing`, `PlacementPruning`, `TiebreakResolutions` | term-id order and reading order, `constraints.dl:12`, `:187-214`, `:261` | none; `ONE` and `CHOOSE` replace them, as in 28a6681f and 4cd1b7b2 | Every model, as [Semantics](../../docs/arclog/constraints.md#semantics) gives. |
| Order under ties, `Unfold` under a score tie | none: tied members share a rank, `minimal` holds each of them, and the walk forks | `successor` in 00576224; `Unfold` in 3490cc26 | No choice. |
| `PairDims` coordinates, read by the proposers `Period`, the `Sep*` proposers and `TileD4` | rows and columns counted from the top and left edges, `proposers.dl:16-30` | 695367ec, 0520fde7 and 00576224 | The results do not depend on the edge: `Period` reads differences, the separator lines of an exact fit are symmetric, and a tile is a box. The arclog text holds no literal, so it enumerates the edge. |
| `PanelCombine` | `c1` is the top or left panel, `proposers.dl:432-455` | 0520fde7 | The proposer gives each panel's place as a Position in the arrangement's frame, as the records already hold it, such as `&combine_member` in 0520fde7.arcdata. |
| `TileD4`'s `swaps` | a literal set | 00576224 | The set is closed under conjugation, so every γ fixes it. |
| Division by side | the edge that the tiles start from, where the extent leaves a remainder | 06df4c85 | Division takes equal parts alone; the present functor refuses a remainder, `lib_functors.cpp:95`. |
| The order of the two attempts on a test input | which grid is the first | the Kaggle run | The score reads the attempts as a set, as [The output set](../../docs/arclog/constraints.md#the-output-set) gives. |

### Quotient's `representative`

`representative` holds one member per class ([lib-spec.md](../../docs/lib-spec.md#the-constructions), the Quotient row). Souffle picks the member of least term id. Where the class members are examples, that is the first example. These files read it:

| File | Use | Does the pick reach an output | Members per class on the train pairs |
| --- | --- | --- | --- |
| 0d3d703e | one order of a swapped color pair | no: `&mapping` reads both orders | 4 classes of 2 |
| 142ca369 | the representative marker of a `RIGID_DET` | through the `RIGID_DET` alone: the markers are copies up to D4 | 1 class of 7 |
| 150deff5 | the representative piece of each color | the same | 2 classes, of 6 and 8 |
| 21897d95 | the representative arrow of each center kind | the same | 2 classes, of at most 12 and 6 |
| 269e22fb | the representative train output | the same | 1 class of 5 |
| 3aa6fb7a | the representative piece | the same | 1 class of 5 |
| 3d588dc9 | the representative key, by one of its shed cells | the same | 1 class of 4 |
| 409aa875 | the representative of each class of congruent marks | the same, but the class tests the shape alone, so the apex and the aim are copies only under the claim | classes of at most 10 |
| 4522001f | the train pair whose pictures the program stores | yes: `&box_anchor` (`DiagDirDomain`) is determined in the picked pair's frame, and the two train inputs are a half turn apart | 1 class of 2 |
| 4c7dc4dd | a test that two cells share a class: two reads joined on the representative | no | 2 classes per marked panel, of 13 and 12 cells |
| 4c177718 | the representative arrow | through the `RIGID_DET` alone | 1 class of 4 |
| a2d730bd | the representative dot | the same | 1 class of at most 8 |
| b15fca0b | one order of the two endpoints, on each input | no: the shortest walk's inner cells are the same from each end | 1 class of 2 |
| b27ca6d3 | the representative footprint of each congruence class | no: the program compares the footprint under every D4 element | 1 class of 4 |

Quotient exports `class` alone. Each use as a representative is a `RIGID_DET` with an `instance` clause over the class, which [Form](../../docs/arclog/rigid.md#form) defines as the replacement of the pick, so an assembly whose instances disagree has no value. 0d3d703e and 4c7dc4dd read `class`, b15fca0b reads both orders, and 4522001f stores its pictures as an assembly over the train pairs, with the anchor as a part.

### The `RIGID_DET` frame

Where the instances admit a common reading, each of its D4 images is one too, and the choice among them is the frame, as [Semantics](../../docs/arclog/rigid.md#semantics) gives. The engine takes one instance's reading, as [Implementation](../../docs/engine/rigid.md#implementation) gives, and a type rule keeps every read from seeing that choice:

- A `:Pose` column has the type Pose of its assembly.
- A Pose label may stand at a `:Pose` column of the same assembly, at a column of a derived relation or of an instance's input, which then takes the type, in `=` and `!=`, and in `d4_elem`, whose column takes the type of its label, since every D4 element is a pose.
- The lib relation `pose_difference(a, b, d)` gives the D4 element that takes the placement at pose a onto the placement at pose b. It is the one way from a Pose to a D4 value, and Γ moves it by conjugation, as the action above gives.
- The checker refuses a Pose label at any other site. So `(d4_identity D)` and `(c4_elem D)` on a pose are type errors.
- The frame's own Idents, the `Ident` columns of a part or of the key that [The pose](../../docs/arclog/rigid.md#the-pose) gives as the assembly's own, are as unobservable as the pose, by the rule that section gives.

The rule is the rule of [The pose](../../docs/arclog/rigid.md#the-pose). It costs one type check per site, and nothing at run time. In `gen/`, every clause that reads a `RIGID_DET` passes the rule. 142ca369 and 269e22fb use `d4_elem` in a `RIGID_DET`. No clause reads `.pose`.

### Wallpaper's shift

An isometry of a periodic set is a D4 element and a coset of the period translations. The candidates hold each coset with a member that the frame admits on each axis, toward either edge, whatever the period, so a D4 element takes the candidates of a frame onto those of its image. `symmetry` holds each shift of the coset under which some cell of the frame lands in the frame, and `action` holds each image under those shifts that lands in the frame, as the Wallpaper row of [Detectors](../../docs/lib-spec.md#detectors) gives. A coset is a set, so no member is chosen. The cost is at most the count of period translations inside the frame, per candidate.

The Souffle form keeps the one member toward the bottom-right corner, `cells.dl:618-624`, which a reflection does not map onto the member it keeps. The lib comparison reports that difference as a fault of the Souffle lib. Three files of `gen/` read `action`, 0dfd9992, abbfd121 and c663677b, and none changes. No file reads `symmetry`.

### `same_line`'s margin

The Souffle form compares the margin of the one side toward the bottom-right corner, `box.dl:223`, and at a DiagAxis, the diagonal whose vertical part is `DIR_B`, `box.dl:224-226`. A reflection does not map that side onto itself. The native form compares the margin on either side, and the two agree on cells. The lib comparison reports a difference as a fault of the Souffle lib. 125 files of `gen/` read `same_line`: 070dd51e, 0becf7df, 0f63c0b9, 12422b43, 137f0df0, 140c817e, 16b78196, 178fcbfb, 195c6913, 1efba499, 21f83797, 221dfab4, 22425bda, 2281f1f4, 22eb0ac0, 23581191, 25c199f5, 2685904e, 291dc1e1, 29c11459, 2b01abd0, 2ccd9fef, 2dd70a9a, 2faf500b, 319f2597, 3345333e, 38007db0, 3979b1a8, 3bd67248, 3e6067c3, 40853293, 412b6263, 41e4d17e, 45bbe264, 4a21e3da, 4aab4007, 4c7dc4dd, 4cd1b7b2, 4f537728, 50aad11f, 5168d44c, 5207a7b5, 5289ad53, 52df9849, 53b68214, 53fb4810, 54d82841, 54dc2872, 55783887, 5a5a2103, 5ad8a7c0, 5daaa586, 62b74c02, 689c358e, 6a980be1, 6e453dd6, 7447852a, 770cc55f, 78e78cff, 79fb03f4, 7c66cb00, 7d7772cc, 7e4d4f7c, 7e576d6e, 80a900e0, 8403a5d5, 84ba50d3, 8731374e, 88207623, 88bcf3b4, 8a371977, 8b9c3697, 8e5c0c38, 8eb1be9a, 8fbca751, 917bccba, 9344f635, 94be5b80, 963f59bc, 9720b24f, 981add89, 985ae207, 98cf29f8, 992798f6, 9aec4887, 9b2a60aa, 9b30e358, 9b4c17c4, 9c1e755f, 9f27f097, 9f669b64, 9f8de559, a2d730bd, a2fd1cf0, a406ac07, a61f2674, a6f40cea, a78176bb, aa300dc3, aab50785, ac3e2b04, ad3b40cf, b0722778, b10624e5, b20f7c8b, b2bc3ffd, b527c5c6, b7f8a4d8, ba1aa698, bae5c565, bcb3040b, bdad9b1f, bf699163, bf89d739, c1990cce, c3f564a4, c64f1187, c803e39c, ca8f78db, cbded52d, d4469b4b, e633a9e5, e9afcf9a, f45f5ca7, and f5b8619d.

## Determinism

- A relation is a set of rows. Each clause and each lib element is a function from sets of rows to a set of rows. With no free choice, each relation is a function of the program, the parameters and the grids.
- So the thread count, the join order, the order in which the constraint module gives the models, and the order of the train pairs do not enter any row. No rule needs to sort.
- An Ident is the one value in which an encoding shows. Its number depends on the order of interning, and a writer numbers Idents by their contents, as [Terms](reader.md#terms) gives, so the text is the same from run to run.
- A writer gives a set in a fixed order of the encodings: the arcdata writer, the trace form's writer, and the two attempts on Kaggle. That order is the form of the file, and no relation reads it.

## Known gaps

| Gap | Where it shows |
| --- | --- |
| The action on a `RIGID_DET` part of type D4 or Sym: [Semantics](../../docs/arclog/rigid.md#semantics) leaves those types as they are, and Γ conjugates them | 4522001f and ad38a9d0 have `RIGID_DET` forms with a part of type D4 |
| A native proposer carries the second and third obligations, and no command compares a native proposer with its definition | each proposer that `engine/lib/registry.sexpr` marks `native`, as [Proposers](determination.md#proposers) gives which are native |
| A claim text that names an orientation constant, which the program does not read | b457fec5, "the DIR_T edge"; b6f77b65, "the DIAG_TL corner" |
