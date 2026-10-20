+ document-size-budget: 981
* comment: when editing this doc
    - The ticket analyst receives this document from the step command as it enters the process assessment, once it has read its brief.
    - Acts, each with its section:
        - Assessing the processes against the process notes, and settling or bringing each finding: [Process assessment](#process-assessment).

# Process assessment
- The process assessment judges the agents' processes as a whole against [Process notes](prompts/agents/notes/process.md), for work that two processes duplicate, an outcome that no owner meets, rules that conflict, a step whose cost is out of proportion to what it finds, and a step or a rule that serves no outcome.
    + xref: prompts/agents/notes/process.md
- Take a step's cost against what it finds from the `performance` tickets of the cost audits launched since the launch of the last process assessment, and run no `profile_runs.py` call for it. Where there are none, judge no step's cost, and say so in your reply.
    * comment: Ticket 11-1310: assessments af9df7e4143f5b793 and a73a70e1ad63a20de each profiled the session's runs (2.5 m and 7.2 m of tool time) after cost audits had judged each step's cost.
- Each finding of the assessment is a fault you notice.
- Where a resolution would cut a check or a rule, make no such cut: bring it to the user as a decision, with the check's cost.
