You are the n-judgetool owner in the LM data study. Read the plan first: model/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. P is /Users/davidlu/code/arc-workspace/work/lm/data-study/ref/progsynth-relabel, a copy of another session's work.

## Goal

A tool the language-model judge uses while it judges one pair. The judge writes arclog clauses that recover gold's table G from the mutant's table X and the available tables. With the tool it runs a clause in the engine, sees its table or the engine's refusal, and checks the clause against G, so that it answers with clauses that run and verify. The tool also gives the final check of the judge's answer. model/study/codex-adm/briefs/judge-decisions.md holds the decisions the tool must follow.

## References

- /Users/davidlu/code/arc-workspace/work/haiku-solve/: a tool another session built for Haiku to write an arclog program clause by clause (`solve.py`, its `guide.md` and `lib.md`, `views.py`, `tableview.py`). Take only what the judge needs.
- P/engine_verify.py and P/verify_recovery.py: the other session's after-the-fact check of a judge's clause.
- P/calibration2-report.md: the engine refusals and stops the judges' clauses met.

P belongs to the other session: read it, write nothing there.

## Your work

You own S/judgetool/ (empty): the tool, and the part of the judge brief that tells the judge how to use it. n-judgedoc owns the judge's document and the judge brief. Agree with n-judgedoc on the brief, so that it is complete and correct for the judge, and so that the document shows tables under the names the tool accepts. The pairs to check the tool on are P's 55 calibration pairs (P/calibration2.json), with the judges' existing clauses in P/labels2/.

## Rules

- Message owners with model/study/codex-adm/send.sh <owner> <request id> <text>, request ids from 9900 upward, one per message. The owners are in S/codex-adm/owners.txt.
- Start your final answer with COORDINATOR: when you need the coordinator: a command your sandbox blocks (such as /Users/davidlu/code/arc-workspace/scripts/run_heavy.py), or a decision outside your area.
- Make no judge call. Run no tests.
- When you stop, write your open items to S/codex-adm/handover-n-judgetool.md.
