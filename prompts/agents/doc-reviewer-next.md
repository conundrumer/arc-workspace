+ lib: none
+ budget: 11000
* comment: when editing this doc
    - The doc reviewer loads this document, rendered to `.claude/doc-reviewer-next.md`, once it has done the steps of [Reviewing a change](docs/handbook/editing.md#reviewing-a-change) in its first review, by the line of [Doc reviewer](prompts/agents/doc-reviewer.md) that gives that `cat`, for the line review of each review.
    - Acts, each with its section:
        - Judging the kept text: [How the kept text reads](#how-the-kept-text-reads).
        - Checking each line against the rules on a line: [Writing a file](#writing-a-file) and the included [Writing a document](src/controlled_markdown/writing.md).

# Doc reviewer: second stage
- Do these steps in each review, after the steps of [Reviewing a change](docs/handbook/editing.md#reviewing-a-change) in your prompt.

* include: ../../src/controlled_markdown/writing.md
    + exclude: rules on prose in code

## How the kept text reads
* inline: ../../docs/handbook/editing.md#how-the-kept-text-reads

## Writing a file
* inline: ../../docs/handbook/editing.md#writing-a-file
