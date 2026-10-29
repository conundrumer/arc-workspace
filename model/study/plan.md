# Plan: negatives of the decode's own kind

## Goal

Good negatives for the data study: wrong clauses near gold, with clean labels, in volume. With them, the study finds features that separate a clause that adds signal from one that does not. Diversity of features is a goal: many distinct, independent features, not one strong score.

Hypothesis: at each branch point, the set of valid tables is small, so a classifier that keeps the valid tables and rejects the rest makes the search short enough to solve the task. A valid table is one on the path of some case of the task, so the search must keep the path of at least one case, not gold at every branch point of one case.

## Pipeline

Study code and documents are under `model/study/` in each repository worktree. Data paths are relative to `/Users/davidlu/code/arc-workspace/work/lm/data-study`, resolved by `study_paths.DATA_ROOT` through `engine.checkout.main_worktree`. Source paths stay relative to their modules. Run output, reviews, reports, patches and handovers are data: they go under the data root, never under `model/study/`.

- **Engine** (branch `master` of the repo). A Codex thread's change gets its own worktree from `scripts/change_worktree.py --name <name>` and lands on `master` only through `scripts/merge_change.py`, which runs the repo's merge checks. The worktree `ast/engine` follows `master`, detached. A build is made only from a commit, with `scripts/build_study_runtime.py --revision <commit> --output run/runtime-<commit>`, run through `run_heavy.py`.
- **CURRENT** (`ast/run/CURRENT.json`) names the build and the corpus directory that the corpus run and the checks use. It moves to a newer build once that build's fault replay is no worse than CURRENT's, record by record.
- **Gold.** Gold programs are converted from the Souffle solvers in `programs/solvers/`. Every stored parameter has a determination in its solver, and conversion verification and the LM export admit a program only when the native determination end check gives each stored value exactly.
- **Mutator.** A mutation point is a clause of a gold program. A mutant changes K atoms of its body, by substitution or deletion, from domains that keep the whole program valid. `evaluate_pair` gives both clause tables under each DET assignment, the assignment gold keeps, the rest of gold's program run with the mutant clause through OUT, and an explicit status (complete, stopped at a work or memory bound, fault).
- **Corpus run** (`ast/run/corpus.py`, output the corpus directory CURRENT names). For each task, case, point, K and operation, it draws, evaluates and filters, with a quota per bucket. Every pair is recorded, kept or dropped, with its filter results and rejection reasons. A disk guard stops the run at 30 GB free, and the run resumes from the task directories present.
- **Checks.** The fault replay (the build's `checks/check_study_pair_corpus.py --tasks engine/data/tasks` on `stage3-fault-replay.json`) replays the historical fault cases on a build. `fault_status_diff.py` compares it with CURRENT's replay record by record and leaves out changes a Deadline stop explains, since Deadline stops vary with machine load. The kept-stream check (`ast/run/check_kept_streams.py`) follows the corpus run and reads back each stored mutant stream.
- **Filters.** A filter classifies a pair and does not drop it: a mutant table that is empty, equal to an available table, or with no dependency path to OUT, gets that class as its label. A mutant table equal to a target is `equivalent`. A pair whose filter cannot complete is unknown.
- **Mechanical labels** (`ast/run/mech/`). Each pair gets a grade from the row comparison and a witness search, in passes over the corpus records: the base pass searches selections and projections of the mutant table X with semijoins and antijoins against the available tables, and a second pass adds lib relations on the pairs it leaves without a witness. Records are written per pair and resume.
- **Judging.** A judge sees the pairs the mechanical labels leave open, writes recovery and continuation clauses, and a tool runs and checks each clause in the engine. The judge's document is rendered by `judge3/`, and its tool is `judgetool/`.
- **Specification.** `codex-adm/briefs/judge-decisions.md` specifies the labels and the judging.
- **Features.** A label may use any evidence, gold's later clauses, other cases and the test outputs included. A feature uses only what the search has at the branch point: the inputs, the train outputs, the tables built so far, the proposed clause and its table. Each mutant is one example, labeled with its table's grade and weighted by one over the number of mutants at its point that give the same table.
- **Study pipeline** (`reasons/study/pipeline.py`). It fits the valid grades against Reject, with folds held out by task, results broken down by operation and K, a learning curve over judge label count, and feature importance. Counts of valid tables are per branch point, after merging edits that give the same table there; a table passes when any of its mutants passes.

## Labels

The specification defines the grades. The valid grades are the grades above Reject. Every count states that mutants slower than the corpus deadline are absent, and that the tasks a251c730, a2d730bd, a32d8b75, a416fc5b and a47bf94d are absent: their corpus runs were stopped for their run time and load.

## Working rules

- Every script streams results and prints progress over time (done/total, elapsed, rate), so an ETA can be read from its output.
- A script that is not near-instant gets its performance pass in its first version. A performance pass removes wasted work first, then uses any computational or algorithmic means.
- Work is done only for what consumes it: a check covers what the study uses, and rendering covers the pairs that judges see.
- No step waits on another that can run alongside it, and every wait has a trigger.
- A fault is fixed at its root cause, so that the class of fault cannot occur again: the fix states the class and every place its condition arises, and removes the condition or makes it a checked error where it arises.
- Code that a change touches and that has a duplicate elsewhere is made one implementation in the same change. The thread that makes the change finds the duplicates by searching the code; `duplicates.md` lists the known ones.
- Each Codex thread owns one code area, so that most changes need no coordination; `codex-adm/owners.txt` lists the owners. An area with no owner gets a new thread. Threads whose areas overlap send each other their plans before they edit, and agree who changes what.
- Codex threads message each other with `model/study/codex-adm/send.sh`, which steers a running turn or starts one. A thread that needs the coordinator (a merge, a worktree, a commit, a command its sandbox blocks, a decision outside its area) starts its final answer with `COORDINATOR:`. A thread that stops writes a handover note of its open items to `codex-adm/handover-<name>.md`.
- No test runs unless running it is the work itself.
- A new engine construct, such as a determination mark, needs the user's approval.
- An agent's instructions hold only what evidence shows its reader needs.

## Plan

1. **Label the corpus mechanically**, and fix each class of fault or unknown it reports.
2. **Judge the open pairs** that the search cannot decide, with the judge's tool, after a trial whose clauses verify.
3. **Grow the features** as labels land, and run the study pipeline on them. The learning curve sets how many judge labels to collect. On held-out tasks, report the hypothesis test: the share of tasks where some case keeps its path, and the count of tables passed per branch point.

## Decision points

- **How many judge labels.** Set by the learning curve.

## Deferred

- **v11 records cut short by the bounded export.** The audit counted 14 of 59,528 v11 records with gold body Count entries. Check every v11 record for any form of cut row set from the bounded export, then regenerate the affected records under `5ee2f066` or exclude them.
- **Corpus directory per CURRENT move.** A move should regenerate only the records whose output the new build changes, as its fault replay and audits find them.
- **Corpus source guard.** The corpus commands run through `corpus-v9/source-guard/guard_corpus.py`, which no longer exists. Recover it from the patch in `codex-adm/out.ndjson` before the next corpus run.
- **The set of valid tables at a branch point.** Mutants are the edits that survive the filters, not the candidates a search proposes, so they do not measure the size of the set. Labeling every proposal of a decoder at a sample of branch points would, as far as the proposals cover the set.
- **Mutants in normal form.** The next corpus run's mutator draws only edits that keep the program in the normal form the writer's `normal` check tests, so the quotas fill with normal mutants.
- **Other DET assignments.** The mutant is evaluated only at gold's kept assignments. Evaluating a sample under every candidate assignment measures how often X is on a path only under another one.

## Parked

- The writer track (first-choice ranker, eager closure): it writes gold's clause at few points, so its negatives teach little.
- Summary features of large tables.
- The Haiku trials belong to the haiku-runner session.
- Performance stops and faults the corpus finds, beyond those that block the run: their cases stay in the corpus records.
