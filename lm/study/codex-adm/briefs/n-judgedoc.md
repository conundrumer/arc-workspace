You are the n-judgedoc owner in the LM data study. Read the plan first: lm/study/plan.md, most of all Goal, Pipeline and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. P is /Users/davidlu/code/arc-workspace/work/lm/data-study/ref/progsynth-relabel, a copy of another session's work.

## Goal

A renderer for the judge's document. The study labels pairs mechanically; a pair the mechanical pass leaves open goes to a language-model judge. The judge decides whether the mutant's table X keeps gold's information, and writes one arclog clause that recovers gold's table G from X and the tables available at that point, or says none exists. The engine then runs that clause as written and compares it with G.

The document must let the judge see that directly: what X keeps and loses against G, what the readers need, and what tables are available, under names a clause can use. It must not show test outputs.

## References

- The study's renderer, S/judge2/render2/, with S/judge2/assemble_prompts.py.
- The other session's renderer, P/render_pair.py, with its judge brief P/judge-brief.md.
- P/calibration2-report.md: the faults the judges and the engine found in P's documents, and the clause refusals.
- S/render-design/design.md and example-after.md: a review of render2 against the judge's decision.
- S/names-probe/answer.md: where render2 shows names that are not source names, and where the source names are.

P belongs to the other session: read it, write nothing there.

## Your work

You own S/judge3/ (empty). Write the renderer there. The pairs to check it on are P's 55 calibration pairs (P/calibration2.json).

## Rules

- Message owners with lm/study/codex-adm/send.sh <owner> <request id> <text>, request ids from 9800 upward, one per message. The owners are in S/codex-adm/owners.txt.
- Start your final answer with COORDINATOR: when you need the coordinator: a command your sandbox blocks (such as /Users/davidlu/code/arc-workspace/scripts/run_heavy.py), or a decision outside your area.
- Make no judge call. Run no tests.
- When you stop, write your open items to S/codex-adm/handover-n-judgedoc.md.
