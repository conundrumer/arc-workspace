# b7249182

## Concept
- The concept case fits every train and test pair (`check_concept.py`, `probe_branches.py`). Each of its rules has a relational form, and it approximates no rule.
- The box is 5 cells across and 4 cells deep on every pair, for runs of 10, 12, 14 and 16 cells. So `bar-reach` and `box-depth` are constants, and the stems take up whatever length is left.
- No witness has verdict `other`.

## Choice points
- `background`
    - `concept`: `background` is stored as 0.
    - `background=DominantColor`: changes the stored `background` to the commonest color of the input. Its parameters are `bar-reach` and `box-depth`. It is undefined where colors tie for commonest, and where the concept is undefined at the derived background. It fits every pair. Witness `background=DominantColor` is a field of 3 with dots 2 and 8 on one column, 10 cells apart. It breaks `two-dots`, read with `background` 0. Plausibility `variant`, verdict `background=DominantColor`. The invariant it breaks is that every input's field is 0.
- `odd-span`
    - `concept`: `even-span`. A run of odd length has no halves, and the model is undefined there.
    - `$OddSpanGap`: changes `even-span` and `halves`. Each half is the floor of half the run, counted from its dot. On a run of odd length, the middle cell of the run and the box's middle line across it stay unpainted, so the two halves do not meet. Its parameters are `background`, `bar-reach` and `box-depth`. It is undefined where the concept is undefined for any reason other than run parity. It fits every pair. Witness `odd-span` has dots 2 and 8 on one column, with a run of 11 cells between them. It breaks `even-span`. Plausibility `borderline`, verdict `$OddSpanGap`. The invariant it breaks is that the run from dot to dot has an even length in every input.
- `dot-count`
    - `concept`: `two-dots`
    - `$EachPair`: changes `two-dots`. The cells that are not background come in pairs. Each pair is on one row or column, and no dot shares a row or column with a dot outside its pair. Each pair gets the concept's bracket. Its parameters are `background`, `bar-reach` and `box-depth`. It is undefined in these places:
        - where a dot shares its row and column with no other dot, or with more than one
        - where a pair breaks `even-span` or `long-span`
        - where the brackets of two pairs paint one cell in different colors

        It fits every pair. Witness `two-pairs` has dots 2 and 8 on one column and dots 4 and 1 on one row. It breaks `two-dots`. Plausibility `variant`, verdict `$EachPair`. The invariant it breaks is that every input holds exactly two cells that are not 0.
- `background` & `odd-span`, `background` & `dot-count`, `odd-span` & `dot-count`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `shared-line`: a reading for dots on no common row or column. None of the pairs draws anything between such dots, and no reading from the pairs gives an output there.
- `long-span`: a reading for halves shorter than `box-depth`. The pairs show no box larger than the run, so no output follows for it.
- A middle line shared by both halves on a run of odd length: no color for that line follows from the pairs, because each painted cell takes the color of the dot whose half holds it.
- `bar-reach` or `box-depth` derived from the input: no proposer in `programs/proposers.dl` gives these values. The box keeps one size over runs of 10 to 16 cells, so a derivation from the run length would give a different size on some pair.
- `background=SharedColor`, `background=RarestColor`: on one input, `SharedColor` gives every color of that input, the dot colors included. `RarestColor` gives the dot colors. At a dot color as background, every model is undefined, so both branches fail Fit on every pair.

## Tickets filed
- none
