# Kind pick given scope contents, 37 held-out tasks

State: partial. The fit, the gold-scope reads and the cover-event read on record fields are done. The read on live scopes isn't done. It needs each visit's scope list, which is only in `.visits` and `.bank` files under folders named `out/`. Run the commands at the end of this file to finish it.

`reads.jsonl` and `cover-reads.jsonl` hold every number here. `show2.py` prints most of them.

## Definitions

- pi is today's pick: `Pool.kind` draws from corpus counts + 1 over the kinds the decoder admits. It reads no scope contents beyond that mask. pi is RULE 0.452, INIT 0.303, DET 0.244, RIGID_DET 0.0007. New-scope visits on the base arms split 0.456, 0.301, 0.243, so all kinds are admitted in practice.
- A kind is picked only at a new slot. A resumed visit keeps the kind of its slot.
- A scope fact is defined in `scope_facts.py`, one definition for gold and live forms.

| Fact | Meaning | On the held map |
|---|---|---|
| `size` | forms in the scope, in buckets | read from the record: `scope_forms` in `cover-rows.tsv` |
| `last` | kind of the last form, by depth then form id | rebuilt, needs the scope list |
| `kinds` | counts of each kind, RULE, DET, INIT capped at 2, RIGID_DET at 1 | rebuilt, needs the scope list |
| `leaves` | those counts over forms no scope form reads | rebuilt, needs the scope list |
| `head` | head of the last non-RULE form: INIT pattern, DET proposer, `det-atoms`, `rigid`; 16 names, others `other` | rebuilt, needs the scope list |
| `cols` | Position and Color columns of the last form, from the engine's render | rebuilt, needs the scope list |
| `key` | a scope form has a key group | rebuilt, needs the scope list |
| `ident` | a scope form has a column of type `Ident`, from the engine's render | rebuilt, needs the scope list |
| `stage` | greatest depth in the scope, capped at 6, depth as in `Pool.take` | rebuilt, needs the scope list |

"Stage" has no definition in the code, so this one is a choice. Run time at a draw isn't a scope fact and has no gold analog, so no fact uses it.

## The fit

- Rows: 1,042 tasks outside `eval-tasks.txt`, 14,982 forms, 8 replicate scopes per form, from `gold/gen-v3-11f6a212c/ast-corpus`, the normal form of `corpus/gen/*.arclog` with one case per task. On tasks with no ALTS, 258 of 271 have equal kind counts in the two. On the 3 of the other 13 that were examined, `ast-corpus` has fewer forms.
- Scope rule `picks6`: the form's read forms with ancestors, and 6 - reads other earlier forms with ancestors. This follows `Pool.scope` with k = 6 and `SEARCH_ORACLE_CONTEXT=2`.
- Smoothing, fixed before any read: back-off chain `last`; `stage size`; `kinds`; `ident key`; `leaves`; `cols head`. Each level adds m = 8 forms of the level above. The marginal is add-one.
- A second estimator, gradient boosted trees on the same facts, checks that the chain doesn't lose signal.
- `frozen-fit.json` was hashed into `manifest.json` before the held read.

## How gold scopes differ from live scopes

1. Gold scopes hold only gold forms. A live scope holds kept forms, most of them junk. `picks6-foreign` adds forms of other tasks: 0.208 per form, RULE 0.112 against 0.175.
2. Every gold row holds its form's read forms. A live visit may not, and the 2.3 is defined only on visits that do.
3. Gold scope size tracks position in the program, from 0 to 17+. Live cover events sit at 6, 8, 12 forms at the 10th, 50th, 90th percentiles.
4. The empty scope is one row per task on gold, 7% of forms. A live search gives it 1.4% of RULE tries.
5. A form with no reads is "held" in every live visit. On gold it has one kind of scope. So gold scopes stand in worst for no-read forms.
6. Gold depth reaches the cap of 6 on 39% of rows. The 23 visits of the record's 4 replays are at depth 1 to 4.
7. Picks in gold scopes are uniform. Live picks come from the policy.
8. The fit's text isn't the held text. Kinds, RULE, DET, INIT: non-held 45%, 25%, 30%; held text 74%, 10%, 16%; base cover events 41%, 40%, 19%.

## 1. Bits paid now

| Unit | Rows | All kinds | RULE | DET | INIT |
|---|---|---|---|---|---|
| Pooled `kind` term, actual | 2,458 form rows, base arms | 2.259 (1.966 to 2.579) | 1.153 (1.045 to 1.343) | 3.743 | 2.474 |
| Same weights under pi | same | 1.697 | 1.146 | 2.032 | 1.723 |
| Per form under pi, held forms | 1,370 forms | 1.337 | 1.146 | 2.032 | 1.723 |
| Per form under pi, non-held | 14,982 forms | 1.550 | 1.146 | 2.032 | 1.723 |
| Per cover event under pi | 1,110 events, base arms | 1.613 (1.550 to 1.678) | | | |

- The first row reproduces the record's 2.3, 1.2, 3.7, 2.5.
- Actual is 0.56 over pi on all kinds. Shuffled kinds "save" 0.561 against actual, so a pick that follows a conditional doesn't earn that part. Compare against pi. DET and INIT carry the gap, RULE doesn't. One candidate cause, not tested: exposure stops at the first cover, so a form covered fast in a right-kind visit has few right-kind tries. Testing it needs the visits.
- 84.3% of base cover events came from a visit of gold's kind, and 20.1% from a resumed visit, where no pick was made.

## 2. Entropy of kind given scope contents

Per form. Non-held is leave-one-task-out. Held is the frozen fit, labelled stand-in: gold scopes, not live ones.

| Read | Rows | Marginal | Given facts | Control, shuffled kinds |
|---|---|---|---|---|
| Non-held, `picks6` | 14,982 forms, 1,042 tasks | 1.550 | 1.325 (1.303 to 1.348) | saving -0.068 (-0.075 to -0.062 over 20) |
| Held stand-in, frozen fit | 1,370 forms, 37 tasks | 1.344 | 0.933 (0.860 to 1.013) | saving -0.034 (-0.063 to 0.032 over 20) |
| Ceiling only: held stand-in, leave-one-task-out | 1,370 forms, 37 tasks | 1.105 | 0.933 (0.831 to 1.041) | saving -0.083 (-0.103 to -0.056 over 20) |

- Second estimator: non-held 1.294 (1.273 to 1.316), held 0.939 (0.864 to 1.025). The chain loses little.
- By cell: `cells-nonheld-last-stage.tsv`, `cells-held-last-stage.tsv`, and `-together` files for all facts. Each has forms, tasks, a thin mark, shares, entropy, bits now, bits under the conditional.
- Thin cells, under 50 forms or 8 tasks: non-held last and stage 6 of 24 cells, 0.7% of forms; held 19 of 21 cells, 29% of forms; all facts together non-held 12,091 of 12,104 cells, 84% of forms; held all 1,299 cells.
- Largest non-held cells, forms, entropy in cell: RULE at depth 6+ 3,101, 1.126; INIT at 6+ 1,976, 1.437; DET at 1 1,547, 1.519; empty scope 1,042, 0.813.
- Largest held cells: RULE at 6+ 833, 0.654; INIT at 6+ 141, 0.856.

## 3. Saving if the pick followed the conditional

| Read | Unit | All kinds | RULE |
|---|---|---|---|
| Non-held, leave-one-task-out | per form against pi | 0.224 (0.206 to 0.243) | 0.175 (0.153 to 0.196) |
| Same, scopes not empty | per form against pi | 0.156 (0.138 to 0.174) | 0.193 (0.174 to 0.213) |
| Held stand-in, frozen fit | per form against pi | 0.403 (0.343 to 0.462) | 0.538 (0.490 to 0.578) |
| Ceiling only: held stand-in | per form against held marginal | 0.171 (0.088 to 0.261) | 0.091 (0.043 to 0.132) |
| Held stand-in, frozen fit | pooled, as the 2.3 and 1.2, against pi | 0.305 (-0.013 to 0.613) | -0.372 (-0.923 to 0.109) |
| Same, no-read forms given no saving | pooled against pi | 0.080 (-0.017 to 0.204) | -0.049 (-0.118 to -0.005) |
| Same, second estimator | pooled against pi | 0.073 (-0.024 to 0.199) | -0.079 (-0.176 to -0.022) |
| Cover events, `size` only, frozen fit | per event against pi | -0.246 (-0.312 to -0.178) | range -0.194 to 0.011 |
| Ceiling only: cover events, `size` only | per event against event marginal | 0.008 (-0.009 to 0.023) | |

- Pooled against actual, the same rows give 0.867 (0.450 to 1.288), all kinds, and -0.364 (-0.939 to 0.160), RULE. Of the 0.867, 0.561 appears with shuffled kinds.
- Pooled by kind against pi: DET 1.102 (0.711 to 1.422), INIT -0.325 (-0.637 to 0.049).
- The held 0.403 per form is mostly a mix effect. Held text is 74% RULE, and the fit gives RULE more weight at large scopes. Over a static mix at the held rate, the ceiling leaves 0.171. A change of mix across tasks already failed in `sampler-pool-cover-priors-600s`.
- Scope rule matters. Non-held per form: `prefix` 0.194, `picks6` 0.224, `closure` 0.490. `closure` is exactly the read forms with ancestors, which a live scope isn't.

Read so far: no saving is shown on RULE in the unit of the 1.2. On all kinds the saving in the unit of the 2.3 isn't separated from zero. The one fact read on real cover events carries nothing there. The live read can still change this.

## 4. Which facts carry the signal

Saving per form over the marginal, all kinds and RULE. Each range is in `reads.jsonl`.

| Fact | Non-held all | Non-held RULE | Not empty, all | Not empty, RULE | Held stand-in all | Held stand-in RULE | Ceiling all | Ceiling RULE |
|---|---|---|---|---|---|---|---|---|
| `kinds` | 0.184 | 0.152 | 0.113 | 0.170 | 0.285 | 0.340 | 0.187 | 0.108 |
| `leaves` | 0.181 | 0.135 | 0.111 | 0.151 | 0.310 | 0.377 | 0.196 | 0.093 |
| `last` | 0.177 | 0.140 | 0.106 | 0.158 | 0.282 | 0.345 | 0.176 | 0.082 |
| `head` | 0.153 | 0.113 | 0.082 | 0.125 | 0.108 | 0.087 | 0.098 | 0.016 |
| `size` | 0.138 | 0.128 | 0.064 | 0.145 | 0.246 | 0.369 | 0.141 | 0.089 |
| `stage` | 0.132 | 0.121 | 0.057 | 0.138 | 0.206 | 0.315 | 0.126 | 0.083 |
| `cols` | 0.114 | 0.089 | 0.038 | 0.106 | 0.100 | 0.123 | 0.061 | 0.038 |
| `key` | 0.044 | 0.027 | 0.015 | 0.028 | 0.110 | 0.139 | 0.053 | 0.019 |
| `ident` | 0.029 | 0.008 | 0.015 | 0.009 | 0.090 | 0.107 | 0.063 | 0.021 |
| Together | 0.225 | 0.188 | 0.157 | 0.207 | 0.410 | 0.551 | 0.171 | 0.091 |

- Kinds of the forms in scope carry most of it, in three overlapping forms: `kinds`, `leaves`, `last`. `key` and `ident` add almost nothing.
- `size` and `stage` come from position in a gold program. On real cover events `size` gives 0.008 at the ceiling, so don't trust those two rows, or any fact that shares that cause, until the live read.

## Left out

- Live scope facts other than `size`, on the held map.
- Item 3 in the pooled unit on live scopes.
- `RIGID_DET` by itself: 15 non-held forms, 1 held. `CHOOSE` forms stay in scopes and aren't targets: 18 non-held, 2 held.
- Gold of the 62 eval tasks outside the 37: in neither fit nor read.
- Any effect on later forms: a pick that moves tries changes which forms enter the pool.

## To finish

Both commands read `out/` through `out-all37`. Run them only where that read is allowed.

Rate unmeasured. An estimate is under 5 minutes in all: 148 runs, and about 18,000 scope renders at most at about 12 ms. The builder prints its rate and ETA and resumes by run, so a rerun of the same command goes on.

```
/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --need soon timeout 170 env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-ba0754492/py313-path /Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python -u /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-kind-pick-given-scope-contents-heldout37/build-map-rows.py

/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --need soon timeout 170 env PYTHONDONTWRITEBYTECODE=1 /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python -u /private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-kind-pick-given-scope-contents-heldout37/read-map.py
```

`read-map.py` first checks each form's held and right-kind exposure against `form-rows.tsv`. It then writes `map-reads.jsonl` and `cells-map-last-stage.tsv`: bits at each cover event, the pooled term on live scopes, each fact alone, the shuffled control, and the ceiling. A file over 10 MB needs `zstd --rm` after the read.
