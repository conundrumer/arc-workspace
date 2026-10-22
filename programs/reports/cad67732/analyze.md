# cad67732

## Concept
- The concept fits every pair at both open values of `anchor-edge`. The probe `work/task/cad67732/probe.py` gives each train output, and on the test it gives one grid, which is the test output.
- The concept reads the band's diagonal in `diagonal-band` as the diagonal whose two corner cells are not `background`, and the period in `least-period` as the least positive shift along that diagonal under which the input agrees with itself where both cells lie in the grid.
- Every claim has a relational form, and the concept case has no witness with verdict `other`.

## Choice points
- `band diagonal`: how the program finds the diagonal the band runs along
    - `concept`: the diagonal whose two corner cells are not `background`, in `diagonal-band`; undefined where both diagonals or neither have that
    - `$LeastPeriodDiagonal`: replaces the band-diagonal reading in `diagonal-band` with the diagonal whose least period (`least-period` read on each diagonal) is smaller; no added parameters; undefined where the two diagonals' least periods tie. It fits every pair (main 3 against anti 4 at train0, main 2 against anti 3 at train1, anti 2 against main 4 at train2, anti 2 against main 6 at test0).
        - Witness `short-anti-shift`: a one-cell band 1 2 3 4 1 2 down the main diagonal of a 6x6 input. The anti-diagonal shift of 3 agrees there, because its overlap holds no band cell, and the branch continues the input along the anti-diagonal. It stands at the stored assignment. Plausibility `variant`: it breaks the invariant of the inputs that each input shows at least two whole periods of the band (6/3, 5/2, 8/2, 10/2). Verdict `concept`.
    - `$StoredDiagonal`: stores the diagonal in place of the band-diagonal reading in `diagonal-band`, parameter `diagonal` (a `DiagAxis`). It fails Fit: the stored main diagonal fails train2, and the stored anti-diagonal fails train0.
- `period`: where the period comes from
    - `concept`: derived per input by `least-period`
    - `$StoredPeriod`: replaces `least-period` with a stored period, parameter `period`. It fails Fit: train0 needs a multiple of 3 that reaches every band cell of the 12x12 output from a 6x6 input, train1 needs a multiple of 2 no larger than 4, and no value is both, so train1 fails at 6, the least value that fits train0.
- `anchor`: the output corner where the input sits
    - `concept`: the end of the band's diagonal on the `anchor-edge` edge, in `anchored-input`
    - `$StoredCorner`: replaces `anchored-input` with a stored corner, parameter `corner` (a `DiagDir`). It is undefined where the stored corner is not on the band's diagonal. It fails Fit: a stored top-left corner fails train2 (anti-diagonal band), and a stored corner on the anti-diagonal fails train0.
- `background`: where the background color comes from
    - `concept`: stored, `background` = 0
    - `background=DominantColor`: derives `background` as the commonest color of the input; undefined where no single color is commonest. It fits every pair (0 is the commonest color of each input).
        - Witness `background=DominantColor`: a band of 3 and 4 down the main diagonal of a 6x6 field of 1 with no 0. It stands at the stored assignment. It breaks the scene claim `diagonal-band` (a grid of `background` 0). The concept finds colored corners on both diagonals and is undefined, `$LeastPeriodDiagonal` fills the cells it does not reach with 0, and the branch fills them with 1. Plausibility `variant`: a color-permuted variant task has this background. Verdict `background=DominantColor`.
    - `background=SharedColor`: derives `background` as each color of the input, read on that input alone. It fails Fit at train0, where the derivation gives 0, 1, 2, 3 and 4, and the model gives five grids.
- `scale`: where the scale comes from
    - `concept`: stored, `scale` = 2
    - `scale=ScaleRatio`: derives `scale` from output and input extents. It fails Fit at train0: on an input alone, with `ex_out` empty, the derivation gives no value, and the model is undefined.
- `band diagonal` & `period`, `band diagonal` & `anchor`, `band diagonal` & `background`, `band diagonal` & `scale`, `period` & `anchor`, `period` & `background`, `period` & `scale`, `anchor` & `background`, `anchor` & `scale`, `background` & `scale`: the two branches' changes applied together

## Open parameters
- `anchor-edge`: `T`, `L`

## Not formed
- An anchor stored as a corner for each diagonal (a `DiagAxis` to `DiagDir` table, the corner on that diagonal): its four assignments agree with the four values of `anchor-edge`, so its model is equivalent to the concept's.
- An anchor derived from the end where the band starts a whole period: in each pair, both ends of the band are cut by the frame in the periodic pattern (for example, train1 (-1,-1) and (4,5)), so no relational reading separates the two ends.
- A copy of the whole input placed again at the far corner along the diagonal (a translation by the input's extent): it fails train0, output (5,6) = 1, and train1, output (5,6) = 0.
- An overlay of input copies at each multiple of the period: on an input that agrees with itself under that shift, every copy gives one color to each cell, so it gives the concept's output on every input where the concept is defined, and where the concept is undefined it is undefined too.
- A period taken as a shift larger than the least one under which the input agrees: no source proposes it. The `Period` proposer and the solvers 017c7c7b, 53b68214 and 963e52fc take the least shift.
- The `Period` proposer: it reads shifts along a row or a column, and the band repeats under no such shift that a period reading would take.
- An output extent derived as the input extent plus a constant (`DimDiff`): the differences are 6, 5 and 8, so no constant fits.
- The other color proposers on `background` (`RarestColor`, `OutNewColor`, `VanishedColor` and the others): none gives 0 on each input, so each fails Fit at train0.

## Tickets filed
- 10-581_task_cad67732_analyze.md
