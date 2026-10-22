# de1cd16c

## Concept
- The concept fits every train pair and the test pair (probe `probe.py`): the speck counts are train0 8:3 over 4:2, train1 2:4 over 8:2, train2 6:4 over 1:3, train3 4:2 over 8:1, test 2:5 over 8:3.
- The speck color is the one color with a cell whose four neighbors all differ from it. The regions are the other colors, one per color, and a region's specks are the speck cells in the bounding box of its fill cells.
- The concept is undefined where two regions tie at the most specks.
- No witness has verdict `other`, and no rule is approximated.

## Choice points
- `speck-color`: how the speck color is found
    - `concept`: the one color that has an isolated cell, a cell with no same-color 4-neighbor
    - `$RarestSpeck`: replaces `scattered-specks` with "the speck color is the input's rarest color", and is undefined where two colors tie for rarest. Fits every pair. Witness `tiny-region`: region 3 is 2×2, fewer cells than the 5 specks, so 3 is read as the speck color and color 4 as a region, which gives 4 where the concept gives 1. It breaks no scene claim. Plausibility `variant`, verdict `concept`. It breaks the invariant "every region has more cells than the input has specks".
- `region-unit`: what one region is
    - `concept`: every cell of one fill color, read as one region
    - `$ComponentRegion`: replaces `rectangular-regions` and `count-specks` with "each 4-connected component of one fill color is a region, its specks the speck cells in that component's bounding box, and the output is the color of the component with the most". It is undefined where components of two colors tie at the most. Fits every pair. Witness `split-region`: color 3 fills two separate rectangles with one speck each, and region 8 between them holds 3. That witness breaks `rectangular-regions` ("no two regions share a color"). The concept's box of color 3 spans the grid and gives 3, and the components give 8. Plausibility `borderline`, verdict `$ComponentRegion`. It breaks the invariant "each fill color forms one rectangle".
- `speck-owner`: which region a speck counts toward
    - `concept`: the region whose fill-cell bounding box contains the speck
    - `$NeighborOwner`: replaces `count-specks` with "a speck counts toward each fill color among its 4-neighbors". Fits every pair. Witness `edge-speck`: two specks sit on region 1's edge column, beside region 2. That witness breaks `scattered-specks` ("no speck touches a region border"). The concept gives 1 (3 against 2), and the branch gives 2 (4 against 3). Plausibility `variant`, verdict `concept`. It breaks the invariant "every 8-neighbor of a speck is its region's fill color".
- `score`: what ranks the regions
    - `concept`: the region's speck count
    - `$SpeckDensity`: replaces `count-specks` with "a region's score is its speck count over its cell count". Fails Fit at train2: region 1 has 3 specks in 56 cells, region 6 has 4 in 80, and the branch gives 1 where the pair gives 6.
    - `$RegionArea`: replaces `count-specks` with "a region's score is its fill-cell count". Fails Fit at train1: region 8 is the largest and gives 8 where the pair gives 2.
- `tie`: the output where regions tie at the most specks
    - `concept`: undefined, by `unique-most`
    - `$TieAll`: replaces `unique-most` and `output-most` with "the output holds one grid for each region tied at the most specks". Fits every pair. Witness `tied-most`: regions 2 and 8 hold 2 specks each. That witness breaks `unique-most`. The concept is undefined there, and the branch gives a grid of 2 and a grid of 8. Plausibility `borderline`, verdict `$TieAll`. It breaks the invariant "one region holds strictly more specks than every other region".
- `out_dim`: how the output extent is found
    - `concept`: stored, 1
    - `out_dim=ConstOutDim`: the extent derived by `ConstOutDim`, which reads `ex_out`. With `ex_out` empty, a single input gives it no value, so the branch is undefined on every input. Fails Fit at train0, and at every other pair.
- `speck-color` & `region-unit`, `speck-color` & `speck-owner`, `speck-color` & `score`, `speck-color` & `tie`, `speck-color` & `out_dim`, `region-unit` & `speck-owner`, `region-unit` & `score`, `region-unit` & `tie`, `region-unit` & `out_dim`, `speck-owner` & `score`, `speck-owner` & `tie`, `speck-owner` & `out_dim`, `score` & `tie`, `score` & `out_dim`, `tie` & `out_dim`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `extreme` taking fewest: the region with the fewest specks fails every pair, so the pairs fix `extreme` to most. That is a stored value, and no reading leaves it open.
- `out_dim=ConstOutDimAxis`: like `ConstOutDim`, it reads `ex_out`, gives no value on a single input, and is a reading of the same point that fails Fit at every pair.
- Counting every non-fill cell in a region's box in place of the speck cells: on a non-rectangular region, that count takes another region's fill cells as specks, which no reader of the concept does. On a rectangular region it equals the concept's count.
- Output the commonest input color (`DominantColor`): gives 8 at train1 where the pair gives 2, so it is the `$RegionArea` reading by cell count, and fails Fit the same way.

## Tickets filed
- none
