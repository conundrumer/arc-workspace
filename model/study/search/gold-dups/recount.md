# Gold duplicate cover: map, fix, and effect on r1 runs

## Result

- 36 of the 50 tasks (37 held-out, 13 fold) have at least one gold key with 2 or more gold forms. The 37 held-out: 32 tasks, 97 groups, 114 extra forms. The 13 fold tasks: 4 tasks, 5 groups, 5 extra forms.
- The map finds all 5 hand-read stuck roots: aa4ec2a5 [0,4] and [3,9,10], dfadab01 [3,4], db695cfb [17,25].
- With the fix, forms covered rise by 16 to 25 per arm and seed (about 9 to 13%; lower to upper bound). The bundle and the other arm gain about the same, so D moves by at most 4 forms.
- No verdict changes. Both runs still fail, with the same reasons.
- 9 of the 40 (seed 0) and 9 of the 44 (seed 1) stuck roots of the frontier read are covered once expanded.
- Check: a 14 s direct worker with the patch on dfadab01 and on aa4ec2a5 writes the duplicate cover lines.

## Files

All under `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/gold-dups/`.

| file | content |
|---|---|
| `dups.json` | {task: [[i, j, ...], ...]}, one list per table key with 2 or more gold indices, for 50 tasks (empty list: none). |
| `dups.jsonl` | The stream behind it, one line per task, with `all_keys` (every key's index list, singletons too). |
| `gold_dups.py` | Builds `dups.jsonl` and `dups.json` with the patched `gold_keys`. Resumes; `--budget` seconds per call. |
| `gold-dups.patch` | The fix in `model/study/sampler/superdag.py` (`patch -p1` from the kit root). |
| `gold-dups-search.patch` | Two lines in `superdag_search.py` that must go with it (see Users). |
| `kit-patched/` | The kit with both patches applied: a real copy of `model/`, symlinks for the rest. |
| `run_direct.sh` | The direct-run helper, from the proposer-mask one. `RULE=` (empty) gives the bundle arm. |
| `recount.py`, `recount.json` | The recount and all its numbers (per task, per arm and seed). |
| `direct-patched-dfadab01/`, `direct-patched-aa4ec2a5/`, `direct-orig-dfadab01/` | Check runs. |

## The map

`gold_dups.py` sets up as `kaggle_worker.py` does: `live.Sampler(models-tk)`, `superdag_search.install('search')` (which installs the order-free `table_key`), a `Run` on the task, then `D.gold_keys` on `points-eval.json` with `ARCLOG_IDENT_SOURCE=value`. It runs on the Mac engine with seed 0. The key is the table merge key, so it reads no atom order, atom index or last-atom fact. The 13 fold tasks are the tasks of the `bundlef` arm in `kits/search-node-score-jobs-arms-heldout50-2seeds-600s.txt`.

A form with several tables has several keys, so groups can overlap on one form (for example b10624e5 [23,28] and [23,29]; aa4ec2a5 form 11 has a key alone and the key [11,12]). 18 forms own a mix like that. Gold forms 11 and 12 of aa4ec2a5 are a duplicate pair that the hand read did not list.

## The fix

`gold_keys` returns {key: [gold indices, ascending]}. `Pool.add_form` writes one `cover` event per index of the key, with the node, depth and draw of the node. `self.covered` stays keyed by table key, so a key covers once.

Users of `self.gold` / `gold_keys`:

| user | reads | with the fix |
|---|---|---|
| `Pool.add_form`, `cover` event | one index | all indices (one event each, same node, draw, depth). This is the fix. |
| `Pool.add_form`, `tags.kind` | only whether the key is in gold (`is not None`) | unchanged: the list is never empty, so the label is the same. |
| `self.covered` (key to node) | keys | unchanged. |
| progress lines, `done.json` (`gold=len(gold)`, `covered=len(pool.covered)`), `kaggle_worker` end line | counts of keys | unchanged. They count tables, not gold forms. |
| `superdag_search.first_pass`, `covered=sorted({self.gold[k] ...})` | one index per key | would break (a list is not hashable). `gold-dups-search.patch` reads all indices. The `first pass` event then lists the duplicate forms too. |
| `superdag_search.add_form`, `cover2` event (gold2, `points-cheapest.json`) | one index | would write a list as `gold`. `gold-dups-search.patch` writes one event per index. `kaggle_worker` writes `gold` as given, so it needs no change. |
| `kaggle_worker` (`D.gold_keys` call, `event`) | passes the dict on; writes `gold=x['gold']` for `cover` and `cover2` | unchanged. |

The cover check changes only what gets written to the `.cover` and `.cover2` files and the `first pass` event. No pick, draw, node or node label reads gold.

Check by direct worker (14 s, `run_direct.sh`, `RULE=` empty):

- dfadab01, seed 0: patched `.cover` has gold 3 and gold 4 on node 9 at draw 12. The unpatched control has gold 3 only. The patched `.cover2` lists gold 1 and 2 as two lines (the control had gold 1 only; the cheapest gold has the pair [1,2] too).
- aa4ec2a5, seed 1000: patched `.cover` has gold 0 and 4 on node 92 (draw 100), gold 3, 9 and 10 on node 94 (draw 103), and gold 11 and 12 on node 208 (draw 234).
- Picks are the same. The scope picks of the patched run and of two control runs are the same lists in the same order ([16, 5, 6, 0, 3, 1], then [0, 6, 16, 5, 33, 2]). The runs differ in timing (a visit ends by seconds), so the draw where a later pick happens, and which later forms are covered, differ between two control runs as well. For example gold 2 came at node 143 draw 241 in one control run and not at all in the other.

## The recount

Method (`recount.py`): read each job's `.out.jsonl.cover` as `search_node_score_read.job_record` does. The old totals reproduce the verdicts exactly (forms covered, DET, Ident-only, in both runs). A cover line for index i means a key whose first index is i was covered. So the expansion adds the other indices of every group whose first index is i. Indices that are not first in their group get no line today, and they get none from a cover of their own other keys.

A form that owns more than one key is ambiguous: the line does not say which key was covered. Two columns bracket that:

- lower: add only what every duplicate key of i gives, and nothing where i also owns a key with no duplicate.
- upper: add every duplicate group that i owns.

Forms covered (all / DET / Ident-only), sum over the 37 tasks, per job set. Seed 0 is `s0`, seed 1000 is `s1`.

Refit run (`search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943`):

| arm, seed | old | new lower | new upper |
|---|---|---|---|
| bundle s0 | 180 / 49 / 9 | 197 / 56 / 9 | 202 / 57 / 9 |
| bundle s1 | 175 / 50 / 6 | 192 / 57 / 6 | 195 / 58 / 6 |
| refit s0 | 167 / 46 / 5 | 184 / 53 / 6 | 189 / 54 / 6 |
| refit s1 | 170 / 47 / 4 | 186 / 53 / 4 | 189 / 54 / 4 |
| bundle, mean of seeds | 177.5 | 194.5 | 198.5 |
| refit, mean of seeds | 168.5 | 185.0 | 189.0 |

Joint run (`search-joint-r1-heldout37-2seeds-600s-0729e4943`):

| arm, seed | old | new lower | new upper |
|---|---|---|---|
| bundle s0 | 189 / 49 / 7 | 209 / 56 / 8 | 214 / 57 / 8 |
| bundle s1 | 174 / 48 / 6 | 191 / 55 / 6 | 196 / 56 / 6 |
| joint s0 | 168 / 47 / 4 | 185 / 54 / 4 | 189 / 55 / 4 |
| joint s1 | 180 / 49 / 11 | 198 / 56 / 13 | 204 / 57 / 14 |
| bundle, mean of seeds | 181.5 | 200.0 | 205.0 |
| joint, mean of seeds | 174.0 | 191.5 | 196.5 |

D (arm minus bundle) and the verdict. The rule is the one in each `verdict.json`: forms covered D at least minus the noise band, and Ident-only D above 0, on both seeds. The band is the absolute difference of the bundle's two seeds. The 90% bands of the mean were not resampled.

| run | quantity | old | new lower | new upper |
|---|---|---|---|---|
| refit | noise band | 5 | 5 | 7 |
| refit | D forms, s0 | -13 (fail) | -13 (fail) | -13 (fail) |
| refit | D forms, s1 | -5 (ok) | -6 (fail, band 5) | -6 (ok, band 7) |
| refit | D forms, mean | -9.0 | -9.5 | -9.5 |
| refit | D Ident-only, s0 / s1 | -4 / -2 | -3 / -2 | -3 / -2 |
| refit | D DET, s0 / s1 | -3 / -3 | -3 / -4 | -3 / -4 |
| refit | verdict | fail | fail | fail |
| joint | noise band | 15 | 18 | 18 |
| joint | D forms, s0 | -21 (fail) | -24 (fail) | -25 (fail) |
| joint | D forms, s1 | +6 (ok) | +7 (ok) | +8 (ok) |
| joint | D forms, mean | -7.5 | -8.5 | -8.5 |
| joint | D Ident-only, s0 / s1 | -3 / +5 | -4 / +7 | -4 / +8 |
| joint | D DET, s0 / s1 | -2 / +1 | -2 / +1 | -2 / +1 |
| joint | verdict | fail | fail | fail |

No verdict changes. The reason of each fail stays: refit fails on seed 0 forms (D -13 against a band of 5 to 7) and on Ident-only not up; joint fails on seed 0 forms (D -24 or -25 against a band of 18) and on seed 0 Ident-only not up. The one flip is refit seed 1 forms (ok to fail) under the lower bound, because the band stays 5 and D moves by one. Under the upper bound the band grows to 7 and that seed stays ok.

The effect is the same in both arms and seeds: the expansion adds 16 to 25 forms per arm and seed, the arm and the bundle gain about alike, and D moves by 0 to 4. Where it moves most (joint seed 0, -21 to -25) the bundle gained 3 to 4 more forms than the joint arm.

## Frontier stuck roots

`frontier/ready.tsv` of the refit run (bundle jobs, 110 ready forms per seed). Stuck roots are the rows with `nreads` 0: 40 (seed 0) and 44 (seed 1). The expansion uses the same bundle job's cover lines.

| | seed 0 | seed 1 |
|---|---|---|
| stuck roots | 40 | 44 |
| covered once expanded, lower | 9 | 9 |
| covered once expanded, upper | 9 | 9 |
| still stuck | 31 | 35 |
| ready forms with reads | 70 | 66 |
| of those covered once expanded (lower to upper) | 4 to 9 | 5 to 8 |

The 9 are the same in both seeds, and all 9 are certain (no ambiguity): aa4ec2a5 g4, g9, g10; dfadab01 g4; db695cfb g25; 135a2760 g1 and g8; b99e7126 g1 and g8. The last four were not in the hand read, which covered only forms under 8 bits (these have 12.3 and 13.6 bits). So 20% (9 of 44) to 23% (9 of 40) of the stuck roots were an artifact of the cover check. The ready forms with reads that get covered also make their dependents ready; the recount does not follow that.

## Limits

- The map is from the Mac engine with seed 0. The pod engine can give another table for a form where the Mac engine gives a different key (the hand read had the same limit).
- Keys use `hash()` of tuples, so two forms with equal tables get one key and different tables almost surely do not; a hash collision would join two different tables, and the map would show it as a duplicate.
- The recount covers `.cover` (the pinned gold, `points-eval.json`). The `.cover2` lines (cheapest gold) were not recounted.
- The recount assumes that the search would have run the same: a covered node is unchanged by the fix, and no pick reads a cover line. It sizes the measurement change, not a change in search.
