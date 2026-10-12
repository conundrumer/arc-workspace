+ budget: 1200
* comment: when editing this doc
    - The ticket analyst loads this document from [Jobs](prompts/agents/ticket-analyst.md#jobs), when its brief asks for the process assessment.
    - Acts, each with its section:
        - Assessing the processes against the process notes, and settling or bringing each finding: [Process assessment](#process-assessment).

# Process assessment
- Assess the agents' processes as a whole against [Process notes](prompts/agents/notes/process.md), for work that two processes duplicate, an outcome that no owner meets, rules that conflict, a step whose cost is out of proportion to what it finds, and a step or a rule that serves no outcome.
- Settle each finding as a fault you notice, by [Settling](prompts/agents/ticket-analyst.md#settling).
- Where a resolution would cut a check or a rule, make no such cut: bring it to the user as a decision, with the check's cost.
