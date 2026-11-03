# Pair term on the scope pick, 37 held-out tasks

State: done. This is a read of the signal on held tasks. No number here is for use elsewhere. Every number comes from `reads.jsonl`, through `report.py`.

## The read

- The pair term separates nothing once scope size and node score are in. On `any`, together 0.498 (0.458 to 0.539) against a shuffled fit of 0.496. On `first`, together 0.634 (0.553 to 0.711) against size alone 0.632 (0.564 to 0.692), and the gain over first order is +0.066 (-0.021 to 0.158).
- On `first`, table overlap and join run the wrong way: `join` 0.357 (0.279 to 0.440), `overlap` 0.380 (0.309 to 0.460), each mean over pairs. Scopes that gave a first cover have less of them. A term built on nodes that fit would point away from those scopes. On `any` the same facts sit at 0.487 and 0.475.
- No saving on the 1.1 bits: -0.144 (-0.240 to -0.061) at block 20, -0.014 at block 5. The reach is small in any case: forms with 2 or more reads are 6.2% of the weight after reads exist, and the ceiling on that route is 0.177 bits.
- On the 3.1 bits of wait the term reads +0.351 (0.149 to 0.518), above its shuffled fit. Do not take it as a saving: first order alone gives +0.174 (-0.004 to 0.335), the pair term's gain over it is +0.179 (-0.008 to 0.297), it sits in the first 20 scopes (+0.415 (0.202 to 0.638), against +0.122 (-0.233 to 0.429) after), and the same tilt loses -0.189 (-0.323 to -0.057) on all first covers, with DET at -1.050 (-1.563 to -0.631).
- `overlap_P` and `join` carry what signal there is, both with a negative weight. `ident` carries none: only 186 of 8540 scopes have such a pair, and 2 `first` positives.
- The term is cheap, median 0.048 ms and largest 7.38 ms a scope, so cost is not what stops it.

Many labels, facts and terms were read here, so a single range that clears .5 or 0 is weak evidence.

## Left out

- `cover` arms: the read is on the base arms only.
- Scopes with a form missing from the final bank, empty scopes: no pair facts. They and their covers keep weight 1 in the bits.
- 66 of 156 `first` scopes with facts have no negative before them in the run, so they leave the AUC and the fit. They stay in the bits read.
- `hold2` is too thin to fit: 5 scopes, 2 tasks.
- A pick that is an ancestor of another pick can't be seen, since a bank holds no pick list. Leaf forms stand in for picks.
- `Ident` values are numbered per producer, so `overlap_I` compares numbers of separate producers. `ident` reads the type only.
- No search was run under the term, and no sampler code changed.

## Definitions

- Node score: `Policy.scope` in `policy.py` takes 5 of 6 picks by the Gumbel top-k rule on `score - uses`, where `score` is the policy model's decision value, fixed when a node is new, and takes 1 pick from the oldest of the least used. `Pool.scope` adds ancestors. A bank file holds `score`, and no pick list, so the picks are read as leaf forms.
- Scope drawn, the unit: a slot, the first visit of a (scope, kind) within 600 s. Its proposals are the tries of all visits of the slot.
- Leaf form: a form of the scope that no form of the scope reads. Pair facts are over pairs of leaf forms, so a pair has no read edge.
- Table sketch: per relation, column and example, the distinct-value count and the smallest 64 hashes of the values, as uint32. DET assignments of an example are put together. The bank holds no rows, so tables were computed again by a replay of the forms.
- Pair facts (`pair_facts.py`): `coltype`, Jaccard of the column type sets, no table read. `ident`, each relation has an `Ident` column, no table read. `join`, the share of compared examples on which a same-type column pair shares 2 or more values. `overlap`, per example and shared type the largest Jaccard over column pairs of that type, mean over shared types, mean over examples. `overlap_P`, `_C`, `_N`, `_I`, `_O`: that on Position; Color; Nat and Int; Ident; other types. `lineage`, a control: the two forms share an ancestor.
- Across examples: train inputs and test inputs. An example counts where both relations have rows. A task-level table (a DET's) counts on every example of the other relation. With no compared example, the fact is 0.
- A form pair takes the largest value over its relation pairs. A scope takes the mean (`_mean`) and the largest (`_max`) over its leaf pairs.
- Labels (`label-rows.tsv`, from the cover map; no fact reads them): `first`, the slot gave a first cover of a gold form in the run. `any`, it gave a cover event. `first_late`, a first cover after the form's read forms were covered, the rows of the wait. `first_r1`, `first_r2`, `any_r2`: covers by a kept clause reading at least 1 or 2 forms. `hold1`, `hold2`: the scope holds all read forms of a form not yet covered that reads at least 1 or 2 forms.
- Match: same run and kind; up to 3 negatives before and 3 after in the run's scope order, within 30 scopes, at least 1 on each side. A negative has no cover event. Both have pair facts.
- AUC: per positive the share of its negatives it beats, ties 1/2; mean per task; mean over tasks. 95% ranges resample tasks, 2,000 times. The shuffled control moves the positive to a random member of each matched set.
- Fit: a conditional logit on the matched sets of the other 36 tasks, fixed ridge 1. It is exactly a term g added to the log of the node-score pick.

## Rows

- 9092 scopes in 74 runs, 37 tasks, base arms. 8540 have pair facts; 478 have a form missing from the final bank, 74 are empty scopes. 7866 negatives.
- Replay: 37180 forms replayed, no replay stopped, 0 forms with no sketch. Row counts per example equal the bank's on 1774 of 1774 checked forms.
- The `out` term rebuilt from the exposure rows: 1.091, against 1.091 in `decompose.jsonl`; RULE 1.898, DET 0.126, INIT 1.175, each equal.

| Label | Scopes | With facts | Matched sets | Left out, no match | Tasks |
|---|---|---|---|---|---|
| first | 194 | 156 | 90 | 66 | 30 |
| any | 754 | 674 | 585 | 89 | 37 |
| first_late | 57 | 56 | 45 | 11 | 20 |
| first_r1 | 103 | 103 | 79 | 24 | 28 |
| first_r2 | 23 | 23 | 21 | 2 | 13 |
| any_r2 | 91 | 91 | 88 | 3 | 25 |
| hold1 | 1942 | 1860 | 1427 | 433 | 27 |
| hold2 | 5 | 5 | 5 | 0 | 2 |

## 1. AUC within task, matched in time

Label `first`, 90 sets, 30 tasks. Shuffled control beside each.

| Fact | Mean over pairs | Control | Largest over pairs | Control |
|---|---|---|---|---|
| `coltype` | 0.470 (0.383 to 0.553) | 0.495 (0.411 to 0.583) | 0.535 (0.510 to 0.560) | 0.499 (0.463 to 0.532) |
| `ident` | 0.496 (0.481 to 0.512) | 0.500 (0.487 to 0.526) | 0.496 (0.481 to 0.512) | 0.501 (0.487 to 0.529) |
| `join` | 0.357 (0.279 to 0.440) | 0.496 (0.421 to 0.579) | 0.444 (0.378 to 0.506) | 0.498 (0.441 to 0.548) |
| `overlap` | 0.380 (0.309 to 0.460) | 0.501 (0.409 to 0.587) | 0.433 (0.356 to 0.518) | 0.498 (0.405 to 0.565) |
| `overlap_P` | 0.400 (0.346 to 0.461) | 0.500 (0.433 to 0.562) | 0.410 (0.355 to 0.467) | 0.497 (0.434 to 0.552) |
| `overlap_C` | 0.486 (0.416 to 0.559) | 0.497 (0.404 to 0.607) | 0.446 (0.379 to 0.515) | 0.502 (0.422 to 0.575) |
| `overlap_N` | 0.493 (0.440 to 0.551) | 0.500 (0.440 to 0.567) | 0.492 (0.440 to 0.550) | 0.504 (0.449 to 0.564) |
| `overlap_O` | 0.534 (0.479 to 0.595) | 0.500 (0.452 to 0.557) | 0.535 (0.480 to 0.596) | 0.502 (0.454 to 0.555) |
| `overlap_I` | 0.490 (0.478 to 0.499) | 0.500 (0.490 to 0.529) | 0.490 (0.478 to 0.499) | 0.499 (0.490 to 0.529) |
| `lineage` | 0.445 (0.400 to 0.496) | 0.501 (0.452 to 0.548) | 0.443 (0.404 to 0.484) | 0.500 (0.450 to 0.547) |

First-order and time, same sets: forms 0.368 (0.308 to 0.436); `score_mean` 0.574 (0.480 to 0.665); `score_max` 0.557 (0.508 to 0.601); depth 0.410 (0.365 to 0.453); order 0.471 (0.445 to 0.501).

Label `any`, 585 sets, 37 tasks. Shuffled control beside each.

| Fact | Mean over pairs | Control | Largest over pairs | Control |
|---|---|---|---|---|
| `coltype` | 0.529 (0.480 to 0.579) | 0.501 (0.462 to 0.542) | 0.517 (0.497 to 0.539) | 0.500 (0.477 to 0.520) |
| `ident` | 0.499 (0.486 to 0.508) | 0.501 (0.491 to 0.517) | 0.499 (0.486 to 0.508) | 0.499 (0.491 to 0.516) |
| `join` | 0.487 (0.439 to 0.537) | 0.503 (0.466 to 0.543) | 0.470 (0.435 to 0.496) | 0.499 (0.476 to 0.517) |
| `overlap` | 0.475 (0.426 to 0.521) | 0.499 (0.464 to 0.538) | 0.471 (0.429 to 0.507) | 0.501 (0.466 to 0.533) |
| `overlap_P` | 0.518 (0.472 to 0.564) | 0.499 (0.462 to 0.533) | 0.513 (0.472 to 0.553) | 0.498 (0.464 to 0.531) |
| `overlap_C` | 0.478 (0.439 to 0.519) | 0.500 (0.467 to 0.536) | 0.480 (0.443 to 0.519) | 0.499 (0.463 to 0.534) |
| `overlap_N` | 0.513 (0.479 to 0.553) | 0.499 (0.472 to 0.536) | 0.509 (0.478 to 0.547) | 0.499 (0.472 to 0.530) |
| `overlap_O` | 0.486 (0.465 to 0.508) | 0.500 (0.479 to 0.529) | 0.486 (0.466 to 0.508) | 0.500 (0.478 to 0.529) |
| `overlap_I` | 0.494 (0.484 to 0.500) | 0.500 (0.493 to 0.513) | 0.494 (0.484 to 0.500) | 0.499 (0.493 to 0.513) |
| `lineage` | 0.489 (0.460 to 0.516) | 0.501 (0.473 to 0.528) | 0.489 (0.461 to 0.515) | 0.498 (0.474 to 0.524) |

First-order and time, same sets: forms 0.508 (0.475 to 0.542); `score_mean` 0.468 (0.422 to 0.512); `score_max` 0.467 (0.436 to 0.498); depth 0.482 (0.451 to 0.511); order 0.499 (0.490 to 0.508).

Facts together, a leave-one-task-out score on `coltype`, `ident`, `join`, `overlap`, each mean and largest. `pair and first order` adds log forms, `score_mean`, `score_max`.

| Label | Sets | Together | Shuffled fit, 50 rounds | Size alone | First order | Pair and first order |
|---|---|---|---|---|---|---|
| first | 90 | 0.634 (0.553 to 0.711) | 0.503 (0.396 to 0.641) | 0.632 (0.564 to 0.692) | 0.657 (0.564 to 0.738) | 0.723 (0.665 to 0.781) |
| any | 585 | 0.498 (0.458 to 0.539) | 0.496 (0.459 to 0.543) | 0.483 (0.450 to 0.515) | 0.501 (0.466 to 0.536) | 0.525 (0.484 to 0.567) |
| first_late | 45 | 0.610 (0.512 to 0.703) | 0.503 (0.368 to 0.658) | 0.671 (0.601 to 0.737) | 0.717 (0.620 to 0.802) | 0.725 (0.634 to 0.803) |
| first_r1 | 79 | 0.642 (0.562 to 0.720) | 0.513 (0.382 to 0.637) | 0.645 (0.577 to 0.706) | 0.670 (0.589 to 0.746) | 0.725 (0.654 to 0.790) |
| first_r2 | 21 | 0.681 (0.544 to 0.816) | 0.518 (0.285 to 0.695) | 0.624 (0.526 to 0.716) | 0.580 (0.468 to 0.699) | 0.698 (0.577 to 0.814) |
| any_r2 | 88 | 0.568 (0.462 to 0.667) | 0.500 (0.399 to 0.582) | 0.489 (0.408 to 0.576) | 0.538 (0.446 to 0.630) | 0.537 (0.445 to 0.629) |
| hold1 | 1427 | 0.558 (0.525 to 0.588) | 0.497 (0.438 to 0.561) | 0.546 (0.499 to 0.590) | 0.619 (0.575 to 0.665) | 0.611 (0.571 to 0.651) |

AUC gain of the pair facts over first order, same task resamples:

| Fit label | Pair and first order, less first order | Pair, less size |
|---|---|---|
| first | +0.066 (-0.021 to 0.158) | +0.001 (-0.110 to 0.122) |
| any | +0.023 (-0.013 to 0.059) | +0.015 (-0.028 to 0.053) |
| first_late | +0.008 (-0.088 to 0.099) | -0.061 (-0.175 to 0.056) |
| first_r1 | +0.055 (-0.040 to 0.152) | -0.003 (-0.116 to 0.117) |
| hold1 | -0.008 (-0.034 to 0.016) | +0.013 (-0.045 to 0.067) |

With negatives matched on the size bucket too, facts by mean over pairs:

| Label | Sets | `join` | `overlap` | `overlap_P` | `coltype` | forms |
|---|---|---|---|---|---|---|
| first | 83 | 0.364 (0.290 to 0.444) | 0.398 (0.324 to 0.476) | 0.410 (0.357 to 0.470) | 0.492 (0.416 to 0.571) | 0.415 (0.352 to 0.484) |
| any | 526 | 0.466 (0.421 to 0.511) | 0.455 (0.411 to 0.498) | 0.501 (0.451 to 0.552) | 0.525 (0.474 to 0.579) | 0.502 (0.464 to 0.540) |
| first_r1 | 73 | 0.370 (0.286 to 0.463) | 0.402 (0.323 to 0.490) | 0.399 (0.342 to 0.467) | 0.511 (0.424 to 0.602) | 0.411 (0.345 to 0.485) |
| first_late | 40 | 0.372 (0.266 to 0.489) | 0.418 (0.306 to 0.527) | 0.358 (0.308 to 0.408) | 0.467 (0.340 to 0.598) | 0.382 (0.319 to 0.461) |

## 2. Bits of a pick by node score plus the pair term

How it is counted. A pick with the term has P'(S) proportional to P(S) e^g(S). For a fixed pool, E'[h] = E[h e^g] / E[e^g], so each drawn scope takes a weight m = e^g / Z, with g fitted on the other tasks and Z the tries-weighted mean of e^g in a block of consecutive scopes of the run. That keeps the block's proposals.

What it assumes:

- The pool at each draw stays as recorded. A form covered sooner opens no later form here, and a form delayed closes none, so effects on the chain, the 2.9 bits of reads not covered, are not counted.
- A scope's proposals, and its covers per proposal, stay as recorded under m. Use counts, and so later picks, do not move, and the resume rule does not react.
- The term is one scope-level factor, applied to the whole of a scope. It tilts drawn scopes only. In expectation that equals a real pick, and in a run of about 120 scopes the sample is small.

Units. `out`: the change in the 1.1-bit term, log2 of W held under m over W held, with the same w = 2^(-s x bits). A positive number is a saving. Wait: log2 of the mean m over the 63 first covers of the wait rows, the rise in the hazard that the 3.1 bits describe. All first covers: the same on all 281 first covers of the base arms.

| Fit label, sets | Term | `out`, of 1.1 | Wait, of 3.1 | All first covers | Weights: sd, largest, effective share |
|---|---|---|---|---|---|
| first, 90 | pair | -0.144 (-0.240 to -0.061) | +0.351 (0.149 to 0.518) | -0.189 (-0.323 to -0.057) | 0.63, 9.7, 0.71 |
| first, 90 | first order | -0.091 (-0.156 to -0.034) | +0.174 (-0.004 to 0.335) | -0.102 (-0.195 to -0.018) | 0.57, 4.9, 0.72 |
| first, 90 | pair and first order | -0.146 (-0.243 to -0.064) | +0.353 (0.116 to 0.555) | -0.134 (-0.272 to 0.001) | 0.97, 17.0, 0.47 |
| first, 90 | size | -0.002 (-0.029 to 0.026) | +0.061 (-0.076 to 0.185) | +0.035 (-0.048 to 0.099) | 0.53, 6.1, 0.75 |
| first, 90 | score | -0.109 (-0.185 to -0.042) | +0.181 (0.032 to 0.328) | -0.165 (-0.254 to -0.079) | 0.35, 3.2, 0.89 |
| any, 585 | pair | -0.030 (-0.049 to -0.015) | +0.087 (-0.010 to 0.176) | -0.074 (-0.114 to -0.033) | 0.19, 2.6, 0.96 |
| any, 585 | first order | +0.045 (0.022 to 0.070) | -0.054 (-0.088 to -0.025) | +0.085 (0.035 to 0.137) | 0.13, 2.5, 0.98 |
| any, 585 | pair and first order | +0.018 (-0.007 to 0.044) | +0.045 (-0.109 to 0.167) | +0.009 (-0.050 to 0.062) | 0.24, 3.1, 0.94 |
| any, 585 | size | -0.001 (-0.003 to 0.002) | +0.003 (-0.010 to 0.015) | -0.002 (-0.011 to 0.005) | 0.04, 1.2, 1.00 |
| any, 585 | score | +0.032 (0.014 to 0.052) | -0.039 (-0.069 to -0.012) | +0.063 (0.024 to 0.106) | 0.11, 1.7, 0.99 |
| first_late, 45 | pair | -0.134 (-0.243 to -0.056) | +0.249 (0.045 to 0.406) | -0.279 (-0.422 to -0.149) | 1.27, 37.1, 0.39 |
| first_late, 45 | first order | -0.098 (-0.173 to -0.036) | +0.173 (-0.032 to 0.357) | -0.100 (-0.207 to -0.004) | 0.70, 7.7, 0.63 |
| first_late, 45 | pair and first order | -0.121 (-0.231 to -0.036) | +0.206 (-0.073 to 0.443) | -0.246 (-0.405 to -0.095) | 2.71, 94.2, 0.12 |
| first_late, 45 | size | +0.001 (-0.033 to 0.038) | +0.064 (-0.112 to 0.213) | +0.048 (-0.048 to 0.122) | 0.66, 11.0, 0.65 |
| first_late, 45 | score | -0.121 (-0.208 to -0.046) | +0.186 (0.016 to 0.350) | -0.179 (-0.280 to -0.083) | 0.40, 4.7, 0.85 |
| first_r1, 79 | pair | -0.136 (-0.230 to -0.053) | +0.355 (0.147 to 0.532) | -0.173 (-0.302 to -0.046) | 0.61, 7.4, 0.72 |
| first_r1, 79 | first order | -0.108 (-0.186 to -0.040) | +0.206 (0.006 to 0.384) | -0.119 (-0.221 to -0.024) | 0.63, 6.0, 0.68 |
| first_r1, 79 | pair and first order | -0.157 (-0.264 to -0.065) | +0.375 (0.125 to 0.592) | -0.130 (-0.265 to 0.003) | 0.92, 12.5, 0.49 |
| first_r1, 79 | size | -0.001 (-0.030 to 0.029) | +0.065 (-0.086 to 0.197) | +0.039 (-0.049 to 0.106) | 0.57, 7.0, 0.72 |
| first_r1, 79 | score | -0.125 (-0.212 to -0.047) | +0.214 (0.040 to 0.384) | -0.178 (-0.281 to -0.081) | 0.42, 4.1, 0.84 |
| any_r2, 88 | pair | -0.048 (-0.088 to -0.011) | +0.299 (0.145 to 0.451) | -0.063 (-0.163 to 0.025) | 0.41, 5.2, 0.85 |
| any_r2, 88 | first order | -0.035 (-0.063 to -0.008) | +0.042 (-0.033 to 0.117) | -0.059 (-0.099 to -0.016) | 0.23, 2.4, 0.95 |
| any_r2, 88 | pair and first order | -0.038 (-0.083 to 0.004) | +0.270 (0.115 to 0.427) | -0.069 (-0.166 to 0.022) | 0.48, 5.6, 0.81 |
| any_r2, 88 | size | +0.001 (-0.003 to 0.004) | -0.023 (-0.039 to 0.001) | -0.005 (-0.019 to 0.015) | 0.08, 1.6, 0.99 |
| any_r2, 88 | score | -0.007 (-0.024 to 0.008) | +0.014 (-0.058 to 0.079) | -0.002 (-0.037 to 0.028) | 0.17, 2.0, 0.97 |
| hold1, 1427 | pair | +0.012 (-0.010 to 0.033) | +0.128 (-0.008 to 0.262) | +0.022 (-0.088 to 0.113) | 0.40, 9.0, 0.86 |
| hold1, 1427 | first order | -0.124 (-0.216 to -0.038) | +0.207 (0.052 to 0.377) | -0.193 (-0.312 to -0.082) | 0.51, 4.7, 0.80 |
| hold1, 1427 | pair and first order | -0.071 (-0.149 to 0.005) | +0.260 (0.069 to 0.480) | -0.117 (-0.297 to 0.045) | 0.68, 7.4, 0.70 |
| hold1, 1427 | size | +0.001 (-0.008 to 0.011) | -0.023 (-0.082 to 0.041) | +0.009 (-0.034 to 0.064) | 0.19, 1.9, 0.97 |
| hold1, 1427 | score | -0.092 (-0.155 to -0.037) | +0.162 (0.026 to 0.294) | -0.136 (-0.212 to -0.066) | 0.30, 2.4, 0.91 |

Shuffled-label fit, pair term, 50 rounds, mean and 95% of rounds:

| Fit label | `out` | Wait | All first covers |
|---|---|---|---|
| first | -0.001 (-0.097 to 0.077) | +0.005 (-0.202 to 0.162) | -0.008 (-0.181 to 0.143) |
| any | +0.000 (-0.034 to 0.031) | -0.004 (-0.091 to 0.083) | +0.001 (-0.060 to 0.069) |
| first_late | -0.004 (-0.118 to 0.107) | -0.023 (-0.308 to 0.205) | -0.008 (-0.206 to 0.201) |
| first_r1 | -0.003 (-0.073 to 0.078) | +0.009 (-0.157 to 0.160) | -0.013 (-0.145 to 0.159) |
| any_r2 | -0.006 (-0.065 to 0.055) | +0.007 (-0.190 to 0.212) | -0.014 (-0.142 to 0.125) |
| hold1 | +0.002 (-0.017 to 0.020) | -0.012 (-0.056 to 0.030) | +0.004 (-0.048 to 0.038) |

Gain of the pair term over first order in bits, same resamples, `first` fit: `out` -0.055 (-0.102 to -0.010), wait +0.179 (-0.008 to 0.297), all first covers -0.032 (-0.166 to 0.083).

Block and strength, pair term, `first` fit:

| Setting | `out` | Wait | All first covers |
|---|---|---|---|
| block 5 beta x 1.0 | -0.014 | +0.315 | -0.208 |
| block 10 beta x 1.0 | -0.089 | +0.316 | -0.192 |
| block 20 beta x 1.0 | -0.144 | +0.351 | -0.189 |
| block 40 beta x 1.0 | -0.161 | +0.315 | -0.200 |
| block 20 beta x 0.5 | -0.101 | +0.222 | -0.165 |
| block 20 beta x 2.0 | -0.160 | +0.493 | -0.170 |
| block 20 first 20 scopes untilted | -0.001 | -0.030 | +0.006 |

The first 20 scopes of a run hold 231 of 281 first covers and 40 of 63 wait covers. Split by that place, block 5:

| Fit, term | Place | `out` | Wait | Covers | All first covers | Covers |
|---|---|---|---|---|---|---|
| first pair | first 20 scopes | -0.023 (-0.082 to 0.032) | +0.415 (0.202 to 0.638) | 40 | -0.278 (-0.436 to -0.127) | 231 |
| first pair | after | -0.006 (-0.023 to 0.011) | +0.122 (-0.233 to 0.429) | 23 | +0.078 (-0.133 to 0.262) | 50 |
| first first_order | first 20 scopes | -0.017 (-0.069 to 0.026) | +0.124 (0.008 to 0.280) | 40 | -0.212 (-0.324 to -0.111) | 231 |
| first first_order | after | -0.019 (-0.040 to -0.004) | +0.241 (-0.111 to 0.589) | 23 | +0.124 (-0.057 to 0.327) | 50 |
| first score | first 20 scopes | -0.044 (-0.089 to -0.007) | +0.161 (0.034 to 0.328) | 40 | -0.239 (-0.348 to -0.137) | 231 |
| first score | after | +0.003 (-0.003 to 0.009) | +0.193 (-0.012 to 0.430) | 23 | +0.077 (-0.044 to 0.211) | 50 |
| any pair | first 20 scopes | -0.003 (-0.012 to 0.004) | +0.090 (0.018 to 0.143) | 40 | -0.066 (-0.101 to -0.029) | 231 |
| any pair | after | -0.001 (-0.005 to 0.003) | +0.047 (-0.057 to 0.128) | 23 | +0.026 (-0.035 to 0.089) | 50 |

Reach. A pair term can only act on a form with 2 or more reads through its pair of read forms. The `out` term by reads:

| Reads | Form rows | Reads all covered | Rows with held exposure | First covered | `out` | Share of W after reads exist | Share of W held |
|---|---|---|---|---|---|---|---|
| 0 | 234 | 224 | 224 | 142 | 0.0 | 0.401 | 0.855 |
| 1 | 1016 | 172 | 107 | 118 | 2.998 | 0.536 | 0.143 |
| 2+ | 1208 | 29 | 3 | 21 | 6.081 | 0.062 | 0.002 |

Ceiling: if every proposal after the reads exist counted as held for forms with 2 or more reads, `out` falls from 1.091 to 0.914, a saving of 0.177 bits. 5 scopes of 9092 held all reads of an uncovered form with 2 or more reads.

## 3. By kind and by scope size

A row is a positive scope, of a slot of that kind. Size is forms in the scope, ancestors included, and negatives are matched within the cell. `thin`: under 50 rows or under 8 tasks. AUC of the score fitted on all kinds, and of `join` and `overlap`, mean over pairs.

Label `first`:

| Cell | Rows | Tasks | Mark | Together | `join` | `overlap` | `coltype` |
|---|---|---|---|---|---|---|---|
| kind RULE | 48 | 20 | thin | 0.619 (0.507 to 0.729) | 0.382 (0.266 to 0.508) | 0.397 (0.293 to 0.505) | 0.577 (0.470 to 0.681) |
| kind DET | 15 | 10 | thin | 0.637 (0.476 to 0.811) | 0.323 (0.167 to 0.474) | 0.334 (0.186 to 0.481) | 0.417 (0.251 to 0.602) |
| kind INIT | 27 | 20 | thin | 0.611 (0.477 to 0.737) | 0.385 (0.258 to 0.519) | 0.379 (0.271 to 0.500) | 0.402 (0.283 to 0.528) |
| size 3-4 | 0 | 0 | thin | | | | |
| size 5-8 | 68 | 26 |  | 0.682 (0.581 to 0.776) | 0.391 (0.313 to 0.477) | 0.412 (0.335 to 0.493) | 0.535 (0.465 to 0.607) |
| size 9-16 | 15 | 12 | thin | 0.553 (0.393 to 0.707) | 0.281 (0.124 to 0.465) | 0.346 (0.189 to 0.507) | 0.306 (0.156 to 0.469) |
| size 17+ | 0 | 0 | thin | | | | |
| kind RULE size 5-8 | 37 | 19 | thin | 0.634 (0.512 to 0.755) | 0.431 (0.302 to 0.564) | 0.449 (0.343 to 0.559) | 0.588 (0.472 to 0.699) |
| kind RULE size 9-16 | 8 | 7 | thin | 0.664 (0.400 to 0.879) | 0.239 (0.000 to 0.502) | 0.276 (0.071 to 0.500) | 0.461 (0.162 to 0.750) |
| kind DET size 5-8 | 12 | 10 | thin | 0.780 (0.640 to 0.910) | 0.272 (0.110 to 0.445) | 0.255 (0.123 to 0.401) | 0.476 (0.287 to 0.665) |
| kind DET size 9-16 | 2 | 2 | thin | 0.367 (0.333 to 0.400) | 0.183 (0.167 to 0.200) | 0.567 (0.333 to 0.800) | 0.200 (0.000 to 0.400) |
| kind INIT size 5-8 | 19 | 14 | thin | 0.608 (0.421 to 0.807) | 0.457 (0.296 to 0.631) | 0.418 (0.260 to 0.570) | 0.477 (0.315 to 0.645) |
| kind INIT size 9-16 | 5 | 5 | thin | 0.483 (0.300 to 0.700) | 0.417 (0.233 to 0.600) | 0.417 (0.267 to 0.600) | 0.217 (0.050 to 0.384) |

Label `any`:

| Cell | Rows | Tasks | Mark | Together | `join` | `overlap` | `coltype` |
|---|---|---|---|---|---|---|---|
| kind RULE | 280 | 28 |  | 0.532 (0.469 to 0.596) | 0.466 (0.401 to 0.529) | 0.465 (0.392 to 0.535) | 0.568 (0.518 to 0.617) |
| kind DET | 207 | 26 |  | 0.457 (0.404 to 0.514) | 0.493 (0.438 to 0.543) | 0.475 (0.424 to 0.530) | 0.446 (0.388 to 0.500) |
| kind INIT | 98 | 29 |  | 0.557 (0.479 to 0.638) | 0.446 (0.360 to 0.541) | 0.445 (0.371 to 0.524) | 0.491 (0.409 to 0.572) |
| size 3-4 | 0 | 0 | thin | | | | |
| size 5-8 | 279 | 35 |  | 0.554 (0.498 to 0.610) | 0.431 (0.379 to 0.486) | 0.430 (0.376 to 0.488) | 0.533 (0.472 to 0.601) |
| size 9-16 | 247 | 36 |  | 0.501 (0.445 to 0.553) | 0.495 (0.431 to 0.561) | 0.493 (0.432 to 0.554) | 0.516 (0.457 to 0.578) |
| size 17+ | 0 | 0 | thin | | | | |
| kind RULE size 5-8 | 149 | 24 |  | 0.518 (0.450 to 0.594) | 0.454 (0.384 to 0.517) | 0.464 (0.382 to 0.534) | 0.591 (0.528 to 0.651) |
| kind RULE size 9-16 | 112 | 28 |  | 0.555 (0.473 to 0.640) | 0.479 (0.395 to 0.557) | 0.474 (0.393 to 0.554) | 0.548 (0.466 to 0.636) |
| kind DET size 5-8 | 81 | 24 |  | 0.538 (0.444 to 0.631) | 0.371 (0.302 to 0.444) | 0.357 (0.292 to 0.429) | 0.366 (0.271 to 0.461) |
| kind DET size 9-16 | 97 | 24 |  | 0.443 (0.371 to 0.520) | 0.503 (0.421 to 0.584) | 0.503 (0.420 to 0.583) | 0.462 (0.373 to 0.554) |
| kind INIT size 5-8 | 49 | 20 | thin | 0.567 (0.464 to 0.663) | 0.489 (0.387 to 0.604) | 0.451 (0.351 to 0.559) | 0.559 (0.445 to 0.676) |
| kind INIT size 9-16 | 38 | 21 | thin | 0.568 (0.468 to 0.659) | 0.452 (0.355 to 0.554) | 0.435 (0.330 to 0.543) | 0.478 (0.362 to 0.599) |

Bits by the gold form's kind, block 20, `first` fit. A row under 50 covers or 8 tasks is thin.

| Kind | `out`, of the kind's term | Wait | Wait covers, tasks | All first covers | Covers, tasks |
|---|---|---|---|---|---|
| RULE | +0.089 (0.025 to 0.184) of 1.9 | +0.514 (0.333 to 0.739) | 35, 15, thin | +0.276 (0.144 to 0.412) | 106, 27 |
| DET | -0.578 (-0.793 to -0.340) of 0.1 | +0.043 (-1.407 to 0.415) | 5, 3, thin | -1.050 (-1.563 to -0.631) | 106, 26 |
| INIT | -0.007 (-0.042 to 0.028) of 1.2 | +0.133 (-0.297 to 0.406) | 23, 14, thin | -0.044 (-0.280 to 0.177) | 69, 27 |

By scope size, log2 of the mean weight on first covers in the size: 5-8: -0.214, 185 covers, 33 tasks; 9-16: -0.431, 35 covers, 20 tasks, thin; 17+: None, 0 covers, 0 tasks, thin.

## 4. Cost of the term

- One thread, Python sets, no memo, one scope: median 0.048 ms, 90th percentile 0.229 ms, 99th 0.813 ms, largest 7.38 ms, over 8540 scopes. A real pick that looks at m candidate scopes pays m times this, less a memo of form pairs.
- Sketch: bottom 64 hashes, uint32, per relation, column and example, 26.8% of column-example entries have over 64 values. Stored bytes per relation: median 96, largest 5502; per form: median 108, largest 17880; per run, leaf forms only: median 140962, largest 364510. As Python frozensets, per relation: median 2624, largest 110096.
- Building one sketch from a parsed table: median 0.025 ms, 90th percentile 1.52 ms, largest 22.0 ms, on 2571 relations of up to 174174 rows.

## 5. Which fact carries the signal, each alone

Leave-one-task-out on one fact, its mean and largest. Bits at block 20.

| Fit label | Fact | AUC | `out` | Wait | All first covers |
|---|---|---|---|---|---|
| first | `coltype` | 0.588 (0.510 to 0.664) | -0.014 (-0.030 to 0.000) | +0.020 (-0.029 to 0.056) | +0.003 (-0.029 to 0.036) |
| first | `ident` | 0.483 (0.468 to 0.496) | +0.006 (-0.001 to 0.015) | -0.010 (-0.018 to -0.002) | -0.009 (-0.016 to -0.005) |
| first | `join` | 0.643 (0.560 to 0.721) | -0.137 (-0.217 to -0.074) | +0.210 (0.081 to 0.303) | -0.249 (-0.357 to -0.151) |
| first | `overlap` | 0.624 (0.545 to 0.704) | -0.138 (-0.212 to -0.079) | +0.150 (0.040 to 0.248) | -0.258 (-0.370 to -0.152) |
| first | `overlap_P` | 0.600 (0.539 to 0.654) | -0.165 (-0.284 to -0.071) | +0.326 (0.154 to 0.527) | -0.176 (-0.313 to -0.051) |
| first | `overlap_C` | 0.515 (0.442 to 0.585) | -0.013 (-0.029 to -0.000) | -0.039 (-0.116 to 0.030) | -0.040 (-0.087 to -0.000) |
| first | `overlap_N` | 0.416 (0.370 to 0.461) | -0.000 (-0.001 to 0.001) | -0.004 (-0.020 to 0.007) | -0.005 (-0.016 to 0.004) |
| first | `overlap_O` | 0.541 (0.490 to 0.600) | -0.027 (-0.052 to -0.008) | +0.025 (-0.072 to 0.134) | +0.044 (-0.026 to 0.114) |
| first | `overlap_I` | 0.510 (0.501 to 0.522) | +0.000 (-0.000 to 0.001) | +0.001 (0.000 to 0.002) | +0.002 (0.001 to 0.003) |
| first | `lineage` | 0.558 (0.524 to 0.596) | -0.006 (-0.024 to 0.009) | +0.012 (-0.056 to 0.078) | -0.015 (-0.061 to 0.026) |
| any | `coltype` | 0.503 (0.467 to 0.539) | -0.010 (-0.017 to -0.005) | +0.008 (-0.007 to 0.019) | -0.013 (-0.028 to 0.002) |
| any | `ident` | 0.498 (0.486 to 0.507) | +0.003 (0.000 to 0.009) | +0.004 (-0.006 to 0.019) | -0.003 (-0.007 to 0.002) |
| any | `join` | 0.513 (0.464 to 0.561) | -0.033 (-0.051 to -0.018) | +0.078 (0.007 to 0.143) | -0.072 (-0.109 to -0.035) |
| any | `overlap` | 0.514 (0.465 to 0.564) | -0.028 (-0.042 to -0.016) | +0.024 (-0.033 to 0.084) | -0.076 (-0.106 to -0.047) |
| any | `overlap_P` | 0.483 (0.448 to 0.520) | +0.010 (0.004 to 0.018) | -0.017 (-0.035 to 0.000) | +0.039 (0.016 to 0.063) |
| any | `overlap_C` | 0.521 (0.480 to 0.560) | -0.010 (-0.019 to -0.003) | -0.012 (-0.054 to 0.025) | -0.020 (-0.052 to 0.006) |
| any | `overlap_N` | 0.485 (0.450 to 0.515) | +0.001 (-0.001 to 0.003) | +0.005 (-0.015 to 0.021) | -0.006 (-0.018 to 0.004) |
| any | `overlap_O` | 0.514 (0.492 to 0.535) | +0.005 (-0.000 to 0.012) | -0.022 (-0.067 to 0.006) | -0.009 (-0.020 to 0.001) |
| any | `overlap_I` | 0.506 (0.500 to 0.516) | +0.000 (-0.000 to 0.000) | +0.000 (0.000 to 0.001) | +0.001 (0.000 to 0.001) |
| any | `lineage` | 0.514 (0.489 to 0.541) | +0.005 (0.000 to 0.010) | -0.007 (-0.028 to 0.013) | +0.016 (-0.007 to 0.049) |

`ident`: 186 of 8540 scopes have a leaf pair with an Ident column on each side; among positives, `first` 2, `any` 11.

