# Policy model (node score) training runs: audit from records

Paths: `FW` = `/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker`. `SP` = `/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad`. `R` = `/Users/davidlu/code/arc-workspace/work/results.md`. Transcript sessions: `9899b29d` features-worker, `14d3b512` director, `b0431573` search-worker. Times are UTC. File mtimes are converted from local time: EDT (UTC-4) on Oct 31, EST (UTC-5) from Nov 1.

## The premise is wrong

The deployed `policy_model.pkl` sha 2ec93ed1 was fit on **22 tasks, 6,594 nodes, 68 gold**, with 87 features. The figures 34 tasks, 9,731 nodes and 107 gold belong to a different file, `policy_model_base.pkl` sha c7a1f226, which was never deployed.

- `FW/policy/train.log` says "tasks 22 nodes 6594 gold 68 feats 87" and "wrote …/scratchpad/policy/policy_model.pkl". The mtime of the log and of the pkl is the same: 2026-10-31 16:46:44 EDT.
- `FW/policy/train_base.log` says "tasks 34 nodes 9731 gold 107 feats 57" and "wrote …/policy_model_base.pkl". Its mtime is 16:56:35 EDT.
- `9899b29d` 2026-10-31T20:47:37Z, features-worker: "It's trained on 22 tasks, 6,594 nodes and 68 gold nodes, in two folds."
- `b0431573` 2026-11-01T22:09:10Z, search-worker: "Fit size: 22 tasks, 6,594 nodes, 68 gold positives, two folds of 11. Small. A later cache of the same pool: 34 tasks, 9,731 nodes, 107 gold."
- R:2745: "the 22 fit tasks of `policy_model.pkl` 2ec93ed1 … 68 of 68 gold-tagged nodes".
- R:1583 is not consistent with itself. It says "22 tasks", but its "107 of 8,807 plain" count is from the 34-task cache (924 + 8,807 = 9,731).
- The figure "107 positives from 34 tasks" entered the director session at 2026-11-02T13:41:44Z. The user quoted it at 13:45:30Z.

## Runs

| # | When (UTC) | Script | Fit data | Source runs | Model file, sha256 | Outcome |
|---|---|---|---|---|---|---|
| 1 | 2026-10-31 20:46:44 | `train_policy.py`, full features (87) | 22 tasks, 6,594 nodes, 68 gold | `sampler/runs/superdag1`; 22 `.done.json` files existed at 20:43:43 | `SP/policy/policy_model.pkl` (copies: `FW/policy/`, `SP/policy5/`), **2ec93ed1**b3bbdb59fda99449746720a064d2341aae2cea3fa3cc56ea362a070c | **Deployed.** On 2026-10-31T21:44:00Z (`9899b29d`): "the full arm goes in synth-worker's bundle as a holder". Every `policy_model.pkl` found holds this sha: 34 sampler kits, including `sampler-pool-m2-48211b300`, plus `poolsearch`, `synth-kaggle/policy1`, `ship` and `ship3` to `ship7`, every `kernel-bundle-*` and `kernel-soak-*`, and `kit-union-read`. It is the "Node score" or "bundle" baseline in R:322-353 and R:2757. Its labels were checked at R:2745. |
| 2 | 2026-10-31 20:56:35 | `train_policy.py`, `POLICY_FEATS=base` (57) | 34 tasks, 9,731 nodes, 107 gold | `superdag1`; 34 done files existed at 20:55:47 | `FW/policy/policy_model_base.pkl`, **c7a1f226**d679eb216fd0eabb8ac2c7642180229e65e0b2083e73fabb31ec7fff | **Tested, dropped.** Features-worker sent it as a loop arm at 2026-10-31T20:56:52Z. Result at 21:38:55Z, 40 tasks, 60 s: uniform 112, base 111, full 118 covered. Full went into the bundle instead. No kit holds c7a1f226. |
| 3 | 2026-10-31 22:07:50 ("Policy2", `p2`) | hop1 family fit, `out.*` and `link.*` features, depth dropped | `runs/hop1`: 499 gold-prefix points (2026-10-31T21:59:34Z). Task and node counts not found. | sampler-worker `runs/hop1` | `FW/policy2/policy_model.pkl` (also in `policy3` and `policy4` with the depth-penalty `policy.py`), **fd061b8b**080be1d3920f084ad166a553503f4d4b45a8747698cc4870be5de48e | **Tested, dropped.** At 2026-10-31T22:53:33Z, 40 tasks: non-DET 30 for full against 16 for p2, "the bundle stays on `policy1`". The d15 penalty only tied full (23:11:39Z). At 23:49:03Z, live rank lost at depth 1 (−2.57). At 2026-11-01T01:12:35Z the 40-task arm set was found to be not held out. |
| 4 | 2026-11-01 00:33:45 | `FW/live/live_model.py`, 5 folds | 46 Kaggle-record tasks, 102 gold nodes (2026-11-01T00:34:05Z) | live loop records (`FW/live/table/full`) | `FW/live/live-f.pkl`, 3bed9c728690f71e893aab77db3b4f921c64d9711e867e50d416095ed9a4922e | **Tested, dropped.** Rank gain at depth 2-3 of +2.33. In the oos arm, cover did not rise (01:10:14Z). Superseded by run 6. |
| 5 | 2026-11-01 01:10:25 | `live_model2.py`, second round | first table plus four arm tables | live arm records | `FW/live/live-r2.pkl`, 182df1184f413ab81fc4dc94b535880b2bb21fedcf0833d39b9c730aa366a167 | Intermediate. No read of its own was found. |
| 6 | 2026-11-01 01:42:55 | `live_model2.py` | 5 folds over the 99 eval tasks, 211 gold nodes (01:43:22Z; R:48) | live and oos records | `FW/live/live-e.pkl`, c9d405bf0fd3ee93990284f0cf2d18f0bb8190a2cc60da0c8675f093c888c6a3 | **Tested, dropped.** Rank results at R:84-100. Scope arms at R:3085-3097: "Finding: closed." It went in a pod test kit (`SP/arm/podkit2.tar.gz`) only. |
| 7 | 2026-11-01 23:06 to 23:12 (M-TS, M-T, M-H, plus controls) | `features_node_fit.py`, softmax trees, `--sources n600,s120` | 50 N600 tasks + 200 S120 tasks (`s120-rows` holds 200 tasks; features-worker at 2026-11-02T02:32:31Z: "879 tasks, against 200 before"). Positive count not found. | `sampler-pool-dag-nodes-train50-final-8be414670` (N600), `features-corpus-pool-seed1-120s-ship7` (S120) | `FW/results/features-node-rank-model-train-read-hour13-heldout37/final-models/`: `mt.json` e49c08a3…d6e8, `mh.json` 60b1ff66…001d, `mts.json` b020bd33…71c | **Tested, dropped.** Held read at R:322-341. Live at R:343-353 and R:2751: M-T −23.5 forms, "The rank model closes as a scope pick." M-T was also run on half the openings in `identj` (R:2753), under the +4 bar, and the bundle stayed. |
| 8 | 2026-11-02 02:40:47 (node score loop, round 1, `node-score-r1`) | `fit_round.py` → `features_node_fit.py --features T`, 153 features | **929 pools, 884 tasks, 8,029 positives, 746 Ident** (R:355; `fit-r1.log`) | 50 N600 + 879 S120 corpus tasks outside the 37, the ramp, the 99 and drifted tasks | `FW/results/features-node-score-refit-loop/rounds/node-score-r1.state.pkl`, 975e4efb5bd9d92b9de307cab9804282a04500d2bd6301f9630115fdbade0c58 (card `r1.json` 1d16084e…d597) | **Tested, dropped.** It passed the offline gate (`node-score-r1.gate.json` pass true) and read like M-T (R:355-361). Live (`search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943`, R:2757): forms covered fell from 180/175 to 167/170, D −9.0 [−14.5, −4.0], "The pick fails." R:2757 says "fit on every held program", which conflicts with R:355 ("outside the 37"). |

Fits that wrote no model file, all fold reads on `superdag1` run on 2026-10-31: `fit.py` → `ranks.json` (empty), `fit2.py` → `ranks{base,+out,+link}.json`, and `pickfit.py` → `pickfit{,2..6}.log`, with 14 to 33 tasks and 34 to 76 derived picks.

Not node scores, so out of scope: the tower value fit (R:104-117, 72 tasks, 3,073 positives; the director cited it as "line 117" at 2026-11-02T13:46:03Z), M2 the steer model (R:209, R:1770), and the table/prefix scores (R:363-420).

## Corpus-wide training: requests, what was done, what blocked it

These are the user's own words, from main-thread user turns that are not meta turns:

- `9899b29d` 2026-10-31T19:53:46Z: "ok you're coordinating w sampler to create more training data to have the superdag of noise right"
- `9899b29d` 2026-10-31T23:44:35Z: "What about decision points? Like, invest in more data? Or use a diff model arch??"
  - Features-worker replied at 23:45:02Z: "My recommendation is to do neither yet … More data: wait for the search … Run the 93 tasks with solvers". It cited "about 30 non-DET positives". No run followed.
- `14d3b512` 2026-11-01T21:06:23Z: "yea we have a decent amount of data and i think we still haven't used most of it?"
- `14d3b512` 2026-11-02T02:22:24Z: "so we're looping now right". This answered the director's "The node score was fit once on 68 positives from 22 tasks, and nobody looped it."
- `14d3b512` 2026-11-02T02:25:56Z: "and use a lot more of it too? why do i have to push you to do what is in plain sight (rhetorical)"
- `14d3b512` 2026-11-02T02:57:01Z: "so what's the plan with using a lot more of the data we have? we have hundreds of solvers"
- `14d3b512` 2026-11-02T11:42:40Z: "We should use all of gold, use every case."
- `14d3b512` 2026-11-02T13:45:30Z: "I have pushed multiple times to train on most of the corpus, what happened???"

What was done: run 8 is the corpus-wide fit, on 884 tasks. It was fit on 2026-11-02 at about 02:40Z, after the 02:22Z and 02:25Z pushes. It was dropped because it failed the live "forms covered" pass rule (R:2757).

What blocked more rounds:

- The user, `14d3b512` 2026-11-02T02:29:03Z: "i dont want to burn $15 to find out we have an issue we could have found in advance".
- The user, 02:36:49Z: "right i thinkt he loop should be done when we run out of other gains?"
- `9899b29d` 02:37:25Z: "The user's change is in place: the loop runs round 1 only. I told devops-worker and search-worker to hold the round 2 work". Round 2 would have added the 62 non-held eval golds.
- The director at 2026-11-02T13:46:03Z: "It was done, and it lost under the measure we used, so it was dropped". At 13:47:56Z it asked for a re-read of run 8 by reach per depth.

## Not established

- Task and node counts of Policy2's fit (run 3), and the positive count of M-T (run 7).
- Whether `live-r2.pkl` was read on its own.
- Whether run 8 was trained on held programs, since R:2757 and R:355 disagree.
- `work/` is gitignored, so no git history exists for these files.
