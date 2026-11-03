# Partial read, 08:30 EST

First read, 100 bootstrap draws. Tasks read: all 384 task and arm rows on cheap observables, all 236 rows with node records on table observables. Done 236 of 236 table rows. Target read: 79 of 79 tasks that have gold in the census list.

- Target: census refit at 8a5ffec60, gold of `arm/points-eval.json`, parents context, 37 held tasks plus 42 evaluation tasks added by the same walk.
- Under 25 bits: 0 positive tasks of 79. Among the 65 tasks with every form drawable, the lowest worst form is 32.1 bits, on 1818057f. The four other census row sets on the 37 also give 0 positive tasks. AUC on that bar can't be read.
- Substitute target, declared in the manifest before the read: worst form in the lowest third of tasks, at or under 81 bits, undrawable negative. 22 positive, 57 negative.
- Pooled, 79 tasks, 7 arms. Each cell: Spearman with total bits, AUC on the substitute target.

| Time | Best no-gold observable | Joint | Grid area | Forms covered (needs gold) |
|---|---|---|---|---|
| 60 s | shape forms, -.27, .68 | .55 | .51 | -.15, .58 |
| 300 s | shape forms, -.30, .72 (.55 to .86) | .64 | .51 | -.27, .67 |
| 600 s | shape forms, -.30, .70 (.57 to .83) | .65 | .51 | -.29, .69 |

On the 37 alone, grid area reads .70 on the substitute target and no pool observable passes it. Intervals are wide: 6 positive tasks there.

The soak's records in the helper read are Kaggle version 5, not `kernel-soak-8a5ffec6`: that read's labels hold 753 nodes for 135a2760, which matches `runs/kaggle-v5/record`. Both are read here.
