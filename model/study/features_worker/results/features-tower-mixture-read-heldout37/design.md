# Tower mixture read: design

## Question
On the 37 held tasks, at the 1,429 steps of the seed-0 walk, this read measures the bits per form that a mode-first mixture saves against the proposal. The mixture first draws the mode from a fit of P(EXTEND | facts known before the step). Under EXTEND it draws gold's outcome from the tower model. Otherwise it draws from the plain proposal.

## Inputs
All inputs are records of the tower read. They are read only.

- `TW` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-heldout37-ramp22`. Its design is `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-read-design/design.md`. The outcome Y, the pattern, the tower facts, the models and the weights have the meaning that design gives them.
- `TW/walks/corpus.jsonl`: the corpus walks, 989 stems, seeds 0 to 3. These are the only fit rows.
- `TW/walks/held.jsonl`: the held walks. The read uses the 37, seed 0, for the bits, and all 16 seeds for the mode model's log loss.
- `TW/held/<task>.jsonl`: per step, `p_kind, n, h_joint, h_shape` for the proposal's rate.
- `TW/fit.json`: the shape list, the fit row count (84,724) and the alpha of each model and factor.
- `TW/tw_lib.py`: imported by path for the facts, the columns, the backoff chains, `Backoff` and `bootstrap_tasks`.

No engine, no draws, no walk is run.

## The mixture
At step t, with gold's outcome Y and gold's mode in the walk:

p_mix(Y) = π · p_tower(Y | EXTEND) + (1 − π) · p_prop(Y)

- `p_prop(Y)` = `p_kind · (h_joint + .5) / (n + 1)`, as in Table 1 of `TW/results.md`.
- `π` = P(EXTEND | facts before the step), from the mode model below.
- `p_tower(Y | EXTEND)` is the tower model's joint over (shape, pattern), restricted to the patterns whose `mode6` is EXTEND (36 of the 216) and renormalised:
  - p_tower(Y | EXTEND) = P(shape | x) · P(pattern | kind, I, x) / Z, where Z = Σ over shapes s of P(s | x) · P(EXTEND patterns | kind(s), I(s), x).
  - The `<unseen>` shape has no kind. Z sums over the seen shapes and divides by their mass. So the unseen shape gets the mean EXTEND share of the seen shapes.
- If gold's mode is not EXTEND, then gold's pattern is not an EXTEND pattern. Then p_tower(Y | EXTEND) = 0 and p_mix = (1 − π) · p_prop(Y).

Why the restriction, and not a model fit only on EXTEND steps: gold's mode is the `mode6` field of gold's pattern, so "the tower model under EXTEND" is the fitted model's own conditional on that field. The restriction gives that conditional exactly from the fit that gave +1.53 on EXTEND chain steps. It needs no new fit or alpha, and it puts no mass on outcomes that the EXTEND branch can't make.

The tower model of the verdict is M2A. M0, M1, M2B, M2M and M3 are given beside it as context.

The tower models are fit again on the 84,724 corpus rows with the alphas of `TW/fit.json`, because `TW` keeps the bits of gold's outcome only and Z needs the other outcomes. The refit must give gold's bits of `TW/tower/` to within .001 at every step. Else the script stops.

## The mode model
- Target: gold's mode at the step is EXTEND (1) or not (0).
- Facts: the 11 tower facts of `TW` (`n_present, n_open, ident_open, maxdepth, h_kind, h_ident, h_nreads, h_depth, prev, m_band, chain_roots`). They read S as a DAG, the kinds, `holds` and the walk so far. They do not read gold's mode at the step, the ready set R, gold's kind at the step, text order or binder marks.
- Model: a `Backoff` table on the target, along this chain of cells, finest first:
  - all 11 facts
  - (prev, m_band, chain_roots, h_kind, h_ident, h_nreads, n_open, ident_open)
  - (prev, h_kind, h_nreads, n_open)
  - (prev)
  - ()
- At m = 0 (step 0, an empty chain) EXTEND can't occur, so π = 0 there.
- Alpha from {0.5, 2, 8, 32, 128} by the 5 folds of `TW` over corpus stems. Then one fit on all corpus rows.
- Fit rows: the 84,724 corpus rows of the tower fit. The script asserts that no fit stem is in `eval-tasks.txt`, the ramp or the 37.
- Report: CV log loss on the corpus. Held log loss on the 1,429 steps and on all 16 seeds of the 37. As a reference, the log loss of a constant π (the corpus EXTEND share over steps t ≥ 1, and 0 at t = 0). Calibration on the 1,429 steps in bins of π of width .1: steps, mean π, EXTEND share.

## The oracle
π = 1 where gold's mode is EXTEND, else 0. So the oracle's bits are the restricted tower bits at EXTEND steps and the proposal's bits elsewhere. This is π from a perfect mode model. It is not the best mixture at each step: at an EXTEND step where p_prop > p_tower(Y | EXTEND), a π below 1 does better.

## Read
Weights and intervals are those of Table 1 of `TW/results.md`: weight = (steps in the task's stratum) / (done steps in it), with the stratum (place, f's mode class); a weighted mean; the 2.5% and 97.5% points of 2,000 bootstrap draws over tasks, seed 0.

- **Table 1**: rows proposal, the mixture with M2A, the oracle with M2A, and both again for the other tower models. Columns: bits mean, saving against the proposal with its interval, the same over steps with `h_joint ≥ 1`.
- **Table 2, by gold's mode class**: EXTEND, BACKTRACK, JUMP. Steps, proposal bits, mean π, saving of the mixture and of the oracle (M2A), with intervals.
- **Table 3, the mode model**: CV log loss, held log loss on the 1,429 and on all seeds, the constant reference, and the calibration bins.
- **Data check**: steps used, steps left out, steps with an unseen gold shape, the sums of the shape factor of each model and of the pattern factor of M2A over all 216 patterns (each must be 1 within 1e-6), the largest difference of the refit from `TW/tower/`.

## Verdict
The mixture saves where the M2A mixture's interval is above 0. If it isn't, the verdict is one line, and this line of work stops.

## Files
The record folder `R2` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-tower-mixture-read-heldout37`.

| File | Does |
|---|---|
| `mx_read.py` | Fits, scores and writes `R2/steps.jsonl` (one line per task, with its steps), then `R2/results.md` and `R2/tables.json`. A rerun skips the fit and the scoring when `steps.jsonl` has all 37 tasks with the same fit signature |
| `mx_env.sh` | `mx_env.sh SCRIPT ARGS`: runs the script on the kit's Python with `PYTHONDONTWRITEBYTECODE=1` through `/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 --need soon` |

## Cost
The fits and the scoring are numpy over 84,724 corpus rows and 1,429 held steps, with 36 EXTEND patterns and 23 shapes a step. One process, under 30 s, under 1 GB.

Command: `timeout 30 bash R2/mx_env.sh mx_read.py`.

## Limits
- The read measures the draw distribution of `Sampler.clause` and of the tower models at gold's step in the round-0 walk, not the search's order. Neither side pays the walk's own choice bits.
- The proposal's bits are a lower bound at steps with `h_joint = 0`, so the saving there is a lower bound.
- The proposal part of the mixture is the plain proposal, which also puts mass on EXTEND outcomes. The proposal's draws are of gold's kind only, so its mass on non-EXTEND outcomes over all kinds is not known, and the proposal can't be restricted to them from these records.
