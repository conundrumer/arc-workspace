You are the render-design agent in the LM data study. Read the plan first: model/study/plan.md, most of all Goal, Labels, and the Pipeline items Render and Judge document.

S is /Users/davidlu/code/arc-workspace/work/lm/data-study. Code is under model/study/ in this thread’s repository worktree; S holds data and thread state.

Scope: the rendering only, meaning how a judge page and the judge document print facts that the record and the engine export already hold. The code is S/judge2/render2/ and S/judge2/assemble_prompts.py. You do not change or propose changes to the engine, the corpus run, the pool follower, the code labels, the held rules or the native readers.

Goal: a judge reads one page and labels the pair correctly. Every fact the judge reads is printed in a form the judge can read directly. The plan says relations show their source names and values are decoded for reading.

Observation: on judge-ready pages (list them with S/judge2/ready_pairs.py --pool S/judge2/pool-ast-v4; for example S/judge2/pool-ast-v4/pairs/08603706bdc881ffa88a3fcf4ca8ab051904f9ad4eab24c3da6207b6328b395c/pair.md) the clause text prints relations as `&r4`, `&r7`, `&r8`, and a legend ("SOURCE RELATION NAMES") above the clause maps `slot 4 = &on_line`, `slot 7 = &spanned`, `slot 8 = &output`. The user considers this a problem: the judge reads `&r4` and must look it up. Other places may have the same kind of problem. An agent that reads S/names-probe/answer.md (when it exists) has a measured list; do not wait for it.

Your job: read the code and the pages, then write a design to S/render-design/design.md and stop. The design states:
1. Every place a page or document prints a name or token that is not the thing's source name or a decoded value, with one real example each.
2. For each, where the code prints it, and whether the render has the source name or decoded value available (file and field).
3. What you propose to change, in which files, and what each page would then print (show one before and after for the page above).
4. What the change does to the render version, to the byte content of existing pages, and to judge-document size. Say what must be re-rendered.
5. What could go wrong: names that are not unique, names that collide, library relations, rule-local relations, and anything in the engine export you would need that the render does not have.

You change no file outside S/render-design. Run no tests. Any script you run prints done/total, elapsed and rate. Heavy commands go through S/ast/engine/scripts/run_heavy.py; if your sandbox blocks it, start your final answer with COORDINATOR: and give the exact command. Message nobody. When the design is written, start your final answer with its path.
