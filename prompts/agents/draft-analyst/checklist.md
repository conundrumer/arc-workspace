+ document-size-budget: 2268
* comment: when editing this doc
    - The draft analyst's checklist: `uv run python scripts/step.py draft-analyst` prints its items one at a time, by [Draft analyst](prompts/agents/draft-analyst.md#draft-analyst), each as the draft analyst reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Read the Grounds
- Read each draft's `Grounds` before you explore, as [Revising a draft](prompts/agents/ticket-analyst/drafts.md#revising-a-draft) gives.
    + xref: prompts/agents/ticket-analyst/drafts.md#revising-a-draft

# Choose the resolutions
- Settle whether each draft's change is needed, and choose its resolution, as [Revising a draft](prompts/agents/ticket-analyst/drafts.md#revising-a-draft) gives.
    + xref: prompts/agents/ticket-analyst/drafts.md#revising-a-draft

# Write the change ticket
- This part applies where a resolution you chose revises a draft or files a `change`: [Writing a change ticket](prompts/agents/ticket-analyst/change.md).

## Write the Intent
- Write or revise the Intent of each such `change`, with its traces, as [Requirements](prompts/agents/ticket-analyst/change.md#requirements) gives.
    + xref: prompts/agents/ticket-analyst/change.md#requirements

## Check the coverage
- Check that each Intent covers the need, as [Requirements](prompts/agents/ticket-analyst/change.md#requirements) gives, and fix each part it leaves.
    + xref: prompts/agents/ticket-analyst/change.md#requirements

## Write the rest
- Write or revise the rest of each `change`'s text, as [Design](prompts/agents/ticket-analyst/change.md#design) and [Change tickets](prompts/agents/notes/tickets.md#change-tickets) give.
    + xref: prompts/agents/ticket-analyst/change.md#design, prompts/agents/notes/tickets.md#change-tickets

## Think the revised design through
- Think each revised design through, as [Revising a draft](prompts/agents/ticket-analyst/drafts.md#revising-a-draft) gives.
    + xref: prompts/agents/ticket-analyst/drafts.md#revising-a-draft

## Check the draft
- Check the text of each `change` before you file it or log its revision, as [Checking a draft](prompts/agents/ticket-analyst/change.md#checking-a-draft) gives.
    + xref: prompts/agents/ticket-analyst/change.md#checking-a-draft

# Apply the resolutions
- Apply each resolution you chose, as [Resolving](prompts/agents/draft-analyst.md#resolving) gives.
    + xref: prompts/agents/draft-analyst.md#resolving

# Reply
- Give your final reply, as [Reply](prompts/agents/draft-analyst/reply.md#reply) and [Commands](prompts/agents/draft-analyst.md#commands) give.
    + xref: prompts/agents/draft-analyst/reply.md#reply, prompts/agents/draft-analyst.md#commands
