+ budget: 21400
* comment: when editing this doc
    - The ticket analyst loads this document by the links of its step documents, before it writes the Intent of a `change` to the agents' processes and at the process assessment; the ticket reviewer loads it by a link of its Checks, for such a `change`. Each serves judging a change to the processes against what they must achieve.
    - Acts, each with its section, one process each, giving its outcomes and how it can fail:
        - Assessing the processes: [Process assessment (life cycle model management)](#process-assessment-life-cycle-model-management).
        - Stating requirements: [Requirements (stakeholder needs and requirements definition, system/software requirements definition)](#requirements-stakeholder-needs-and-requirements-definition-systemsoftware-requirements-definition).
        - Making decisions: [Decisions (decision management)](#decisions-decision-management).
        - Designing a change: [Design (design definition, architecture definition)](#design-design-definition-architecture-definition).
        - Building, checking, validating and merging a change: [Implementation](#implementation), [Verification](#verification), [Validation](#validation), [Merge (integration, transition)](#merge-integration-transition).
        - Quality assurance, measurement, risk, work control and configuration: [Quality assurance (quality assurance, incident management, problem management)](#quality-assurance-quality-assurance-incident-management-problem-management), [Measurement](#measurement), [Risk management](#risk-management), [Work control (project assessment and control)](#work-control-project-assessment-and-control), [Configuration management](#configuration-management).
        - Solver passes and their work products: [Solver passes (implementation)](#solver-passes-implementation), [Work products](#work-products).

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
    - Work that two processes duplicate, an outcome that no owner meets, rules that conflict, a step whose cost is out of proportion to what it finds, and a step or a rule that serves no outcome reach the user before the user asks.
    - The context each run of an agent loads holds only the lines each of its runs needs, and each other line loads by a stated condition before the work that needs it.
- Owner: a ticket analyst with a process assessment brief, which an operator launches after a set count of merged changes to the agents' processes.
- Takes from: quality assurance, the fault families, and measurement, the cost of each step. Gives to: every process, as `change` tickets, and the user, as decisions.
- How it can fail:
    - It runs too often: the count of merged changes that launches it bounds its runs.
    - It cuts a check whose value shows only in rare runs: it cuts nothing itself, and brings each cut to the user with the check's cost.
    - It does the root-cause work of quality assurance again: that work looks at one fault family, and the assessment at the processes as a whole.
    - A rule that serves no outcome may guard a case these notes do not give: the assessment judges that rule, and that finding alone cuts no rule.

## Requirements (stakeholder needs and requirements definition, system/software requirements definition)
- Purpose: turn the user's words into requirements that a check can confirm, each traced to those words.
- Principles: [The user's part](prompts/agents/notes/decisions.md#the-users-part).
- Outcomes:
    - Each `change` that serves a `request` gives its requirements in its Intent: statements of what holds once the change is made, each one checkable, each traced to the user's words in a span of the request, quoted, or to a line of the request's Grounds for what that line itself asks for or states, with a means the coordinator proposed a candidate design.
    - A part of what the request's spans ask for that the change leaves unmet is a decline.
    - When the user adds words, each requirement is checked against them.
- Owner: the ticket analyst writes the requirements, and the ticket reviewer checks each trace.
- Takes from: the coordinator's `request`. Gives to: design, verification and validation.
- How it can fail:
    - A requirement is written to be easy to check, and misses the need: each traces to a quoted part of a span, and validation checks the need in use.
    - A requirement fixes the design too early: it states what holds, and not how.

## Decisions (decision management)
- Purpose: make each decision at the level that holds its context, and record it with its grounds.
- Principles: [How a decision is made](prompts/agents/notes/decisions.md#how-a-decision-is-made) and [The user's part](prompts/agents/notes/decisions.md#the-users-part).
- Outcomes:
    - A decision that departs from the user's words, a ruling of the user or a line of [Principles](docs/handbook/principles.md) reaches the user.
    - A ticket analyst's decline reaches the coordinator in place of the user, with its defense, and the coordinator judges it before the change merges.
    - Each decision is recorded with what it was made from.
- Owner: the ticket analyst decides, the coordinator judges each decline, and the user rules on each decision that reaches the user.
- Takes from: every process that decides. Gives to: the user, through the coordinator.
- How it can fail: each small choice is given as a decline and floods the coordinator: only a part of a need the user stated counts.

## Design (design definition, architecture definition)
- Purpose: decide the shape of a change's code and of its document lines before they are written: the existing code or lines it uses or extends, each new operation and its module, each new rule or fact, its section and the rules and facts on the same act it joins, replaces or retires, and how its parts fit.
- Principles: "Keep the process, the code and their semantics in their best state, with maintainable code", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences), and one idea in one place.
- Outcomes:
    - Each `change` that adds a mechanism to code has a design, made from reading the code, that gives the existing operations it uses or extends, and each new operation with its module.
    - Each `change` that adds or changes a rule or a fact in the agent-facing documents has a design, made from reading those documents, that plans each rule or fact it adds or changes against the rules and facts on the same act that its reader loads for the part of its work that needs it, so that, for each of those, the new rule or fact joins it, replaces it, retires it, or stands beside it as no exception to it.
        - In a document under [agents](prompts/agents), the design puts each rule or fact under the act of that document's spec whose rule it joins, replaces or retires, or revises that spec.
    - Each design gives what it costs and what it gains against the goal of [The user's goals](prompts/agents/notes/decisions.md#the-users-goals) that its change serves.
    - A part whose gain its grounds do not show to exceed its cost is left out, a requirement included, and leaving out a part that serves a need the user stated is a decline.
    - An agent other than the one that wrote the design checks it before the build, against the code, or against the documents and the rules for editing them.
    - The Scope covers each file the design gives.
- Owner: the ticket analyst writes the design, and the ticket reviewer checks it.
- Takes from: requirements. Gives to: implementation, and configuration management, by the Scope.
- How it can fail:
    - The design gives a file outside the Scope: the ticket reviewer checks the Scope against the files the design gives.
    - The design is worse than a shape the code or the documents show: the editor builds that shape, and gives the departure with its reason in its report.
    - The design adds a step before each change: only a change that adds a mechanism to code, or adds or changes a rule or a fact in the documents, has one.

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
    - Each `change` ticket is checked before the build: each requirement traces to the request's spans or Grounds and can be checked, each claim about the current state holds, and the Scope covers the design.
    - An agent other than its editor checks the built change against each requirement, for documents as for code.
    - For a document change that alters what an agent does, there is evidence before the merge that its reader acts as the requirement states, from a trial that read nothing that reveals its case's outcome.
    - The lines in force in the agents' documents get a standing review, as the code in the tree gets the code review.
    - A finding in a later round of a review falls only on text that changed since the earlier round.
- Owner: the ticket reviewer for the `change` ticket, the item checker for the built change, the doc reviewer for the form of the documents and, by its trials, for the evidence of a reader's behavior, a standing doc review for the lines in force in the agents' documents, and the code reviewer and the gate for the code.
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
- Owner: the sweep of `uv run python scripts/file_ticket.py`, which an operator runs after a batch, and the ticket analyst, for a check that no command decides.
- Takes from: merge. Gives to: requirements, for a need not met.
- How it can fail:
    - A check is placed on each change, and most never run: only a change that serves a need the user stated gets one.
    - The check is lost before it runs: it stands in the `request` under `tickets/deferred/` until a batch's runs show it, and a change no run exercises opens for a ticket analyst.

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
    - These notes give which review covers each run, so that no run gets two transcript reviews.
        - The checks during a run are those the module docstring of [monitor.py](src/operations/monitor.py) gives, and the batch profile at a batch's end is the one the brief that `batch_profile` in [briefs.py](src/operations/briefs.py) writes gives.
        - A solver pass gets a transcript review at its end, as the module docstring of [passes.py](src/operations/passes.py) gives, and the batch profile launches one on each other run its brief gives. A transcript review looks for what the brief that `transcript_review` in [briefs.py](src/operations/briefs.py) writes asks of it.
    - A fault that recurs after a fix is taken as one family: its common cause is removed, and the fixes that removal makes redundant are listed.
- Owner: the operator's checks, the batch profile and transcript reviews for the runs, and the ticket analyst for the causes.
- Takes from: the runs of every process. Gives to: process assessment, the fault families, and every process, as `change` tickets.
- How it can fail: one review at a run's end misses what another would have found: these notes give what each review looks for, and the process assessment checks the split.

## Measurement
- Purpose: give each decision on cost or time a measured figure.
- Principles: "recompute no output or measurement that a file already holds", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences).
- Outcomes:
    - Each figure of cost or time in a decision cites the command that produced it.
    - The summed cost of each kind of step over a window, against what it finds, reaches a ticket with no word of the user.
- Owner: the agent that gives the figure, and, for the summed cost, the cost audit, a `general-purpose` agent an operator launches after each process assessment's launch.
- Takes from: the transcripts. Gives to: each decision on cost or time.
- How it can fail:
    - A cited figure rests on a wrong price table: the table cites its source and its date.
    - The audit files a finding a process already covers: it files none on a cause a ticket outside `tickets/closed/` records.
    - The audits of concurrent sessions read the same runs: each audit's window opens at the launch of the latest cost audit of any session.

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
- Purpose: know what each change touches, and build each change after each change whose result it reads.
- Principles: "Save token cost first and time second, and count about 30 minutes saved as worth about $5 of token cost", in [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences).
- Outcomes:
    - A change is built after each change whose result its Design reads.
    - Each worktree belongs to one live change.
- Owner: the ticket analyst for `depends-on`, and [merge_change.py](scripts/merge_change.py) for the worktrees.
- Takes from: the Scopes. Gives to: merge.
- How it can fail: two changes in flight at once that edit one part of a file may conflict in the rebase, and where they do, the later change runs again with a new first editor.

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
- A `request`: a ticket analyst writes the `change` tickets that serve it. Its reviews: the ticket reviewer's check of each requirement's trace to its spans or Grounds, and validation.
- A `change` ticket with its design: a ticket analyst writes it. Its review: a ticket reviewer's, before the build.
- A built code change: a code editor builds it, and the `handbook-expanded` agent the part in the lib and the solvers. Its reviews: the item checker's check of its items, the gate at its merge, and the code review that follows its merge.
- A built document change, the text of each `mctx` fragment a change adds or changes included: the doc editor builds it, from a code editor's draft for a fragment's text. Its reviews: the doc reviewer's, the item checker's check of its items, and the `controlled_markdown` check.
- A solver: the Create pass writes it, and each Refine pass reconciles it with the latest report. Its review: the transcript review of each pass that writes it.
- A pass's report: the pass writes it, and a ticket analyst takes the tickets it lists. Its review: the transcript review of that pass.
- A `refactor` ticket whose title ends in `many ideas in one place`: a code reviewer files it, the code editor that next edits the module it cites splits that module, and the merge of that editor's change closes the ticket or logs the part left unsplit. Its reviews: the gate at that merge and the code review that follows it.
- Each other ticket of a fault: a ticket analyst settles it. Its review: the ticket analyst's check of it against the state that produced it.
