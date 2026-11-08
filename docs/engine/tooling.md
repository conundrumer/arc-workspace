# Tooling

The last step of the [build order](overview.md#build-order). It builds the [witnesses and the case conditions](cases.md#refine-step) of the judge, the CLI, the reports that refine passes read, and the checks over a solver's structure, written as arclog queries.

The step ends when a refine pass runs on the engine, the checks of the present lint have moved to the engine, and the engine is at parity with Souffle on the witness outcomes and the case-condition reports, as [verification.md](verification.md) checks them, or the difference is reported as a fault, as the Principles requirement of [Requirements](overview.md#requirements) gives.

## Checks as queries

- The engine gives two sets of facts as fact relations of a check program:
    - The structure facts describe a solver: its forms, clauses, atoms, sites, reads, declarations, blocks and alts.
    - The run facts describe a run: row counts, whether each case solves each pair, output cells, determined values, and the evaluations stopped at a cap.
- A check is arclog clauses in `engine/checks/*.arclog`. The columns of a check relation's rows are the code, the place and the parts of the message.
- The engine runs the check program with the same evaluator. So a new check that reads only these facts is a text edit, and it runs at engine speed.

## Reports

- A report that changes the program or the data and evaluates again is an engine operation over the result cache, given as a CLI command. These reports are among them:
    - delete each atom and compute again, to find the atoms that no output needs
    - drop each stored fact, to find the facts that no train pair needs
    - record a witness
    - find the proposers whose derivation solves the train pairs, as `$Derived` alts
    - find the relations with one value on every input, as `$Stored` alts
- Explain gives, for a case on an input, the alts the case takes, the models enumerated, the parameter values, and each relation's row count. For an undefined output, it gives the cell, and the first atom of the `OUT` form, in written order, whose relation has no row at the cell's binding. On request, it gives the same for that atom's relation, one step further back in the dependency graph.

## CLI

- The CLI does what the present `run_dl.py` commands do, where the function is still needed in arclog: check, run, a grid or a relation on a written input, record, witness, audit, derive, store, deletions, drop-one, trace and render.
- The parameter sweep and the determination plan have no counterpart, since the program states the determination.

## Formatting

- The writer formats a hand-written file in the layout of [Solvers](reader.md#solvers), so a refine pass never handles layout.

## How each decision can fail

| Decision | Failure | What catches or bounds it |
| --- | --- | --- |
| Checks as arclog queries | a check needs a form that the language lacks | the structure facts grow by a relation; a check that changes the program and evaluates again is an engine operation |

## Known gaps

| Gap | Where it shows |
| --- | --- |
| The schema of the structure facts and the run facts, and how a check's message is made from columns | the move of the present lint's checks |
