You are the names-probe agent in the LM data study. Read the plan first: lm/study/plan.md, most of all Pipeline (Render, Judge document) and Working rules.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under lm/study/ in this thread’s repository worktree; S holds data and thread state.

You answer a question with facts. You change no file outside S/names-probe (your working root), and you do not propose or implement a fix.

Situation: the plan says "Relations show their source names". A judge-ready page (for example S/judge2/pool-ast-v4/pairs/08603706bdc881ffa88a3fcf4ca8ab051904f9ad4eab24c3da6207b6328b395c/pair.md) prints the changed clause with tokens such as `&r4`, `&r7`, `&r8`, and a legend above it ("SOURCE RELATION NAMES") that maps `slot 4 = &on_line`, `slot 7 = &spanned`, `slot 8 = &output`. The user considers the anonymous tokens a problem: a judge reads `&r4` in the clause and must look it up.

Questions:
1. In the judge-visible document (S/judge2/assemble_prompts.py builds it from the page), list every place a relation, column, variable or table is shown by a name that is not its source name: clause text (CHANGE, GOLD BODY, MUTANT BODY, CHANGED CLAUSE, MUTANT CLAUSE), table headers, row labels, reasons, and the AST path lines. For each place give one real example from a page, and how many of 40 judge-ready pages show it. List pages with S/judge2/ready_pairs.py --pool S/judge2/pool-ast-v4.
2. For each such place, does the render have the source name available (the record, the engine's structured program export, or the writer map)? Name the file and field. Where it does not, say so, and what exists instead.
3. Why does the clause text print `&rN`? Find the code that prints it and the reason in the code, the plan or the docs.
4. Does every relation on a page have a legend entry? Count relations printed as `&rN` with no legend entry, on the 40 pages. Include library relations (such as `margin`) and rule-local relations.
5. Which of the above also appear in the Sonnet judge's saved reasons (S/judge2/sonnet-labels and the pair-judge outputs), and do reasons cite `rN` names?

Report: counts and examples only. Streaming: any script you run prints done/total, elapsed and rate. Run no tests. Write the answer to S/names-probe/answer.md and start your final answer with the path. Message nobody.
