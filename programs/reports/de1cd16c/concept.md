# de1cd16c

## Concept
- The grid is cut into solid-colored rectangular regions, and single cells of one speck color are scattered over them; the answer is a one-cell grid of the color of the region that holds the most specks.

## Scene
- `rectangular-regions`: the grid is tiled by axis-aligned rectangles, each filled with its own background color, and no two regions share a color.
- `scattered-specks`: cells of one speck color, which no region has as its fill, sit isolated inside the regions; no speck touches another speck or a region border.
- `unique-most`: one region holds strictly more specks than every other region.

## Rules
- `count-specks`: each region's speck count is the number of speck cells inside the bounding box of that region's fill cells.
- `output-most`: the output is an `out_dim`×`out_dim` grid filled with the fill color of the region with the most specks.

## Parameters
- `extreme`: most
    - which end of the speck-count order picks the region
- `out_dim`: 1
    - the output's extent on each axis

## Scene parameters
- none
