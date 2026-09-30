# Deletion report
- The parts of the audit's deletion section, one section per group the report prints.

* comment: when editing this doc
    - A section's heading is the name `render_deletions` asks for.
    - The finding rows are data, and the code builds them under the header statement.
    - A group's note states what its findings mean, and the reader reads the rows in light of it.

## baseline-fails
- baseline fails: stored source does not pass train+test

## none
- every deletion changes the result ({{judged}} tested)

## noop
- {{count}}/{{judged}} deletions change nothing:
    - The removal changed no pair's output{{determined}}.
    - The pairs never instantiate the structure it removed, or another atom already implies that structure.
    - Judge which.
    * comment:
        - A column drop removes that argument at every atom of the relation.
        - The variables that bound it are left unbound at the consumers.

## case
- The cases agree on every pair, so dropping the case column changes nothing.
- The column stays.
* inline: #case-claim

## enumerator
- {{count}}/{{judged}} deletions remove an enumerator over a bound variable:
    - The enumerator runs over a variable another atom of its clause binds.
    - Its removal says nothing about the pairs.
    * comment:
        - It is the readable form of a per-member test.

## unprobed
- {{count}} {{noun}} the probe cannot judge:
    - Dropping the case column ungrounds a variable, so the probe result says nothing about the cases.
    * inline: #cases-settle-nothing

## ungrounded
- {{count}} {{noun}} the run cannot judge:
    - The removal ungrounds a variable, so Souffle rejects the file.
    - The run says nothing about the pairs.

## unexercised
- the pairs do not separate the case's model from the concept case's:
    * inline: #cases-settle-nothing

## timed-out
- the runs below timed out:

## Partials

### case-claim
- [Models and tasks](docs/handbook/principles.md#models-and-tasks) states what a case claims.

### cases-settle-nothing
- The pairs settle nothing about the cases.
* inline: #case-claim
