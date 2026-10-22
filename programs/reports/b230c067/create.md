# b230c067

## Departures
- The cases `$FourAdjacent & $UniqueCount`, `$FourAdjacent & $UniqueBbox`, `$FourAdjacent & $UniqueCongruent`, `$FourAdjacent & $FewestCells` and `$FourAdjacent & $SmallestBbox`, with each object-cells reading, are not cases of the solver: each fails Fit at test0. Under 4-adjacency the odd object at test0 rows 1–4, cols 1–3 splits into a 3-cell piece and a 4-cell piece. The 4-cell piece shares its cell count, its bbox extent and its D4 class with pieces of the copies, and the fewest-cells and smallest-bbox readings pick the single cells (3,7) and (8,4), so each of these models turns test0 output (3,1), (4,1), (4,2), (4,3) to 1. The Analyze report gives `adjacency` & `odd-object` as the two changes applied together, and names no fit for each pair.
- `@derive TileCount` on `copy_count` is a branch the Analyze report does not have: `derive` reports that it fits. Its witness `copy_count=TileCount` uses the input of `three-copies`. On that input the derived counts include 3, so the blocks take copy_color and the bar odd_color, which is the concept's output. The stored `copy_count` 2 turns every object 2.
- The Analyze witness `$NonBackgroundObjects & background=DominantColor` has the id `background=DominantColor` in the witness file, the name the Witness file section gives the `@derive DominantColor` branch. The second witness that `derive` wrote under that id, train 0 with 0 and 3 swapped, was removed as a duplicate of the branch's witness.
- Witnesses `fewer-cells-larger-box` and `six-copies` are added (see Judgments).
- `recolored-copy-cell` stands under `$NonBackgroundObjects` with its `@relaxed` line, and also under `$ColoredShapes`: its verdict `$NonBackgroundObjects` makes it a witness of the concept case, and a witness of the concept case stands under the branch its verdict denotes.

## Judgments
- Keywords `objects match classify congruent count rank`: objects are components (`objects`). Copies pair off by shape (`match`). Each object maps to the copy or odd class, and that class sets its color (`classify`). `$UniqueCongruent` identifies shapes up to D4 (`congruent`). `$UniqueCount` and `$CopyCountClass` read counts (`count`). `$FewestCells`, `$SmallestBbox` and `$OutsideMajority` read an extremum (`rank`).
- Encoding: an object's shape is its cells cropped to its own bbox (`Bbox` and `crop`). Shapes compare with `KeyedSetCompare.equals`: over `Position` members for cell shapes, and over `[Position, Color]` members for `$ColoredShapes`. For congruence the observed key is `[object, D4]`, with the cells moved by `apply`. A bbox's extent is `axis_dim` of a cropped cell. A bbox's area is a `Tally` of the grid cells inside the box, so it counts cells and needs no product.
- `impl_choice` leaves out `$ColoredShapes` with `$UniqueCount`, `$UniqueBbox`, `$FewestCells` and `$SmallestBbox`. Those readings compare no shapes, so the Analyze report gives no shape-colors property with them.
- The hint "case section" on `object_cells_choice` is dismissed with `@ignore: case section`. That relation is the field's enumerator, and the template places enumerators before the markers.
- Deletions report: the `domain` rules of the three `Tally` instances were removed, because every key has a member. The `impl_choice` atoms in the `odd` clauses were removed, because `out` joins `impl_choice` and `obj` or the extremum atom grounds each clause. The rest were kept. The `colored` rules, the `!colored(K)` negations and the colored comparators act only where colors differ inside an object, which no pair has. `label` in `colored_cell` keeps out the cells of other objects that lie in the bbox. The `impl_choice` and enumerator rules list cases.
- Witness `fewer-cells-larger-box`, built to separate `$FewestCells` from `$SmallestBbox`: two solid 2x3 blocks and a 5-cell L in a 3x3 box. `ordinary`, verdict `concept`. It breaks no scene claim. The concept and `$FewestCells` turn the L 2, and `$SmallestBbox` turns the blocks 2.
- Witness `six-copies`, built to separate `$CopyCountClass & copy_count=TileCount` from `$UniqueShape`: six single cells and one domino on a 10x10 grid. `variant`, verdict `concept`, `@relaxed copies-and-one-odd`, the same judgment the Analyze report gives `three-copies`. The derived counts on a 10x10 grid leave out 6, so `$CopyCountClass` turns every object 2 under either value of `copy_count`.
- `@derive TileCount: variant concept`, `@relaxed copies-and-one-odd`, judged on its witness: the three-copies input is a variant with three copies, and the concept's output is the one the generator pairs with it.
- Not formed, by place: no place property separates the odd object from both copies in every pair (top-right in train0 and train1, left in train2), so every reading by place fails Fit at a train pair.
- Not formed, by color: every input has one object color, so no object has a color that no other object has. A unique-color reading turns every object copy_color and fails Fit at train0.
- Determine: the sweep gives one value for each parameter, and `determination-plan` lists no actions, so the solver has no Determine comp.

## Open
- none

## Lib
- Shape equality of objects up to translation: crop each object to its own bbox, then compare the cropped cell sets with `KeyedSetCompare.equals`. In this solver it is `shape_cell([K, Id], P_inner) :- obox.box([K, Id], B), label(K, P, Id), crop(P, B, P_inner).` fed to both inputs of `shapes = KeyedSetCompare<Object, Object, Position>`. The same form stands in `39a8645d` (`shape_cell` with `same_shape = KeyedSetCompare<Ident, Ident, Position>`). The grep for solvers that use `KeyedSetCompare`, `Bbox` and `crop` together also finds 009d5c81, 00dbd492, 0934a4d8, 11852cab, 14754a24, 15113be4, 15660dd6, 18419cfa, 18447a8d, 1fad071e, 21897d95, 228f6490, 2a5f8217, 2c181942, 2ccd9fef, 38007db0, 3b4c2228, 3d588dc9, 42f14c03, 44d8ac46, 4c177718, 4c5c2cf0, 4ff4c9da, 5dbc8537, 63613498, 776ffc46, 88a62173, 898e7135, 93b4f4b3, 97a05b5b, a09f6c25, a834deea, aab50785, ad38a9d0, aee291af, b20f7c8b and ff28f65a. Those sites were not each checked for this exact shape.
- Congruence up to D4: the same comparison with the observed key `[object, D4]` and the cells moved by `apply(D, P_inner, P_out)`. The grep for solvers that use `KeyedSetCompare` with `apply` finds 0934a4d8, 11852cab, 18419cfa, 21897d95, 2c181942, 4c5c2cf0, 898e7135, 97a05b5b, ad38a9d0 and b20f7c8b, not each checked.

## Fixes elsewhere
- none

## Tickets filed
- 10-275_task_b230c067_create.md
