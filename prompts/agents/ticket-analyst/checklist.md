+ budget: 4039
* comment: when editing this doc
    - The ticket analyst's checklist: `uv run python scripts/step.py ticket-analyst` prints its items one at a time, by [Ticket analyst](prompts/agents/ticket-analyst.md#ticket-analyst), each as the ticket analyst reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Settle the tickets
- This part applies where your brief gives tickets under `tickets/open/` to settle: [Settling tickets](prompts/agents/ticket-analyst/tickets.md).

## Take the tickets
- Take each ticket your brief gives to settle, other than one you leave untaken as [Settling tickets](prompts/agents/ticket-analyst/tickets.md#settling-tickets) gives, as [Tracking](prompts/agents/ticket-analyst.md#tracking) gives.

## Find the duplicates
- Find each one's duplicates, as [Settling tickets](prompts/agents/ticket-analyst/tickets.md#settling-tickets) gives.

## Check the evidence
- Check each one's evidence, as [Settling tickets](prompts/agents/ticket-analyst/tickets.md#settling-tickets) gives.

## Choose the resolutions
- Find each one's root cause and choose its resolution, as [Settling](prompts/agents/ticket-analyst.md#settling) and [Settling tickets](prompts/agents/ticket-analyst/tickets.md#settling-tickets) give.

# Make the process assessment
- This part applies where your brief asks for the process assessment: [Process assessment](prompts/agents/ticket-analyst/process-assessment.md).

## Assess the processes
- Assess the agents' processes, as [Process assessment](prompts/agents/ticket-analyst/process-assessment.md#process-assessment) gives.

## Choose the resolutions of the findings
- Find each finding's root cause and choose its resolution, as [Settling](prompts/agents/ticket-analyst.md#settling) gives.

# Revise the draft
- This part applies where a later message gives a draft `change` to revise: [Revising a draft](prompts/agents/ticket-analyst/drafts.md).

## Read the Grounds
- Read the draft's `Grounds` before you explore, as [Revising a draft](prompts/agents/ticket-analyst/drafts.md#revising-a-draft) gives.

## Choose the resolution of the draft
- Settle whether a change is needed, and choose the resolution of the draft, as [Revising a draft](prompts/agents/ticket-analyst/drafts.md#revising-a-draft) gives.

# Write the change ticket
- This part applies where a resolution you chose files a `change` or revises one: [Writing a change ticket](prompts/agents/ticket-analyst/change.md).

## Write the Intent
- Write or revise the Intent of each such `change`, with its traces, as [Requirements](prompts/agents/ticket-analyst/change.md#requirements) gives.

## Check the coverage
- Check that each Intent covers the need, as [Requirements](prompts/agents/ticket-analyst/change.md#requirements) gives, and fix each part it leaves.

## Write the rest
- Write or revise the rest of each `change`'s text, as [Design](prompts/agents/ticket-analyst/change.md#design) and [Change tickets](prompts/agents/notes/tickets.md#change-tickets) give.

## Think the revised design through
- Where you revise a draft, think the revised design through, as [Revising a draft](prompts/agents/ticket-analyst/drafts.md#revising-a-draft) gives.

## Check the draft
- Check the text of each `change` before you file it or log its revision, as [Checking a draft](prompts/agents/ticket-analyst/change.md#checking-a-draft) gives.

# Apply the resolutions
- Apply each resolution you chose, as [Resolving](prompts/agents/ticket-analyst.md#resolving) gives.

# Reply
- Give your final reply, as [Reply](prompts/agents/ticket-analyst/reply.md#reply) and [Commands](prompts/agents/ticket-analyst.md#commands) give.
