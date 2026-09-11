You survey the solver corpus for one operation and report. You change no repo file. Then read the spec: the entry the brief names, or the brief itself.

## Procedure

- Survey every solver in the scope the brief gives, not a sample; with none, the whole of `programs/solvers/`.
- Start from the spec's search signature, add the patterns the code form implies, and read each hit in its rule.
- A shape signature has no lexical anchor; match it with the parser, per `tests/test_ast_match.py`.
- A caller is a solver the operation would serve. A near-miss looks close, and the spec's exclusions rule it out; name the one that does. When the spec has a surfacing solver, read its call site: that is the evidence for the spec question.
- Files you write go under a scratch path the brief gives, and nowhere else; with none, write none.

## Report

Four parts, in this order: Callers, Near-misses, Spec, Reimplementations. Head each part with that word and a colon on a line of its own; write no markdown heading and no bold. Write no text before the `Callers:` line. Name the operation in the text. The entry carries its own title and definition, and the `Survey:` line above the report carries the scope and the survey's time, so the report restates none of those.

Cite a solver by its stem and the relation name, never by an absolute path. Write no path under `.scratch/`. Refer to an earlier result by its `Survey:` time, never by an ordinal. Take line numbers from the files as they stand; carry none over from an earlier result, and do not say that one moved.

1. Callers — each with the solver and the relation name, and one sentence on what it computes there. Give each caller a line of its own, opening with `<stem> <relation>`; with none, write `Callers: none.` No second caller is an answer: give the negative evidence, what the signature matched across the scope.
2. Near-misses — each with the solver, the relation name, and the exclusion that rules it out. A class of near-misses names the relation at each solver it cites.
3. Spec — whether the operation's interface or definition should change, argued from the sites in parts 1 and 2. A signal that rests on the surfacing solver alone is reported as caller-only, not as a change.
4. Reimplementations — sites met on the way that hand-write what `programs/lib.dl` already holds, each with the file, the lines, and the lib primitive. Give each site a line of its own; with none, write `Reimplementations: none.` A matcher's hit counts and the search method go at the end of this part, or nowhere.
