# Traceability matrix
- The map of each rule of the documents under [notes](prompts/agents/notes) and of the agent definitions under [agents](prompts/agents) to the outcomes of [Process notes](prompts/agents/notes/process.md) it serves.
- Each entry is a section, with the outcomes its rules serve, each as its process and a phrase of its words. Under the entry stands each rule of that section that serves another outcome or none, by its opening words.
- An entry or a rule that serves no outcome gives the judgment that keeps it.
- An entry on a document's title heading covers the lines above its first section. A section with no rule of its own, only lines that inline or include another document, has no entry.

## Decision notes
- [The user's goals](prompts/agents/notes/decisions.md#the-users-goals): none. Kept: the goals are the purpose of Process assessment, and its principle.
- [Rule and intent](prompts/agents/notes/decisions.md#rule-and-intent): Decisions: each decision recorded with what it was made from.
    - "Have a support line added only": none. Kept: a principle of Decisions.
    - "Have a fix of agent-facing text that misled": none. Kept: it places the fix of a misleading line on that line.
    - "The agents' definitions, the spec": Process assessment: each rule maps to an outcome.
- [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made): Decisions: each decision recorded with what it was made from.
    - "Where a decision touches a solver", "Where a decision touches a document", "Churn is no reason", "Prefer the general option", "Make no option the default that fits only", "Before you act on a default": none. Kept: the principle of Decisions.
    - "Check a reported problem against the state", "Take agents' reports as evidence": none. Kept: they serve the purpose of Quality assurance, the cause of each fault.
    - "Carry out no resolution whose need no output depends on": none. Kept: the principle of Process assessment, spend no run the work does not need.
    - "Where neither settles what the tool does": Solver passes: a pass runs its operations on its task.
    - "The history of a decision is in the session transcripts": none. Kept: it gives where Measurement and Decisions find a decision's history.
    - "Leave the judgment of how the code is written, past the `Design`": none. Kept: the principle of Design.
- [The user's part](prompts/agents/notes/decisions.md#the-users-part): Decisions: a departing decision reaches the user; a decline carries its defense.
    - "Tell the user, without waiting on them", "Bring the user nothing else": none. Kept: the principle of Decisions and of Requirements.
- [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences): none. Kept: each line is a preference of the user, which the decisions on its subject apply, and each line a process gives as a principle serves that process.
- [Decisions on solver work](prompts/agents/notes/decisions.md#decisions-on-solver-work): none. Kept: the principle of Solver passes.
- [Decisions on the agents' documents](prompts/agents/notes/decisions.md#decisions-on-the-agents-documents): Verification: evidence of a reader's behavior.
    - "Write the documents first to serve": none. Kept: the principle of Verification.
    - "The user writes no text": Verification: another agent checks the built change.
    - "Keep instructions few", "Give a context bound": none. Kept: a preference of the user on the agents' documents, which each document change applies.
    - "Structure the documents so": none. Kept: the principle of Configuration management.

## Change notes
- [Carrying a change](prompts/agents/notes/changes.md#carrying-a-change): Verification: another agent checks the built change; Implementation: each item not done reaches the agent that decides it; Merge: a hotfix reviewed after it merges.
    - "Have an editor write each change": Process assessment: the agent and the reviews of each work product.
    - "A change is one editor's edit", "A change's ticket is the `change` ticket": none. Kept: they give what a change and its ticket are, which the rest of the section acts on.
    - "Make the worktree of a change": Configuration management: one live change per worktree.
    - "Where you take up a change that another agent held", "Then, where your brief", "Send no message to an editor or reviewer that other agent launched": Work control: one live holder per ticket.
    - "Run the changes you launch at the same time": none. Kept: the principle of Configuration management, run parallel parts at once.
- [Findings an editor leaves](prompts/agents/notes/changes.md#findings-an-editor-leaves): Implementation: each item not done reaches the agent that decides it.
    - "Judge each finding a change's editor leaves": Decisions: each decision recorded with what it was made from.
- [Merging a change](prompts/agents/notes/changes.md#merging-a-change): Merge: each merge passes the gate and the checks; a failed or denied merge reaches an agent.
    - "Where a kept finding of a change raises a decision": Decisions: a departing decision reaches the user.
    - "Before you merge a change, read the diff": Verification: another agent checks the built change.
    - "Once a change is merged, and before you close its ticket": Validation: a fault in use traced to the change.
    - "Once a change is merged, move to `tickets/closed/`", "Once a change is merged, close each `refactor` ticket": none. Kept: they close the tickets a merged change settles, so that no settled ticket waits for a step.
- [A denied merge](prompts/agents/notes/changes.md#a-denied-merge): Merge: a failed or denied merge reaches an agent.

## Code notes
- [code-working-rules](prompts/agents/notes/code.md#code-working-rules): none. Kept: they bound what a code-working agent reads and launches, and keep its progress across a compaction.
- [place-kinds](prompts/agents/notes/code.md#place-kinds): Verification: a standing review of the lines in force.
- [place-tickets](prompts/agents/notes/code.md#place-tickets): Verification: a standing review of the lines in force.
    - "In the title of a `question` ticket": none. Kept: it gives the form of a ticket that poses a question.

## Command notes
- [waiting-on-commands](prompts/agents/notes/commands.md#waiting-on-commands): Work control: stopped work reaches an agent.
- [ending-commands](prompts/agents/notes/commands.md#ending-commands): none. Kept: an agent ends its own processes, and signals no process of another agent.
- [Background agents](prompts/agents/notes/commands.md#background-agents): Work control: stopped work reaches an agent.
    - "Call SubagentHandback only": Implementation: each item not done reaches the agent that decides it.
- [denied-calls](prompts/agents/notes/commands.md#denied-calls): Implementation: each item not done reaches the agent that decides it.
- [resumed-agents](prompts/agents/notes/commands.md#resumed-agents): Implementation: each item not done reaches the agent that decides it.
- [coordinator](prompts/agents/notes/commands.md#coordinator): none. Kept: it gives the coordinator's address, which the lines on a final reply use.
- [report-file](prompts/agents/notes/commands.md#report-file): Implementation: each item not done reaches the agent that decides it.
- [final-report](prompts/agents/notes/commands.md#final-report): Implementation: each item not done reaches the agent that decides it.

## Coordinator
- [Coordinator](prompts/agents/notes/coordinator.md#coordinator): none. Kept: it gives the coordinator its part and how it reads the documents.
- [Routes](prompts/agents/notes/coordinator.md#routes): Requirements: requirements traced to the spans; Merge: a hotfix reviewed after it merges.
    - "`scratch` is work after which": none. Kept: the principle of Process assessment, spend no run the work does not need.
- [Tickets](prompts/agents/notes/coordinator.md#tickets): Requirements: requirements traced to the spans; Work control: stopped work reaches an agent.
    - "Where you run no solver pass, file each fault": none. Kept: it serves the purpose of Quality assurance, the cause of each fault.
    - "Tell the user what each ticket": none. Kept: the principle of Requirements, the user's part.
    - "Where the user's later words bear on a `request`": Requirements: requirements checked against added words.
    - "Where a `request` under `tickets/blocked/` waits on `validation`": Validation: a run shows the need met.
    - "Where the user rules on a ticket under `tickets/blocked/`": Decisions: a departing decision reaches the user.
- [Decisions](prompts/agents/notes/coordinator.md#decisions): Decisions: each decision recorded with what it was made from.
- [Declines](prompts/agents/notes/coordinator.md#declines): none. Kept: it leads the coordinator to the notes on a decline when one reaches it.
- [Changes](prompts/agents/notes/coordinator.md#changes): Process assessment: the agent and the reviews of each work product.
    - "Before you launch a pass on a task, read", "Before you send an operator a line, or move or revise", "While the user gives feedback, read", "Where you run no solver pass, read": none. Kept: they lead the coordinator to the notes its work there needs.
    - "Run a change yourself only on `direct` and `hotfix`", "Where a ticket it would settle waits on a `change`": Work control: one live holder per ticket.
    - "Once a change you run is on `master`": Merge: a hotfix reviewed after it merges.
- [Worktrees](prompts/agents/notes/coordinator.md#worktrees): Configuration management: one live change per worktree.
- [Reports to the user](prompts/agents/notes/coordinator.md#reports-to-the-user): Decisions: a departing decision reaches the user.
- [Cards](prompts/agents/notes/coordinator.md#cards): Decisions: a departing decision reaches the user.
- [Codex](prompts/agents/notes/coordinator.md#codex): Decisions: a departing decision reaches the user.
    - "When specifying an issue in prose to fix": Requirements: requirements traced to the spans.

## Decline notes
- [Declines](prompts/agents/notes/declines.md#declines): Decisions: a decline carries its defense.

## Card notes
- [Cards](prompts/agents/notes/cards.md#cards): Decisions: a departing decision reaches the user.

## Launching notes
- [Launching](prompts/agents/notes/launching.md#launching): Implementation: each item not done reaches the agent that decides it; Requirements: requirements traced to the spans.
    - "After an agent's definition changes": none. Kept: the harness reloads an agent's file only after that wait.
    - "Give an agent a brief in the form": none. Kept: it leads a launcher to the form of each brief.
    - "Where a brief gives a scratch directory": none. Kept: it keeps the session's files in the session's scratchpad.
    - "Give each way the edit can fail": Risk management: each way a design can fail is a requirement.
    - "Before you give another agent a draft `change` ticket": Verification: each `change` ticket checked before the build.
    - "Split work between agents": none. Kept: the principle of Process assessment and of Configuration management.
    - "Token cost is the list price", "Take each token cost you give": Measurement: each figure cites its command.
    - "Launch a ticket analyst with each ticket": Work control: stopped work reaches an agent.
    - "A transcript review is a `general-purpose` agent": Quality assurance: the review at each run's end.
    - "Pause or serialize agents only": none. Kept: the principle of Work control.
- [A part a brief leaves out](prompts/agents/notes/launching.md#a-part-a-brief-leaves-out): Implementation: each item not done reaches the agent that decides it.
- [A transcript brief](prompts/agents/notes/launching.md#a-transcript-brief): Requirements: requirements traced to the spans.
- [An editor's brief](prompts/agents/notes/launching.md#an-editors-brief): Configuration management: one live change per worktree.
    - "It gives the accepted gate outputs": Merge: each merge passes the gate and the checks.
- [A code editor's brief](prompts/agents/notes/launching.md#a-code-editors-brief): none. Kept: it gives a code editor the directories its work writes to.
- [A change's brief](prompts/agents/notes/launching.md#a-changes-brief): Requirements: requirements traced to the spans; Configuration management: overlapping changes ordered.
- [Items and files](prompts/agents/notes/launching.md#items-and-files): Configuration management: overlapping changes ordered.
- [A doc editor's brief](prompts/agents/notes/launching.md#a-doc-editors-brief): none. Kept: the principle of Design, one idea in one place.
- [A ticket reviewer's brief](prompts/agents/notes/launching.md#a-ticket-reviewers-brief): Verification: each `change` ticket checked before the build.
- [A ticket analyst's brief](prompts/agents/notes/launching.md#a-ticket-analysts-brief): Work control: stopped work reaches an agent.
    - "With a draft whose next revision opens": none. Kept: it bounds the cost of the reviews a draft gets, a way Verification can fail.
    - "With the tickets a solver pass filed": Quality assurance: the review at each run's end.
- [An item checker's brief](prompts/agents/notes/launching.md#an-item-checkers-brief): Verification: another agent checks the built change.
- [An operator's brief](prompts/agents/notes/launching.md#an-operators-brief): Work control: stopped work reaches an agent.
    - "`Merge: <number>`": Merge: a failed or denied merge reaches an agent.
    - "`Decision: <decision key> <choice>`": Decisions: a departing decision reaches the user.
    - "`Solve: <task id> ...`", "`Solve from the queue`", "`Override: <task id> <pass> <override>`", "`Override: pass over <step key>`": Solver passes: a pass runs its operations on its task.
- [A code reviewer's brief](prompts/agents/notes/launching.md#a-code-reviewers-brief): Verification: a standing review of the lines in force.
- [A doc reviewer's brief](prompts/agents/notes/launching.md#a-doc-reviewers-brief): Verification: another agent checks the built change; a standing review of the lines in force.
- [Solver work](prompts/agents/notes/launching.md#solver-work): Solver passes: a pass runs its operations on its task; a pass writes only where its notes give.
- [A solver work brief](prompts/agents/notes/launching.md#a-solver-work-brief): Solver passes: a pass runs its operations on its task.
- [Writing a solver work brief](prompts/agents/notes/launching.md#writing-a-solver-work-brief): Solver passes: a pass runs its operations on its task.
    - "Solver work other than a pass is a change": Implementation: each requirement shown to hold.
- [An editor's report on a change](prompts/agents/notes/launching.md#an-editors-report-on-a-change): Implementation: each requirement shown to hold.
- [Passes on a task](prompts/agents/notes/launching.md#passes-on-a-task): Solver passes: a pass runs its operations on its task.
- [Operators](prompts/agents/notes/launching.md#operators): Work control: stopped work reaches an agent.
    - "Bring the user each `decision:` item": Decisions: a departing decision reaches the user.
    - "Send each draft `change` ticket", "Revise a `change` ticket that stands under": Verification: each `change` ticket checked before the build.
    - "Once the user rules on a draft `change` ticket": Requirements: requirements checked against added words.
    - "Ask an operator for no message to you": none. Kept: it keeps an operator's messages to the coordinator to those the coordinator acts on.
    - "Each time a `change` of your session comes to stand": Configuration management: overlapping changes ordered.
- [While the user gives feedback](prompts/agents/notes/launching.md#while-the-user-gives-feedback): none. Kept: the principle of Process assessment, spend no run the work does not need.
    - "Where a request touches the files of a change": Configuration management: one live change per worktree.
- [draft-outcome](prompts/agents/notes/launching.md#draft-outcome): Verification: each `change` ticket checked before the build.

## Process notes
- [Process notes](prompts/agents/notes/process.md#process-notes): Process assessment: one owner for each process; the faults of the processes reach the user.
    - "A change to the agents' processes is": none. Kept: it gives the changes whose count launches the process assessment.
- Each process section: its Outcomes are what this map maps to, and its Owner line serves Process assessment: one owner for each process.
    - Its "Takes from" and "Gives to" lines: none. Kept: they give the hand-offs between processes, which the process assessment reads for work two processes duplicate.
    - Its "How it can fail" lines: none. Kept: each gives what holds in a way the process can fail, which the process assessment weighs against the cost of a step.
- [Work products](prompts/agents/notes/process.md#work-products): Process assessment: the agent and the reviews of each work product.

## Reading notes
- [abridgement](prompts/agents/notes/reading.md#abridgement): Solver passes: a pass runs its operations on its task.
- [citations](prompts/agents/notes/reading.md#citations): Solver passes: a pass runs its operations on its task.
- [lib-index](prompts/agents/notes/reading.md#lib-index): Solver passes: a pass runs its operations on its task.
- [lib-interface](prompts/agents/notes/reading.md#lib-interface): Solver passes: a pass runs its operations on its task.

## Solver pass notes
- [solver-pass-lead](prompts/agents/notes/solver-pass.md#solver-pass-lead): Solver passes: a pass writes only where its notes give; a pass's report gives its judgments, its open items and its tickets.
    - "Do not read": Solver passes: a pass runs its operations on its task.
- [report-form](prompts/agents/notes/solver-pass.md#report-form): Solver passes: a pass's report gives its judgments, its open items and its tickets.

## Ticket notes
- [pass-tickets](prompts/agents/notes/tickets.md#pass-tickets): Solver passes: a fault a pass meets reaches a ticket.
    - "File a `delay` ticket for each step": Process assessment: the faults of the processes reach the user.
    - "Write under `Impact` what it cost the pass": Measurement: each figure cites its command.
- [Ticket files](prompts/agents/notes/tickets.md#ticket-files): none. Kept: it serves the purpose of Quality assurance, the cause of each fault.
- [Noticed faults](prompts/agents/notes/tickets.md#noticed-faults): none. Kept: it serves the purpose of Quality assurance, the cause of each fault.
- [Ticket fields](prompts/agents/notes/tickets.md#ticket-fields): none. Kept: it ties each ticket to the run or the change it is on, which the cause of a fault needs.
- [Tracking](prompts/agents/notes/tickets.md#tracking): Work control: one live holder per ticket.
    - "`tickets/` is in the main tree", "Every session on the repository shares", "Where you look for a ticket that already exists", "Make each transition": none. Kept: they give where the tickets are and how a ticket's state changes, which every holder's step uses.
    - "Close the ticket of a place that is judged and kept": Decisions: each decision recorded with what it was made from.
    - "Read a ticket you do not edit": Process assessment: the context each run of an agent loads holds only the lines each of its runs needs.
- [Change tickets](prompts/agents/notes/tickets.md#change-tickets): Configuration management: overlapping changes ordered.
    - "A ticket that asks for a change", "Give each `change` you file or revise the `mechanical` field": none. Kept: they give the fields a `change` ticket's handling reads.

## Worktree notes
- [editor-messages](prompts/agents/notes/worktree.md#editor-messages): Implementation: each item not done reaches the agent that decides it.
- [worktree](prompts/agents/notes/worktree.md#worktree): Configuration management: one live change per worktree.
    - "Where your brief gives the number of your change's ticket": none. Kept: it gives the command that prints a ticket's path.
    - "A later message may add a request": Requirements: requirements checked against added words.
- [worktree-commands](prompts/agents/notes/worktree.md#worktree-commands): Configuration management: one live change per worktree.
- [Re-invoked in another agent's worktree](prompts/agents/notes/worktree.md#re-invoked-in-another-agents-worktree): Configuration management: one live change per worktree.
    - "At such an event, and each time something re-invokes you": Work control: stopped work reaches an agent.
- [gate](prompts/agents/notes/worktree.md#gate): Merge: each merge passes the gate and the checks.

## Analyze agent
- [Analyze agent](prompts/agents/analyze.md#analyze-agent): Solver passes: a pass runs its operations on its task; a pass writes only where its notes give; a pass's report gives its judgments, its open items and its tickets.

## Analyze after the concept
- [Analyze after the concept](prompts/agents/analyze-next.md) has no rule of its own.

## Create agent
- [Create agent](prompts/agents/create.md#create-agent): Solver passes: a pass runs its operations on its task.
- [Report](prompts/agents/create.md#report): Solver passes: a pass's report gives its judgments, its open items and its tickets.

## Refine agent
- [Refine agent](prompts/agents/refine.md#refine-agent): Solver passes: a pass runs its operations on its task.
- [Report](prompts/agents/refine.md#report): Solver passes: a pass's report gives its judgments, its open items and its tickets.

## Handbook agents
- [handbook](prompts/agents/handbook.md): Solver passes: a fault a pass meets reaches a ticket.
    - "File a `delay` ticket for each step": Process assessment: the faults of the processes reach the user.
- [handbook-expanded](prompts/agents/handbook-expanded.md), its lines above its first heading: Solver passes: a fault a pass meets reaches a ticket.
    - "File a `delay` ticket for each step": Process assessment: the faults of the processes reach the user.
- [Carrying a change](prompts/agents/handbook-expanded.md#carrying-a-change): Implementation: each item not done reaches the agent that decides it.
    - "The lines below apply where your brief gives": none. Kept: it gives the work the lines below it apply to.
    - "Run no git command that changes state": Configuration management: one live change per worktree; Merge: each merge passes the gate and the checks.

## Ticket analyst
- [Ticket analyst](prompts/agents/ticket-analyst.md#ticket-analyst): none. Kept: it serves the purpose of Quality assurance, the cause of each fault.
- [Jobs](prompts/agents/ticket-analyst.md#jobs): none. Kept: the principle of Process assessment, spend no run the work does not need.
- [Settling](prompts/agents/ticket-analyst.md#settling): Quality assurance: a recurring fault taken as one family; Decisions: each decision recorded with what it was made from.
- [Resolving](prompts/agents/ticket-analyst.md#resolving): Decisions: a departing decision reaches the user; a decline carries its defense; each decision recorded with what it was made from.
    - "Carry out every other resolution": Work control: one live holder per ticket.
    - "In a `change` for speed": Measurement: each figure cites its command.
    - "Give rote work to an agent": none. Kept: the principle of Process assessment, spend no run the work does not need.
    - "At the end of your reply, under a `## For the coordinator`": Work control: stopped work reaches an agent.
- [Tracking](prompts/agents/ticket-analyst.md#tracking): Decisions: each decision recorded with what it was made from.
    - "The kind of a ticket you file is `change`": none. Kept: it gives the form of the tickets the analyst files.
    - "A `change` to the agents' processes": Process assessment: each rule maps to an outcome.
    - "Give with each Intent item": Requirements: requirements traced to the spans.
    - "Write the `Design` section", "List each state the design acts in", "Give what each part of the design costs", "Cover in its Scope each file": Design: a design from the code or the documents; its cost and gain against the goal; the Scope covers the design.
    - "Where meeting an Intent item costs more": Design: a requirement that costs more than it gains reaches the user; Decisions: a decline carries its defense.
    - "Leave out of the design", "Where a part's gain exceeds its cost": Design: its cost and gain against the goal.
    - "Settle by [Settling]": Process assessment: the faults of the processes reach the user.
- [Commands](prompts/agents/ticket-analyst.md#commands): Process assessment: the context each run of an agent loads holds only the lines each of its runs needs.
- [Settling tickets](prompts/agents/ticket-analyst/tickets.md): Requirements: requirements traced to the spans; Decisions: each decision recorded with what it was made from.
    - "Where the log of a `request` you take shows a `change` filed": Requirements: requirements checked against added words.
    - "Where the log of a `request` you take gives a commit": Merge: a hotfix reviewed after it merges.
    - "A ticket of kind `refactor` is a defect place": none. Kept: the principle of Design, one idea in one place.
    - "Judge a ticket a solver pass filed": none. Kept: it serves the purpose of Quality assurance, the cause of each fault.
- [Revising a draft](prompts/agents/ticket-analyst/drafts.md): none. Kept: the principle of Process assessment, spend no run the work does not need.
    - "Where you leave every suggestion": Verification: a later round on changed text only.
    - "Cut each line of the draft that a finding falls on": none. Kept: it keeps a requirement to what holds, a way Requirements can fail.
    - "Where a finding is a defensible reason", "Findings of two ticket reviewers": none. Kept: the principle of Decisions.
    - "Then think the whole revised design through": Risk management: each way a design can fail is a requirement.
- [A held step](prompts/agents/ticket-analyst/held-step.md): Work control: stopped work reaches an agent.
    - "Where [The user's part]": Decisions: a departing decision reaches the user.
    - "Where the operator's command could have decided": none. Kept: it serves the purpose of Quality assurance, the cause of each fault.
- [Process assessment](prompts/agents/ticket-analyst/process-assessment.md): Process assessment: the faults of the processes reach the user; each rule maps to an outcome.
- [An editor's findings](prompts/agents/ticket-analyst/findings.md): Decisions: a decline carries its defense.
    - "Judge each `refactor` place": Implementation: each item not done reaches the agent that decides it.

## Item checker
- [Item checker](prompts/agents/item-checker.md#item-checker): Verification: another agent checks the built change; Implementation: each item not done reaches the agent that decides it.

## Ticket reviewer
- [Ticket reviewer](prompts/agents/ticket-reviewer.md#ticket-reviewer): Verification: each `change` ticket checked before the build.
    - "Change no word of a draft": none. Kept: it leaves each revision of a draft to the ticket analyst, which Decisions gives as the owner of what a draft decides.
    - "Where you see a resolution one level above": none. Kept: the principle of Decisions.
    - "Where an earlier round reviewed the draft": none. Kept: the principle of Process assessment, spend no run the work does not need.
- [A later round](prompts/agents/ticket-reviewer/later-rounds.md): Verification: a later round on changed text only.
- [Checks](prompts/agents/ticket-reviewer.md#checks): Verification: each `change` ticket checked before the build.
    - "Report nothing on a draft's wording": none. Kept: it keeps the review on what a requirement states, a way Verification can fail.
    - "A `change`, other than one under `tickets/blocked/`", "Instructions that change the same files are ordered", "A `change` ticket's `depends-on` gives": Configuration management: overlapping changes ordered.
    - "A `change` to the agents' processes": Process assessment: each rule maps to an outcome.
    - "In a `change` that serves a `request`, each item of the Intent": Requirements: requirements traced to the spans.
    - "A `change` that adds a mechanism to code has a `Design`", "A `change` that adds or changes a rule or a fact", "A `Design` lists each state": Design: the design checked before the build.
    - "Each item of the Intent is a requirement": Requirements: requirements traced to the spans.
    - "No case that the readers of a line": Risk management: each way a design can fail is a requirement.
    - "A finding quotes the draft's line": none. Kept: it gives the form of a finding, which the ticket analyst acts on.
- [Tickets](prompts/agents/ticket-reviewer.md#tickets): none. Kept: it serves the purpose of Quality assurance, the cause of each fault.
    - "File a `performance` ticket": Process assessment: the faults of the processes reach the user.
- [Reply](prompts/agents/ticket-reviewer.md#reply): Verification: each `change` ticket checked before the build.

## Code editor
- [Code editor](prompts/agents/code-editor.md#code-editor): Implementation: each requirement shown to hold; each item not done reaches the agent that decides it.
    - "Observe and report": none. Kept: it keeps the editor's report to what it saw.
    - "When you start, copy `src/`": none. Kept: it lets the editor read its own diff.
    - "Before you write code, search every package": Design: a design from the code.
    - "Edit only the files your brief gives", "Run no git command that changes state": Configuration management: one live change per worktree.
    - "Where your brief asks for a comparison": none. Kept: the principle of Process assessment, spend no run the work does not need.
    - "Where your brief gives the places of `refactor`", "Before you edit a module, look under `tickets/open/`": none. Kept: the principle of Design, one idea in one place.
    - "Before you report done, read your diff": none. Kept: the principle of Design, one idea in one place.
    - "Where you ran the gate": Merge: each merge passes the gate and the checks.
- [Working rules](prompts/agents/code-editor.md#working-rules): Work control: stopped work reaches an agent.
- [Tickets](prompts/agents/code-editor.md#tickets): Implementation: each item not done reaches the agent that decides it.
- [The before side](prompts/agents/code-editor/before-side.md): Measurement: each figure cites its command.
- [A split](prompts/agents/code-editor/split.md): none. Kept: the principle of Design, one idea in one place.

## Code reviewer
- [Code reviewer](prompts/agents/code-reviewer.md#code-reviewer): Verification: a standing review of the lines in force; a later round on changed text only.
    - "Edit nothing under the tree", "Run no other git command": none. Kept: they leave the tree to the editors and the merge.
- [Tickets](prompts/agents/code-reviewer.md#tickets): Verification: a standing review of the lines in force.
    - "File a `performance` ticket": Process assessment: the faults of the processes reach the user.

## Doc editor
- [Doc editor](prompts/agents/doc-editor.md#doc-editor): Implementation: each requirement shown to hold; each item not done reaches the agent that decides it.
    - "Run no git command that changes state": Configuration management: one live change per worktree.
    - "Each Justification entry names", "In your reply, list as unused each Justification entry": none. Kept: the principle of Verification, check new agent-facing text against each agent it reaches.
    - "State the Intent at the minimum": Requirements: requirements traced to the spans.
    - "Build the `Design` of your change's ticket": Design: a design from the documents.
    - "Before you write anything, take these steps", "Judge each line you write or keep", "After each edit you make", "Fix each finding that needs no decision", "Then judge each line of the place you edited again": none. Kept: the principle of Verification, check new agent-facing text against each agent it reaches.
    - "Where you ran the gate": Merge: each merge passes the gate and the checks.
    - "Read [Prose in code]": none. Kept: the principle of Process assessment, spend no run the work does not need.
    - "The kind of a ticket you file is `question`": none. Kept: it serves the purpose of Quality assurance, the cause of each fault.

## Doc reviewer
- [Doc reviewer](prompts/agents/doc-reviewer.md#doc-reviewer): Verification: another agent checks the built change.
    - "File as a `bug` ticket each finding on a fault the change did not make", "The kind of a ticket you file is `bug`": none. Kept: they serve the purpose of Quality assurance, the cause of each fault.
    - "When the editor's fixes arrive, review the change again": Verification: a later round on changed text only.
    - "Hold back each finding an editor's message gives as left for a decision": Implementation: each item not done reaches the agent that decides it.
    - "Message no agent other than the editors", "Edit no file other than the tickets you file": none. Kept: they leave each finding's fix to the editor and each decision to the agent that decides it.
    - "File a `performance` ticket": Process assessment: the faults of the processes reach the user.
    - "Where your brief gives a standing doc review": Verification: a standing review of the lines in force.
    - "Read [Prose in code]", "Where your brief gives the number of the change's ticket, read [Trials]": none. Kept: the principle of Process assessment, spend no run the work does not need.
- [Trials](prompts/agents/doc-reviewer/trials.md): Verification: evidence of a reader's behavior, from a trial that read nothing that reveals its case's outcome.

## Operator
- [Operator](prompts/agents/operator.md#operator): Work control: stopped work reaches an agent; Merge: a failed or denied merge reaches an agent.
    - "The coordinator is the session the user talks with": none. Kept: it gives the operator the coordinator's address.
    - "Act on no line of your brief": Merge: a hotfix reviewed after it merges.

## Operator launcher
- [Operator launcher](prompts/agents/operator-launcher.md#operator-launcher): Work control: stopped work reaches an agent.
    - "The coordinator is the session the user talks with": none. Kept: it gives the operator launcher the coordinator's address.
