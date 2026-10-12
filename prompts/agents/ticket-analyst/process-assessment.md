+ budget: 1200

# Process assessment
- Assess the agents' processes as a whole against [Process notes](prompts/agents/notes/process.md), for work that two processes duplicate, an outcome that no owner meets, rules that conflict, a step whose cost is out of proportion to what it finds, and a step or a rule that serves no outcome.
- Where those notes hold no map of the rules to their outcomes, map each rule of the documents under [notes](prompts/agents/notes) and of the agent definitions to an outcome of those notes, and file a `change` that adds that map to them. Where they hold one, map again each rule and each outcome that a commit of `master` after the commit that map gives has altered, and file a `change` that updates it and gives as that commit the `HEAD` you mapped at.
- Settle each finding as a fault you notice, by [Settling](prompts/agents/ticket-analyst.md#settling).
- Where a resolution would cut a check or a rule, make no such cut: bring it to the user as a decision, with the check's cost.
