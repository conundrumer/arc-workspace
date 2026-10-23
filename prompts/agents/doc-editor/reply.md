+ document-size-budget: 2100
* comment: when editing this doc
    - The doc editor reads this document by the links of the items `Write your reply` and `Reply` of its checklist, as it writes its reply to its report file before it launches its change's checks, and as it gives its final reply.
    - Acts, each with its section:
        - What its reply gives: [Your reply](#your-reply).

# Your reply
- Your reply gives:
    * comment: The cases this rule covers are those of the lines it replaced, each a part of the reply: the Intent and later requests, the departures, the unused Justification entries, the findings left for a decision, the items Reviewing a change has you report to the one who asked, and the gate outputs.
    - Each thing the Intent asks for, and each thing a request a later message adds asks for, as done, or as unfinished with its reason, and each place you departed from the request, with why.
        - What [An editor's report on a change](prompts/agents/notes/launching.md#an-editors-report-on-a-change) gives.
            + xref: prompts/agents/notes/launching.md#an-editors-report-on-a-change
    - Each finding of the last review pass that you left unfixed because it needs a decision, and each item [Reviewing a change](docs/handbook/editing.md#reviewing-a-change) has you report to the one who asked for the change, as a finding that needs a decision.
        + xref: docs/handbook/editing.md#reviewing-a-change
    - Each Justification entry that kept no line once you cut the lines no rule keeps, as unused.
    - Where you ran the gate, each output you copied, and each output a `DIFF` line gives that you did not copy, with that line.
        + xref: src/gating/lines.py:LineKind.DIFF
    - What [A part a brief leaves out](prompts/agents/notes/launching.md#a-part-a-brief-leaves-out) and [denied-calls](prompts/agents/notes/commands.md#denied-calls) give.
        + xref: prompts/agents/notes/launching.md#a-part-a-brief-leaves-out, prompts/agents/notes/commands.md#denied-calls
