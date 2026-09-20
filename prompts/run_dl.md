# Deletion report
- The parts of the audit's deletion section, one section per group the report prints.

* comment: when editing this doc
    - A section carries the name `render_deletions` asks for.
    - The finding rows are data, and the code builds them under the header statement.
    - A group's note states what its findings mean, and the reader takes the rows against it.

## baseline-fails
- baseline fails: stored source does not pass train+test

## none
- every deletion changes the result ({{judged}} tested)

## noop
- {{count}}/{{judged}} deletions change nothing:
    - The removal changed no pair's output and no determined value.
    - The pairs never instantiate the structure it removed, or another atom already implies that structure.
    - The session judges which.
    - A column drop removes that argument at every atom of the relation.
    - The variables that bound it are left unbound at the consumers.

## case
- The cases agree on every pair, so dropping the case column changes nothing.
- The column carries the coverage hypothesis, and the pairs do not exercise it.
- The column stays, since the hypothesis is the solver's claim and not a fact the pairs settle.

## enumerator
- {{count}}/{{judged}} deletions remove an enumerator over a bound variable:
    - The enumerator runs over a variable another atom of its rule binds.
    - It is the readable form of a per-member test.
    - Its removal changes nothing, and that says nothing about the pairs.

## unprobed
- {{count}} {{noun}} the probe cannot judge:
    - Dropping the case column ungrounds a variable, so the probe result says nothing about the cases.
    * inline: #cases-settle-nothing

## ungrounded
- {{count}} {{noun}} the run cannot judge:
    - The removal ungrounds a variable, so Souffle rejects the file.
    - The run says nothing about the pairs.

## unexercised
- the pairs do not exercise the coverage hypothesis:
    * inline: #cases-settle-nothing

## Partials

### cases-settle-nothing
- Every case emits an accepted grid on every pair, which holds of every passing multi-case solver.
- The pairs settle nothing about the cases either way.
- [Models and tasks](../docs/handbook/principles.md#models-and-tasks) of Principles states what a case is.
