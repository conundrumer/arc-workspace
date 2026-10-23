+ lib: none
+ document-size-budget: 16800
* comment: when editing this doc
    - The `analyze` agent loads this document, rendered to `.claude/analyze-next.md`, once it has written the concept, by the step of [Analyze](docs/handbook/procedure.md#analyze) that gives it.
    - Parts of the work, in order:
        - Forming every other branch and giving each its standing: [Analyze after the concept](#analyze-after-the-concept).
        - Writing the witness file: [Witness file](#witness-file).
    - Acts, each with its section:
        - Choosing the proposers from which step 1 forms `@derive` branches: [Proposers](#proposers).
        - Choosing the keywords whose solvers step 1 lists: [Keywords](#keywords).

# Analyze after the concept
* inline: ../../docs/handbook/procedure.md#analyze-after-the-concept

## Proposers
- Each proposer, with the column types of its `propose` relation and what it derives from the examples it reads; under a `@derive` branch it reads one input and no output.
    + xref: src/handbook/listings.py:Listing.PROPOSERS, src/handbook/listings.py:_proposer_lines
    * comment: Observed misread, a rewording of the words the reader misread: the transcript review a03d91106af718c5a of the Analyze pass on e872b94a, in ticket 17-70, read the listing's "a color in every input and no train output" for VanishedColor against the task's train outputs, where a `@derive` branch gives the proposer none, and filed the pass's correct `shape_color=VanishedColor` report as wrong.
* text: proposers

## Keywords
* inline: ../../docs/handbook/keywords.md#keywords

## Witness file
* inline: ../../docs/handbook/solver-file.md#witness-file
