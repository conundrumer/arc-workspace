You are the n-study owner in the LM data study. Read the plan first: lm/study/plan.md, most of all Goal, Pipeline (Features and Study pipeline), Labels and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study.

## Goal

The study the plan's step 3 describes: features of a proposed clause and its table at a branch point, fit against the grades, with the learning curve, feature importance and the hypothesis test on held-out tasks. The user reviews it by reading its report and samples of examples with their features and grades.

Many distinct, independent features are the aim. A feature is worth adding when it separates valid tables from Reject in a way the existing features do not.

## Inputs

- The grades: S/ast/run/mech/labels.sqlite3, one record per pair. The labeler is still writing it, and a second pass and the judge add grades later, so the study reads it again on each run. lm/study/codex-adm/briefs/judge-decisions.md defines the grades; n-mech owns the labeler and the grade.
- The pairs, their clauses and their tables: the corpus records each label record names.
- Gold's own clause at each point is scored on held-out tasks for the path test, and is not a training example.

## References

- S/reasons/features2/ (featurelib and rounds 2 to 5) and S/reasons/study/pipeline.py: earlier feature extraction and fits, built for judge labels that are now deprecated. Keep what serves the goal.
- S/codex-adm/handover-n-features.md, handover-feat.md and handover-reasons.md: the earlier owner's open items. The items about judge batches and per-pair judge labels are obsolete.

## Your work

You own S/reasons/. Produce a first report on the grades present now, then extend it as grades land. Every count states what is absent, as Labels in the plan says, and how many pairs are unknown or still open.

## Rules

- Message owners with lm/study/codex-adm/send.sh <owner> <request id> <text>, request ids from 9700 upward, one per message. The owners are in S/codex-adm/owners.txt.
- Start your final answer with COORDINATOR: when you need the coordinator: a command your sandbox blocks (such as /Users/davidlu/code/arc-workspace/scripts/run_heavy.py, which every run longer than a minute goes through), or a decision outside your area.
- Run no tests.
- When you stop, write your open items to S/codex-adm/handover-n-study.md.
