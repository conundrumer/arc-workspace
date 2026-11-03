# Pool against clock: run spec

## Question

Inside a right scope, does the cover rate per try fall with the pool's size or with time in the job? In two reads, log pool size gave x0.53 and x0.71 per e-fold with the uncovered form's bits in the fit, but pool size and time correlate .78 to .86 in every run so far. This run makes the pool large from the start, so that at equal time the two arms differ in pool size by a large factor.

## Arms

- `empty`: the bundle as it runs today. The pool starts empty.
- `loaded`: the same lines, with the worker's bank file present at start. The worker reads a bank file at start where one exists (`read_bank` in `kaggle_worker.py`), as it does after a renewal. The bank is the end bank of the same task from round 1's bundle at the other seed: `bundle_s1`'s bank for the seed 0 line, and `bundle_s0`'s for the seed 1000 line. That gives about 2,000 to 3,400 nodes at 0 s against about 50 for `empty`.

The two arms share the kit, the models, the settings, the seeds and the pod of each task.

## Kit

`kits/search-pass-r1-kit-0729e4943.tar.gz`, with `FIRST_PASS_SECONDS` unset, so both gold-key patches are in, and with a bank save at the job end added as in the recency kit. The `loaded` lines copy their bank into `ARC14_ROOT` before the worker starts.

Points to check in the kit before the request:

1. `read_bank` restores the bank's forms and nodes, and the policy's uses, with no cover event for them. If it emits covers at load, the read drops cover lines before the job's first picks line.
2. The loaded bank's covered gold forms are known from its source run. The read counts only gold forms uncovered at the opening, so a form the bank already covers is never a right form.
3. The renewal share and memory limit hold at the larger start: a loaded pool of 3,400 nodes must stay under the worker's RSS limit of 2,888 MiB, with room to grow.

## Size

The 37 held-out tasks, seeds 0 and 1000, 2 arms: 148 jobs at 300 s wall. The effect sits in the first 300 s, where the pool ratio between the arms is largest. That's about 13 CPU h, about $0.90 at the last rate. A task's 4 lines share one pod.

## Stop rule

The run is a diagnostic, not a candidate, so the forms stop at 60 s doesn't apply. A failed check line or a crash of the check stops the round, as in the loop. The 60 s read reports, for each arm, the right tries and covers so far, and the round goes on.

## Logged

- `.picks`: `n` (scored nodes, which is the pool size), the picks, the draw and the time, on every opening.
- `.visits` with `SEARCH_LOG_VISITS=1`: the scope's `fids`, the kind, tries and new nodes.
- `.cover` with time and node.
- The bank at the job end, so every node of a cover is in it.
- A line at start in the `loaded` arm: the bank's node count, form count and covered gold forms.

## Read

Right-scope rows as in `runs/search-joint-r1-heldout37-2seeds-600s-0729e4943/variety/` and `runs/search-pass-r1-heldout37-ramp22-2seeds-600s-0729e4943/pool-clock/`: an opening whose scope holds the read of a single-read gold form uncovered at that moment. The fit is binomial with a complementary log-log link, an offset of log tries, standard errors clustered by task, with bits, the arm, log pool and time as terms. Report the rate ratio `loaded` over `empty` at equal time in 0 to 100 s, 100 to 200 s and 200 to 300 s, and the correlation of log pool with time, which should be well under .5.

## Prediction

At 50 s the pool is about 2,500 nodes in `loaded` and about 700 in `empty`, so log pool differs by about 1.3.

- If the rate follows the pool: the `loaded` rate per right try at equal time is x0.45 to x0.65 of the `empty` rate in 0 to 100 s, and the gap narrows toward x0.8 by 300 s, as the empty pool grows. In the fit, log pool stays at x0.5 to x0.75 per e-fold with time in, and time is near x1.
- If the rate follows the clock: the ratio is x0.85 to x1.15 in each window, and time takes the term.

Decision: a ratio in 0 to 100 s whose 90% interval lies below .85 says pool. An interval that holds 1 and lies above .7 says clock. Anything else is not settled, and is reported as such.
