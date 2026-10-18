+ budget: 2254
* comment: when editing this doc
    - The doc reviewer's checklist: `uv run python scripts/step.py doc-reviewer` prints its items one at a time, by [Doc reviewer](prompts/agents/doc-reviewer.md#doc-reviewer), each as the doc reviewer reaches its step, in each review.
    - Acts, each with its section: each step of its work, under the item of that step.

# Review a commit
- This part applies where your brief gives a commit of `master` that the coordinator merged, or a standing doc review: [A review of a commit](prompts/agents/doc-reviewer/commit-review.md).

## Tag the standing review
- Where your brief gives a standing doc review, set its tag.

# Launch the trials
- This part applies where your brief gives the number of the change's ticket: [Trials](prompts/agents/doc-reviewer/trials.md).

## Write the cases
- Write the case of each trial of this review whose item gives none, or whose case reads a ticket whose text it does not quote.

## Launch each trial
- Launch each trial of this review.

# Review the change
- Review the change by the steps [Reviewing a change](docs/handbook/editing.md#reviewing-a-change) gives.
    + xref: docs/handbook/editing.md#reviewing-a-change

# Judge the trials
- Where you launched trials in this review, judge each trial's reply once its run has ended, as [Trials](prompts/agents/doc-reviewer/trials.md) gives.
    + xref: prompts/agents/doc-reviewer/trials.md

# File the tickets
- File each finding of this review that [Filing and sending findings](prompts/agents/doc-reviewer/findings.md#filing-and-sending-findings), or, in a review of a commit or a standing doc review, [A review of a commit](prompts/agents/doc-reviewer/commit-review.md), gives as a ticket.
    + xref: prompts/agents/doc-reviewer/findings.md#filing-and-sending-findings, prompts/agents/doc-reviewer/commit-review.md

# Send the findings
- Send each other finding of this review, as [Filing and sending findings](prompts/agents/doc-reviewer/findings.md#filing-and-sending-findings) gives.
    + xref: prompts/agents/doc-reviewer/findings.md#filing-and-sending-findings

# Reply
- Give your reply, as [Your reply](prompts/agents/doc-reviewer/reply.md#your-reply) gives.
    + xref: prompts/agents/doc-reviewer/reply.md#your-reply
