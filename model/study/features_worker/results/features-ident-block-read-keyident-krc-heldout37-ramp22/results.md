# Ident block read, held-out 37 and ramp 22


Design: `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-ident-block-read-design/design.md`.

## Verdict

- The 37 (the verdict): **B, compounding over chain depth is the block**. A False, B True, C False.
    - A1 fails: weighted share under 0.03, weighted median L 0.92
    - A2 holds: plain share under 0.00, median L 0.69
    - A3 fails: median L at link 1 -0.42, link 2 0.78
    - A4 holds: proposal rise vs gold rise (RULE, INIT): 4.89 vs 11.56; 1.35 vs 3.29
    - B1 holds: weighted share under 0.03, weighted median L 0.92
    - B2 holds: slope -0.06, median L at link 5+ 0.92
    - C fails: median L at link 1 -0.42, link 2 0.78, slope -0.06
- The ramp (a second, weak read: 41 forms; relR4_o has the ramp in its train rows): **mixed**. A False, B False, C False.
    - A1 fails: weighted share under 0.05, weighted median L 1.17
    - A2 holds: plain share under 0.00, median L 0.75
    - A3 fails: median L at link 1 0.66, link 2 3.51
    - A4 holds: proposal rise vs gold rise (RULE, INIT): 4.57 vs 11.56; 1.38 vs 3.29
    - B1 fails: weighted share under 0.05, weighted median L 1.17
    - B2 holds: slope -0.17, median L at link 5+ 1.21
    - C fails: median L at link 1 0.66, link 2 3.51, slope -0.17
    - shapes that hold the `under` forms (weighted count, share of all Ident-only forms): INIT|1|key-ident 2.0 (5%)

## Data check
- corpus stems listed 989, replayed 989, left 0, with a replay error 0 (21181 forms listed, 21181 rows)
- corpus forms per kind: DET 3476, INIT 3172, OTHER 17, RIGID_DET 13, RULE 14503
- corpus C1 cells: 24, with under 40 forms: 4 (holding 91 forms); shapes seen V=22
- held rows 711, task lines 59, provisional-gold rows 0
- rows by (set, pass, role): ('37', 1, 'ident') 289, ('37', 1, 'plain') 110, ('37', 2, 'ident') 206, ('ramp', 1, 'ident') 41, ('ramp', 1, 'plain') 65
- 37: pinned Ident-only forms 495, done 495, tasks with rows 37 of 37
- ramp: pinned Ident-only forms 41, done 41, tasks with rows 22 of 22
- duplicate (task, form) rows: 0

## Table 1, by shape: The 37 held-out tasks

| shape | forms (done, total) | median p_gold | median p_prop | mean L | median L | mean L_kind | under (resolved) | unresolved | under, weighted to all forms | noise-floor under |
|---|---|---|---|---|---|---|---|---|---|---|
| INIT/1/key-ident | 41 / 41 | 0.0798 | 0.0349 | 1.90 | 0.95 | -0.70 | 11 | 2 | 11.0 (27%) | 0.0 |
| INIT/2/key-ident | 5 / 5 | 0.0086 | 0.0029 | 1.45 | 1.01 | -1.05 | 0 | 3 | 0.0 (0%) | 0.0 |
| INIT/1/key-plain | 12 / 12 | 0.0041 | 0.0064 | 0.20 | -0.63 | -1.10 | 0 | 4 | 0.0 (0%) | 0.0 |
| INIT/1/nokey | 28 / 28 | 0.0239 | 0.0229 | -0.85 | -0.42 | -1.01 | 0 | 0 | 0.0 (0%) | 0.0 |
| INIT/2/nokey | 3 / 3 | 0.0057 | 0.0047 | 0.32 | 0.99 | -1.38 | 0 | 1 | 0.0 (0%) | 0.0 |
| RULE/1/- | 316 / 316 | 0.5587 | 0.2671 | 1.07 | 0.99 | 0.81 | 1 | 5 | 1.0 (0%) | 0.0 |
| RULE/2/- | 61 / 61 | 0.1235 | 0.1301 | 0.30 | -0.08 | 0.90 | 2 | 3 | 2.0 (3%) | 0.0 |
| RULE/3+/- | 23 / 23 | 0.0144 | 0.0890 | -2.16 | -2.63 | 0.96 | 0 | 1 | 0.0 (0%) | 0.0 |
| DET/1/- | 5 / 5 | 0.0839 | 0.0704 | -0.72 | -0.14 | -2.14 | 0 | 0 | 0.0 (0%) | 0.0 |
| INIT/3+/nokey | 1 / 1 | 0.0003 | 0.0006 | -0.88 | -0.88 | -1.69 | 0 | 1 | 0.0 (0%) | 0.0 |
| all Ident-only forms | 495 / 495 | 0.5587 | 0.2123 | 0.74 | 0.92 | 0.49 | 14 | 20 | 14.0 (3%) | 0.0 |
| plain control | 110 / 934 | 0.6833 | 0.3630 | 0.26 | 0.69 | 0.31 | 0 | 0 | 0.0 (0%) | 0.0 |

## Table 1, by shape: The 22 ramp tasks

| shape | forms (done, total) | median p_gold | median p_prop | mean L | median L | mean L_kind | under (resolved) | unresolved | under, weighted to all forms | noise-floor under |
|---|---|---|---|---|---|---|---|---|---|---|
| INIT/1/key-ident | 7 / 7 | 0.3819 | 0.0301 | 3.26 | 3.67 | 0.34 | 2 | 3 | 2.0 (29%) | 0.0 |
| INIT/2/key-ident | 1 / 1 | 0.0060 | 0.0138 | -1.21 | -1.21 | -0.91 | 0 | 0 | 0.0 (0%) | 0.0 |
| INIT/1/key-plain | 4 / 4 | 0.0197 | 0.0038 | 1.65 | 1.75 | -0.37 | 0 | 2 | 0.0 (0%) | 0.0 |
| INIT/1/nokey | 11 / 11 | 0.0341 | 0.0321 | -0.25 | -0.41 | -0.62 | 0 | 1 | 0.0 (0%) | 0.0 |
| RULE/1/- | 16 / 16 | 0.5851 | 0.2465 | 1.21 | 1.21 | 0.64 | 0 | 0 | 0.0 (0%) | 0.0 |
| DET/1/- | 2 / 2 | 0.0512 | 0.0481 | 0.09 | 0.09 | -1.63 | 0 | 0 | 0.0 (0%) | 0.0 |
| all Ident-only forms | 41 / 41 | 0.3635 | 0.0481 | 1.10 | 1.17 | 0.00 | 2 | 6 | 2.0 (5%) | 0.0 |
| plain control | 65 / 302 | 0.6983 | 0.4452 | 0.62 | 0.75 | 0.63 | 0 | 0 | 0.0 (0%) | 0.0 |

## Table 2, by link: Ident-only forms, the 37

| link bin | forms | median L | mean L | share under | median L, INIT keyed | median L, RULE |
|---|---|---|---|---|---|---|
| 1 | 31 | -0.42 | -0.43 | 0% | -0.63 | - |
| 2 | 57 | 0.78 | 1.52 | 19% | 5.04 | 0.64 |
| 3-4 | 92 | 1.04 | 1.16 | 2% | 0.98 | 1.05 |
| 5+ | 315 | 0.92 | 0.60 | 0% | 0.16 | 0.92 |

OLS slope of L on link (capped at 8), unweighted: -0.06 bits a link, 95% interval from 1,000 bootstrap draws over tasks [-0.14, 0.03].

## Table 2, by link: Ident-only forms, the ramp

| link bin | forms | median L | mean L | share under | median L, INIT keyed | median L, RULE |
|---|---|---|---|---|---|---|
| 1 | 10 | 0.66 | 0.84 | 0% | 2.74 | - |
| 2 | 9 | 3.51 | 2.52 | 22% | 3.67 | 0.87 |
| 3-4 | 16 | 0.96 | 0.55 | 0% | 0.09 | 1.37 |
| 5+ | 6 | 1.21 | 0.85 | 0% | - | 1.21 |

OLS slope of L on link (capped at 8), unweighted: -0.17 bits a link, 95% interval from 1,000 bootstrap draws over tasks [-0.49, 0.29].

## Table 3, response of the within-kind share of I >= 1 to Ident in scope: the 37

| kind | scope class | gold share of I>=1 (corpus forms) | proposal mean share of I>=1 (held rows) | rise from first class to third |
|---|---|---|---|---|
| RULE | no Ident in scope | 0.000 (10208) | 0.015 (45) |  |
| RULE | Ident in scope, not at a sink | 0.037 (1323) | 0.222 (29) |  |
| RULE | Ident at a sink | 0.837 (2972) | 0.672 (404) | log-odds rise: gold 11.56, proposal 4.89 |
| DET | no Ident in scope | 0.006 (3226) | 0.015 (13) |  |
| DET | Ident in scope, not at a sink | 0.059 (75) | - |  |
| DET | Ident at a sink | 0.798 (175) | 0.330 (5) | log-odds rise: gold 6.43, proposal 3.46 |
| INIT | no Ident in scope | 0.134 (2319) | 0.084 (42) |  |
| INIT | Ident in scope, not at a sink | 0.051 (167) | 0.239 (6) |  |
| INIT | Ident at a sink | 0.806 (686) | 0.263 (61) | log-odds rise: gold 3.29, proposal 1.35 |
| RIGID_DET | no Ident in scope | 0.062 (7) | - |  |
| RIGID_DET | Ident in scope, not at a sink | 0.250 (1) | - |  |
| RIGID_DET | Ident at a sink | 0.583 (5) | - | log-odds rise: gold 3.04, proposal - |

## Table 3, response of the within-kind share of I >= 1 to Ident in scope: the ramp

| kind | scope class | gold share of I>=1 (corpus forms) | proposal mean share of I>=1 (held rows) | rise from first class to third |
|---|---|---|---|---|
| RULE | no Ident in scope | 0.000 (10208) | 0.016 (35) |  |
| RULE | Ident in scope, not at a sink | 0.037 (1323) | 0.242 (6) |  |
| RULE | Ident at a sink | 0.837 (2972) | 0.611 (18) | log-odds rise: gold 11.56, proposal 4.57 |
| DET | no Ident in scope | 0.006 (3226) | 0.022 (17) |  |
| DET | Ident in scope, not at a sink | 0.059 (75) | - |  |
| DET | Ident at a sink | 0.798 (175) | 0.197 (2) | log-odds rise: gold 6.43, proposal 2.38 |
| INIT | no Ident in scope | 0.134 (2319) | 0.080 (14) |  |
| INIT | Ident in scope, not at a sink | 0.051 (167) | - |  |
| INIT | Ident at a sink | 0.806 (686) | 0.258 (14) | log-odds rise: gold 3.29, proposal 1.38 |
| RIGID_DET | no Ident in scope | 0.062 (7) | - |  |
| RIGID_DET | Ident in scope, not at a sink | 0.250 (1) | - |  |
| RIGID_DET | Ident at a sink | 0.583 (5) | - | log-odds rise: gold 3.04, proposal - |

## Table 4, against the 4.2% and .04 figures

| set | row | this read | reference |
|---|---|---|---|
| 37 | 1. INIT draws at Ident scopes that read an Ident scope form | 61.2% of 5271 draws | search tries 4.2%, random draws on dagb 28.6%; gold 31.6%, gold with an Ident form in reach 55.2% |
| 37 | 2. median p_prop / p_gold of INIT Ident-only forms, keyed (58) / not keyed (32) | 0.591 / 1.341 | pool share over gold share .04 |
| 37 | 3. INIT draws with a key on an Ident label | 8.0% of 8190 INIT draws, 17.5% of 3730 keyed draws | gold: 36.4% of keys |
| ramp | 1. INIT draws at Ident scopes that read an Ident scope form | 73.7% of 1413 draws | search tries 4.2%, random draws on dagb 28.6%; gold 31.6%, gold with an Ident form in reach 55.2% |
| ramp | 2. median p_prop / p_gold of INIT Ident-only forms, keyed (12) / not keyed (11) | 0.119 / 1.325 | pool share over gold share .04 |
| ramp | 3. INIT draws with a key on an Ident label | 5.7% of 2651 INIT draws, 12.6% of 1197 keyed draws | gold: 36.4% of keys |

## Table 5, cells

- Corpus forms per C1 cell: 24 cells, 4 with under 40 forms (holding 91 forms, which back off).

| set | backoff level of the C1 read (rows) | mean L, C1 | mean L, C2 | mean L, kind alone |
|---|---|---|---|---|
| 37 | C1 486, I2 9 | 0.74 | 0.73 | -1.50 |
| ramp | C1 41 | 1.10 | 1.07 | -0.97 |

Largest C1 cells (nscope, ident_in, ident_sink): ('12+', '0', 0): 4200; ('6-11', '0', 0): 3278; ('0', '0', 0): 2987; ('1-2', '0', 0): 2703; ('3-5', '0', 0): 2599; ('12+', '4+', 1): 1556; ('12+', '4+', 0): 831; ('6-11', '4+', 1): 759; ('3-5', '2-3', 1): 409; ('6-11', '2-3', 1): 396; ('12+', '2-3', 0): 292; ('3-5', '1', 1): 260; ('6-11', '2-3', 0): 171; ('6-11', '1', 1): 132; ('1-2', '1', 1): 126

## Pins and names
- Models: `models-tk` for the 37 and pass 3, `models-tkf` for the ramp, both in kit `sampler-pool-tiekey-value-0729e4943`. These are the models of `kernel-bundle-ec15d12f0`, the kit the refit and Ident reads ran against as the bundle. The `Bundle:` line of `work/facts.md` names an older Kaggle set (priors 49759a522172b459, relR4_o c527e533408a5269, choice5_o 9603712a5cf35684, tilt_v1 730b7596c1b841cc), which this read does not use.
- The ramp read is held out for the priors only: `relR4_o.pkl` has the ramp tasks in its train rows.
- Held gold: `points-eval.json` (sha256 af855438) and `gold-ident-only-refit.json` (08ec1bc4) of `live-gold-r1`. Corpus gold: `sampler-view-final-2149`, 989 stems (`corpus-pin.json`).

## Limits
- The read measures the draw distribution (`Sampler.clause`), not the best-first search's order or its visit end.
- The cell rate is a coarse model of gold. A proposal that equals gold's own process still shows L below 0 on average, because that process knows more than the cell. So L at or above 0 is a loss even against a coarse gold model, and the size of L is a lower bound.
- The shape is a necessary part of a cover, not the whole of one. A small L rules out the head shape as the block. It doesn't rule out the body.
- `relR4_o.pkl` holds the ramp in its train rows. The corpus copy is of 21:49, and the priors were fit earlier, so the corpus can differ from the fit text on stems regolded since.
- Pass 1 alone estimates the totals through the task weights; the raw counts sit beside the weighted ones.
