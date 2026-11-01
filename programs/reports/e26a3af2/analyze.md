# e26a3af2

## Concept
- Fits every pair: on each input exactly one axis has a majority color in every line (columns in train0 and train1, rows in train2 and test0), and painting each line of that axis its commonest color gives the output.
- The rule as the generator applies it: the input is solid stripes along one axis, with noise written over scattered cells, and the output is the stripes before the noise. A task in which noise ties with or outnumbers a stripe's color in a line is invalid, so the concept's majority test and line mode give that recovery on every input the generator produces.
- The concept is undefined on the witnesses `heavy-noise-line` (no axis has a majority in every line) and `wide-stripe` (both axes have one). Its verdict is `$AxisFewestChanges` on both witnesses.

## Choice points
- `repair-unit`
    - `concept`: each line along the stripe axis is painted whole (`line-axis`, `line-mode`)
        - `stripe-axis`
            - `concept`: the axis on which every line has a color that holds more than half of its cells, and undefined where neither axis or both axes qualify (`line-axis`)
            - `$AxisPlurality`: replaces `line-axis` with the axis on which every line has one commonest color with no tie. Undefined where neither axis or both axes qualify. Fits every pair, because each pair's other axis has a line with a tied commonest color. Fails Subsumption: where it is defined, the other axis has a tied line, so `$AxisFewestChanges` takes the same axis and gives the same output.
                - witness `heavy-noise-line`: row 1 holds its stripe color 1 in 4 of 10 cells, the commonest there, and every column of 1, 2, 3 has a tie. The branch takes rows, and the concept is undefined.
                    - breaks `sparse-noise`
                    - plausibility `variant`, verdict `$AxisFewestChanges` (the same output as `$AxisPlurality`)
                    - invariant broken: in each input, a stripe's color holds at least 0.6 of each line along the stripe
            - `$AxisFewestChanges`: replaces `line-axis` with the axis whose per-line painting changes the fewest cells, among the axes on which every line has one commonest color with no tie. Undefined where no axis qualifies or two axes tie on the count. Fits every pair.
                - witness `wide-stripe`: a column stripe of 4 covers 8 of 10 columns, so every row and every column has a majority color. The branch takes columns (3 cells change, where rows change 18). The concept and `$AxisPlurality` are undefined.
                    - breaks no scene claim
                    - plausibility `variant`, verdict `$AxisFewestChanges`
                    - invariant broken: each stripe covers less than half of the lines across the stripes (the largest is 6 of 14 in train1, and 6 of 15 in train2)
            - `$AxisStored`: replaces `line-axis` with one stored axis for every input. Fails Fit: at columns it fails train2, and at rows it fails train0.
    - `$LocalMajority`: replaces `line-axis` and `line-mode`, and no stripe axis exists: each cell takes the commonest color among its neighbors (4- or 8-adjacent, with or without the cell itself). Undefined at a tie. Fails Fit at train0: each neighborhood choice ties at some cell there, and with a tie keeping the cell's own color, 1 cell differs from the output.

## Open parameters
- none

## Not formed
- painting each stripe, a maximal run of adjacent lines with one commonest color, with the stripe's commonest color: equivalent to `line-mode`, because each line of the run has that color as its commonest color, so the run's commonest color is the same color.
- reading a line's color at one fixed cell of the line: a noise cell can stand at any cell. At row 0, train1 col 7 holds 1 in the stripe of 8.
- reading the axis by how many adjacent lines share their commonest color: it scores the same per-line colors that `$AxisFewestChanges` scores, and no solver header, lib component or proposer gives it.

## Tickets filed
- none
