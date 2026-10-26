# Dev learning test of the binding

## Question

On real tables, does the encoder learn to read bound values? The test reads the training records' loss of the hidden Color and Ident fields whose binding key finds the true value, against chance. These are the `key_hit_exact` and `key_hit_inexact` parts of `row_target` under `by_source_rows`. If those fields do not fall below chance on the programs the model trains on, a run at full scale cannot show more. This test is small, on the dev export, and runs on the A100 because a CPU step takes 20 to 30 s against about 1.3 s there.

## Settings

Code: the enc-bind worktree at commit 287caf3e (/Users/davidlu/code/arc-workspace/.worktrees/enc-bind). It is not on master. Data: work/tables/dev (loader version 21, 10 tasks) and the worktree's lm/data-dev; the loader cache rebuilds on the pod in seconds.

Run A, with the binding:

    OMP_NUM_THREADS=16 MKL_NUM_THREADS=16 python -u lm/pretrain.py --data lm/data-dev --tables work/tables/dev \
      --out runs/bind-dev-on --steps 300 --eval-every 25 --device cuda \
      --mask-remote-groups --enc-ptr-equality --enc-parent-bias 4 --enc-bind --enc-bind-dim 2048 --enc-per-example

Run B, the control: the same command with `--out runs/bind-dev-off` and without `--enc-bind --enc-bind-dim 2048`. B runs only where A's key-hit parts fall below chance, as its own unit after A's result.

Each run is bounded at 1,800 s.

## Decision rule, fixed before the run

Read the `train` records of the last two evaluations (steps 275 and 300) of each run. Under `by_source_rows`, buckets 1-50 and 51-200, take Color and Ident `row_target`, the `key_hit_exact` and `key_hit_inexact` parts, and compare `group_loss` with `group_chance_loss`.

| A, key-hit parts | B, key-hit parts | reading | next |
| --- | --- | --- | --- |
| within 0.05 of chance | not run | the binding is not learned on real tables | design; inspect the reads on the dev fields |
| at least 0.1 nats below chance in 1-50 for both types | within 0.05 of chance, and A at least 0.1 below B | the binding is learned on real tables | the full-scale run, for held-out programs |
| at least 0.1 nats below chance in 1-50 for both types | below chance by as much as A | the drop is not the binding | inspect what B learns from |

The other parts (`key_hidden`, `key_miss`, `no_read`) are read as context only.
