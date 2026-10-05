# Deletion report
- The parts of the `deletions` report, one section per group the report prints.

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

## enumerator
- {{count}}/{{judged}} deletions remove an enumerator over a bound variable:
    - The enumerator runs over a variable another atom of its clause binds.
    - The enumerator stays.
    * comment:
        - It is the readable form of a per-member test.

## ungrounded
- {{count}} {{noun}} the run cannot judge:
    - The removal ungrounds a variable, so Souffle rejects the file.
    - The run says nothing about the pairs.

## timed-out
- the runs below timed out:
