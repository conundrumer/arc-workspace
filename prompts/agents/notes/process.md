# Process notes
- The agents' processes, for changes and for solver passes, each in the project's terms with the name of its process in ISO/IEC/IEEE 12207 beside it, and what each must achieve, in its outcomes and in what holds in each way it can fail. The rules that achieve it stand in the documents of the agents that follow them, and where the tree does not achieve it, that gap is a finding for the process assessment.
- These notes are support under [Decision notes](prompts/agents/notes/decisions.md), and a line of these notes that conflicts with a line of that document is a finding for the process assessment.
- A change to the agents' processes is a change whose Scope touches `prompts/agents/` or `src/operations/`.

## Process assessment (life cycle model management)
- Purpose: keep the agents' processes, as a whole, fit for [The user's goals](prompts/agents/notes/decisions.md#the-users-goals).
- Principles: the third of those goals, and "Spend no run the work does not need", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences).
- Outcomes:
    - These notes give one owner for each process.
    - These notes give, for each kind of work product, the agent that acts on it and the reviews it gets.
        - [Work products](#work-products) gives them.
    - Work that two processes duplicate, an outcome that no owner meets, rules that conflict, a step whose cost is out of proportion to what it finds, and a step or a rule that serves no outcome reach the user before the user asks.
    - Each rule of the notes and of the agent definitions maps to an outcome of these notes.
        - [Traceability matrix](prompts/agents/notes/traceability.md) holds that map.
- Owner: a ticket analyst with a process assessment brief, which an operator launches after a set count of merged changes to the agents' processes.
- Takes from: quality assurance, the fault families, and measurement, the cost of each step. Gives to: every process, as `change` tickets, and the user, as decisions.
- How it can fail:
    - It runs too often: the count of merged changes that launches it bounds its runs.
    - It cuts a check whose value shows only in rare runs: it cuts nothing itself, and brings each cut to the user with the check's cost.
    - It does the root-cause work of quality assurance again: that work looks at one fault family, and the assessment at the processes as a whole.
    - A rule that maps to no outcome guards a case these notes do not name: the assessment judges that rule, and that finding alone cuts no rule.
    - The map of rules to outcomes costs a pass over every rule on each run: the map is made once, and checked again only for a rule or an outcome a change has altered since.

## Requirements (stakeholder needs and requirements definition, system/software requirements definition)
- Purpose: turn the user's words into requirements that a check can confirm, each traced to those words.
- Principles: [The user's part](prompts/agents/notes/decisions.md#the-users-part).
- Outcomes:
    - Each `change` that serves a `request` gives its requirements in its Intent: statements of what holds once the change is made, each one checkable, each traced to the request's `Words`.
    - A part of the `Words` that the change leaves unmet is a decline.
    - When the user adds words, each requirement is checked against them.
- Owner: the ticket analyst writes the requirements, and the ticket reviewer checks each trace.
- Takes from: the coordinator's `request`. Gives to: design, verification and validation.
- How it can fail:
    - A requirement is written to be easy to check, and misses the need: each traces to the quoted `Words`, and validation checks the need in use.
    - A requirement fixes the design too early: it states what holds, and not how.

## Decisions (decision management)
- Purpose: make each decision at the level that holds its context, and record it with its grounds.
- Principles: [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made) and [The user's part](prompts/agents/notes/decisions.md#the-users-part).
- Outcomes:
    - A decision that departs from the user's words, a ruling of the user or a line of [Principles](docs/handbook/principles.md) reaches the user, other than a ticket analyst's decline.
    - A decline carries its defense, and the coordinator judges it before the change merges.
    - Each decision is recorded with what it was made from.
- Owner: the ticket analyst decides, the coordinator judges each decline, and the user rules on each decision that reaches the user.
- Takes from: every process that decides. Gives to: the user, through the coordinator.
- How it can fail: each small choice is given as a decline and floods the coordinator: only a part of a need the user stated counts.

## Design (design definition, architecture definition)
- Purpose: decide the shape of a change's code before it is written: the existing code it uses or extends, each new operation and its module, and how its parts fit.
- Principles: "Keep the process, the code and their semantics in their best state, with maintainable code", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences), and one idea in one place.
- Outcomes:
    - Each `change` that adds a mechanism to code has a design, made from reading the code, that gives the existing operations it uses or extends, and each new operation with its module.
    - An agent other than the one that wrote the design checks it against the code before the build.
    - The Scope covers each file the design names.
- Owner: the ticket analyst writes the design, and the ticket reviewer checks it.
- Takes from: requirements. Gives to: implementation, and configuration management, by the Scope.
- How it can fail:
    - The design names a file outside the Scope: the ticket reviewer checks the Scope against the files the design names.
    - The design is worse than a shape the code shows: the code editor builds that shape, and gives the departure with its reason in its report.
    - The design adds a step before each change: only a change that adds a mechanism to code has one.

## Implementation
- Purpose: build the change to its design and its requirements.
- Principles: the editors' documents.
- Outcomes:
    - Each requirement is shown to hold, by a command and its output, or by a reason.
    - Each item not done is given with its reason, and reaches the agent that decides it.
- Owner: the code editor, the doc editor and the `handbook-expanded` editor.
- Takes from: design. Gives to: verification.
- How it can fail: an editor shows a requirement to hold by rote: verification checks each requirement against the worktree, and not against the report.

## Verification
- Purpose: confirm that each work product meets its requirements before it merges.
- Principles: "check new agent-facing text against each agent it reaches before a pass runs on it", in [Decisions on the agents' documents](prompts/agents/notes/decisions.md#decisions-on-the-agents-documents).
- Outcomes:
    - Each `change` ticket is checked before the build: each requirement traces to the `Words` and can be checked, each claim about the current state holds, and the Scope covers the design.
    - An agent other than its editor checks the built change against each requirement, for documents as for code.
    - For a document change that alters what an agent does, there is evidence before the merge that its reader acts as the requirement states.
    - The lines in force in the agents' documents get a standing review, as the code in the tree gets the code review.
    - A finding in a later round of a review falls only on text that changed since the earlier round.
- Owner: the ticket reviewer for the `change` ticket, a ticket analyst for the built change, the doc reviewer for the form of the documents, and the code reviewer and the gate for the code.
- Takes from: implementation and requirements. Gives to: merge.
- How it can fail:
    - Each review adds cost to every change: the reviews a work product gets are set by its reader.
    - A reviewer checks that a form is filled in: each requirement is checked against the worktree or a run, and not against text.
    - Evidence of a reader's behavior is costly, and one run proves little: it is made only for a line that changes what an agent does, and it is evidence for the reviewer of the change, and no pass or fail on its own.
    - The standing review files many small findings: they go through the fault options of [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences).

## Validation
- Purpose: confirm, after the merge, that the change meets the user's need in use.
- Principles: [The user's goals](prompts/agents/notes/decisions.md#the-users-goals). A change is done when the user's need is met.
- Outcomes:
    - For each change that serves a need the user stated, a run that exercises it shows the need met, or the need goes back to a ticket analyst.
    - A fault found in use is traced to the change, and to the requirement or the design that missed it.
- Owner: the coordinator, which reads the next run that exercises the change.
- Takes from: merge. Gives to: requirements, for a need not met.
- How it can fail:
    - A check is placed on each change, and most never run: only a change that serves a need the user stated gets one.
    - The check is lost before it runs: the `request` waits under `tickets/blocked/` until the check runs.

## Merge (integration, transition)
- Purpose: merge a verified change into `master` and make it live, with no change that skips verification.
- Principles: "keep a merge's gate under a minute", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences).
- Outcomes:
    - Each merge passes the gate and the checks of [merge_change.py](scripts/merge_change.py).
    - A hotfix, a change merged with no ticket review or no review of the change, gets both after it merges.
    - A merge that fails or is denied reaches an agent that acts on it.
- Owner: the operator, and the coordinator for a denied merge.
- Takes from: verification. Gives to: validation.
- How it can fail: the review of a hotfix is skipped because the hotfix works: that review is a step of the operator's command.

## Quality assurance (quality assurance, incident management, problem management)
- Purpose: check that the processes are followed and work, and find the cause of each fault and of each fault family.
- Principles: the fault options and "Prefer simple mechanisms: watch an agent by reading what it does", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences).
- Outcomes:
    - These notes give which review covers each run at its end, so that no run gets two reviews at its end. The checks during a run, such as a hung call or a budget, are apart from those reviews.
        - The module docstring of [monitor.py](src/operations/monitor.py) gives the runs that get a transcript review at their end and those that get an `op-auditor` audit.
        - A transcript review looks for what the brief that `transcript_review` in [briefs.py](src/operations/briefs.py) writes asks of it, and an `op-auditor` audit for the signs [Signs](prompts/agents/op-auditor.md#signs) gives.
    - A fault that recurs after a fix is taken as one family: its common cause is removed, and the fixes that removal makes redundant are named.
- Owner: transcript reviews and `op-auditor` audits for the runs, and the ticket analyst for the causes.
- Takes from: the runs of every process. Gives to: process assessment, the fault families, and every process, as `change` tickets.
- How it can fail: one review at a run's end misses what another would have found: these notes give what each review looks for, and the process assessment checks the split.

## Measurement
- Purpose: give each decision on cost or time a measured figure.
- Principles: "recompute no output or measurement that a file already holds", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences).
- Outcomes: each figure of cost or time in a decision cites the command that produced it.
- Owner: the agent that gives the figure.
- Takes from: the transcripts. Gives to: each decision on cost or time.
- How it can fail: a cited figure rests on a wrong price table: the table cites its source and its date.

## Risk management
- Purpose: find, before the build, how a design can fail, and decide what holds in each case.
- Principles: "Think a design through for how it can fail before it is implemented", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences).
- Outcomes: each way a design can fail, found before the build, that would lose work or leave an output wrong is a requirement that gives what holds in that case.
- Owner: the ticket analyst, as it writes the design.
- Takes from: design. Gives to: requirements.
- How it can fail: each Intent grows a long list of cases: only a case that loses work or leaves an output wrong becomes a requirement.

## Work control (project assessment and control)
- Purpose: see that work moves, and act when it stops.
- Principles: "Pause or serialize agents only where the user agreed to it", in [Launching](prompts/agents/notes/launching.md#launching).
- Outcomes:
    - Work with no step, or with a holder that is gone, reaches an agent that acts on it.
    - Each ticket has one live holder at most.
- Owner: the operator's command, and the coordinator past it.
- Takes from: the tracker and the transcripts. Gives to: the coordinator.
- How it can fail: work that is slow and not stuck is escalated: the trigger is the absence of a step, and not time alone.

## Configuration management
- Purpose: know what each change touches, and keep the changes that touch the same thing in order.
- Principles: "split work that can run in parallel on disjoint files and run its parts at once, with no contention", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences).
- Outcomes:
    - Changes whose Scopes overlap are ordered before the build.
    - Each worktree belongs to one live change.
- Owner: the ticket analyst for `depends-on`, and [merge_change.py](scripts/merge_change.py) for the worktrees.
- Takes from: the Scopes. Gives to: merge.
- How it can fail: an order slows changes that do not conflict: the ticket analyst may override an order with its reason.

## Solver passes (implementation)
- Purpose: solve a task by the Analyze, Create and Refine passes on it.
- Principles: [Decisions on solver work](prompts/agents/notes/decisions.md#decisions-on-solver-work).
- Outcomes:
    - A pass runs its operations on the task its brief gives, and reads what its notes give it to read.
    - A pass writes only under the paths its notes give, and changes no git state.
    - A pass's report gives its judgments, its open items with their reasons, and the tickets it filed.
    - A fault of a document or of a tool that a pass meets reaches a ticket.
- Owner: the passes, with the operator for their launch and the transcript review for the review at a run's end.
- Takes from: the operator's launch on a task. Gives to: quality assurance, by its tickets and its transcript.
- How it can fail: a pass meets a fault and files no ticket on it: the transcript review of the pass reads what the tool and the documents did to its work.

## Work products
- A `request`: a ticket analyst writes the `change` tickets that serve it. Its reviews: the ticket reviewer's check of each requirement's trace to its `Words`, and validation.
- A `change` ticket with its design: a ticket analyst writes it. Its review: a ticket reviewer's, before the build.
- A built code change: a code editor builds it, and the `handbook-expanded` agent the part in the lib and the solvers. Its reviews: a ticket analyst's check of its items, the gate at its merge, and the code review that follows its merge.
- A built document change: the doc editor builds it. Its reviews: the doc reviewer's, a ticket analyst's check of its items, and the `controlled_markdown` check.
- A solver: the Create pass writes it, and each Refine pass reconciles it with the latest report. Its review: the transcript review of each pass that writes it.
- A pass's report: the pass writes it, and a ticket analyst takes the tickets it lists. Its review: the transcript review of that pass.
- A ticket of a fault: a ticket analyst settles it. Its review: the ticket analyst's check of it against the state that produced it.
