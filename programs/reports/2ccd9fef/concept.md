# 2ccd9fef

## Concept
- The input is a film strip of equal frames that show objects growing step by step, and the frame at the end of the strip is still blank; the output is that blank frame with the next step drawn in.

## Scene
- `panel-strip`: the input is a row or a column of equal panels laid end to end, and every panel shows one background pattern.
- `blank-end-panel`: the panel at one end of the strip shows only the background, and the sequence runs from the other end toward it.
- `filled-panels`: each panel other than the blank one shows objects drawn over the background, and there are at least two such panels.
- `object-colors`: object cells take only colors that the background pattern does not use.
- `steady-step`: from each filled panel to the next, each object changes by one same step:
    - its two ends along one axis each move a fixed number of cells, which can be zero;
    - between its ends, it stretches by repeating its periodic run of lines;
    - its extent across that axis does not change;
    - its colors change by one fixed permutation, which can be the identity.

## Rules
- `output-is-blank-panel`: the output is the blank panel, the size of one panel.
- `next-step`: each object of the last filled panel, advanced by one more step, is drawn in the output over the background.

## Parameters
- none

## Scene parameters
- none
