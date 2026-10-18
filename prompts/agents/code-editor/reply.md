+ budget: 1900
* comment: when editing this doc
    - The code editor reads this document by the links of the items `Write your report` and `Report` of its [checklist](prompts/agents/code-editor/checklist.md), as it writes its report to its report file before it launches its change's checks, and as it gives its final reply.
    - Acts, each with its section:
        - What its report opens with and gives: [Your report](#your-report).

# Your report
- Observe and report: say what is there, never what the spec should say, and offer no option.
- Your final reply opens with `done` where you end at Done, and with `blocked` where you end at Blocked, then gives each item of your brief, and of each request a later message adds, as done or as unfinished with its reason, and, where you end at Blocked, the concrete case.
- It gives as well what [An editor's report on a change](prompts/agents/notes/launching.md#an-editors-report-on-a-change), [A part a brief leaves out](prompts/agents/notes/launching.md#a-part-a-brief-leaves-out) and [denied-calls](prompts/agents/notes/commands.md#denied-calls) give.
- The report has a `Reuse` section, which gives the `Reuse` list of your `progress.md`, and a `Review` section, which gives each kind of place you read your diff for and the places your diff holds of it, each defect place fixed or standing with its reason, each standing place as a list item that opens with `stands:`.
- Where you ran the gate, the report gives each output that a `DIFF` line gives and you did not copy, with that line.
