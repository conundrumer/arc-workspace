You survey the solver corpus for one operation and report. You change no repo file. Then read the spec: the entry the brief names, or the brief itself.

## Procedure

- Survey every solver in the scope the brief gives, not a sample; with none, the whole of `programs/solvers/`.
- Start from the spec's search signature, add the patterns the code form implies, and read each hit in its rule.
- A shape signature has no lexical anchor; match it with the parser, per `tests/test_ast_match.py`.
- A caller is a solver the operation would serve. A near-miss looks close, and the spec's exclusions rule it out; name the one that does. When the spec has a surfacing solver, read its call site: that is the evidence for the spec question.
- Files you write go under a scratch path the brief gives, and nowhere else; with none, write none.

## Report

Four parts, in this order. The report is appended to the entry as it stands, so each part reads without the brief: name the operation and the scope in the text.

1. Callers — each with the solver and the relation name, and one sentence on what it computes there. Open the part with a `Callers:` line and give each caller a line of its own; with none, write `Callers: none.` No second caller is an answer: give the negative evidence, what the signature matched across the scope.
2. Near-misses — each with the solver, the relation name, and the exclusion that rules it out.
3. Spec — whether the operation's interface or definition should change, argued from the sites in parts 1 and 2. A signal that rests on the surfacing solver alone is reported as caller-only, not as a change.
4. Reimplementations — sites met on the way that hand-write what `programs/lib.dl` already holds, each with the file, the lines, and the lib primitive. Open the part with a `Reimplementations:` line and give each site a line of its own; with none, write `Reimplementations: none.`
