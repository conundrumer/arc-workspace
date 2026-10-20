+ document-size-budget: 1814
* comment: when editing this doc
    - The decision analyst's checklist: `uv run python scripts/step.py decision-analyst` prints its items one at a time, by [Decision analyst](prompts/agents/decision-analyst.md#decision-analyst), each as the decision analyst reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Judge what the editors leave
- This part applies where your brief gives findings or items an editor left, places a code editor's report gives as standing, or `question` tickets filed on the change: [An editor's findings](prompts/agents/decision-analyst/findings.md).

## Judge each finding
- Judge each finding, item and place your brief gives, decide each question it raises, and send each editor your judgments on its part by SendMessage, as [Findings an editor leaves](prompts/agents/notes/changes.md#findings-an-editor-leaves) and [An editor's findings](prompts/agents/decision-analyst/findings.md#an-editors-findings) give.
    + xref: prompts/agents/notes/changes.md#findings-an-editor-leaves, prompts/agents/decision-analyst/findings.md#an-editors-findings
    * comment: Decision analyst ae975fc42988a5088 of session 129de8fc-2a0d-4d4d-b950-3a0194c762e2, on change 9-1262, 2026-10-18T12:21:20Z to 12:23:11Z, wrote three edits for the editor that launched it (a9ced10d14742eab8) into its reply file and called no SendMessage; the editor gave its final reply and the operator merged without those edits. Ticket 11-1248, Motivation.

## Settle the question tickets
- Close or block each `question` ticket on the change that you decide, as [An editor's findings](prompts/agents/decision-analyst/findings.md#an-editors-findings) gives.
    + xref: prompts/agents/decision-analyst/findings.md#an-editors-findings

# Decide the held step
- This part applies where your brief gives a step an operator holds: [A held step](prompts/agents/decision-analyst/held-step.md).

## Decide each held step
- Decide each step an operator holds that your brief gives, as [A held step](prompts/agents/decision-analyst/held-step.md#a-held-step) gives.
    + xref: prompts/agents/decision-analyst/held-step.md#a-held-step

# Reply
- Give your final reply, as [Reply](prompts/agents/decision-analyst/reply.md#reply) and [Commands](prompts/agents/decision-analyst.md#commands) give.
    + xref: prompts/agents/decision-analyst/reply.md#reply, prompts/agents/decision-analyst.md#commands
