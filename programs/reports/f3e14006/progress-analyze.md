# Progress: analyze f3e14006

## interference: train1 output
- Target: `data/tasks/f3e14006.json` train1 output, row 4, cols 3 and 5.
- The pair's output holds `8` (the bar line's base) at train1 output (4,3), (4,5); these are cross-thread cells in a hole row, which every other hole row of every pair, row 6 and row 8 of train1 included, gives the cross line's base `5`. No interpretation found reproduces the two cells.
- The concept gives the pair, rows 2–8, cols 2–6:

    ```
    2 5 2 5 2
    8 8 8 8 8
    9 5 9 5 9
    8 8 8 8 8
    9 5 9 5 9
    8 8 8 8 8
    9 5 9 5 9
    ```

- Judged by that output, the concept fits train1, as do `$AnchorAcrossBarLine`, `$AnchorAlongNearCross` and `background=DominantColor`, each of which gives that output on train1 (`work/task/f3e14006/probe.py`); judged by the pair's own output, every case fails Fit at train1. No witness is drawn from train1, so no verdict rests on it.
- Cost: one check run and the time to search for a reading of the two cells. The output is still wrong in the task file.
