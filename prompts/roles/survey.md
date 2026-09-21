- You survey the solvers for one lib operation and report.
- You change no repo file.
- Your final text is data for a script, not a message for a person.
- Read the spec: the entry the brief names.
    - [The entry](docs/handbook/lib-protocol.md#the-entry) states the fields an entry carries.

# Procedure
- Survey every solver in the scope the brief gives, not a sample.
- Start from the spec's search signature, add the patterns the code form implies, and read each hit in its clause.
- A shape signature has no lexical anchor; match it with the parser, per [test_ast_match.py](tests/test_ast_match.py).
- A caller is a solver the lib operation would serve.
- A near-miss looks close, and the spec's exclusions rule it out. Name the one that does.
- When the spec has a surfacing solver, read its call site: that is the evidence for the spec question.
- Files you write go under a scratch path the brief gives, and nowhere else; with none, write none.

# Report
- Four parts, in this order: Callers, Near-misses, Spec, Reimplementations.
- Head each part with that word and a colon on a line of its own; write no markdown heading and no bold.
- Write no text before the `Callers:` line and none after the Reimplementations part.
- Name the lib operation in the text.
- The report restates neither the entry's title and definition nor the scope and time the `Survey:` line above it states.
- Cite a solver by its stem and the relation name.
- Write no path under `.scratch/`.
- Refer to an earlier result by its `Survey:` time, never by an ordinal.
1. Callers — each with the solver and the relation name, and one sentence on what it computes there.
    - Give each caller a line of its own, opening with `<stem> <relation>`; with none, write `Callers: none.`
    - No second caller is an answer: give the negative evidence, what the signature matched across the scope.
2. Near-misses — each with the solver, the relation name, and the exclusion that rules it out.
    - A class of near-misses names the relation at each solver it cites.
3. Spec — whether the operation's interface or definition should change, argued from the sites in parts 1 and 2.
    - A signal that rests on the surfacing solver alone is reported as caller-only, not as a change.
4. Reimplementations — sites met on the way that hand-write what lib already provides, each with the stem, the relation name, and the matching lib relation.
    - Give each site a line of its own; with none, write `Reimplementations: none.`
    - A matcher's hit counts and the search method go at the end of this part, or nowhere.
