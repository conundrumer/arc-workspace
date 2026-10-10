# Proposal: a root document for the agents' change process, framed by ISO/IEC/IEEE 12207

Draft for the user to judge (request 6-85). `prompts/agents/notes/process.md` holds the parts in force. It is written at the level of a spec. For each process it gives the purpose, the outcomes, the principles, the owning role, and the processes it takes from and gives to. It prescribes no line of the notes or of the agent definitions, and no mechanism.

Evidence is cited by ticket number (`tickets/<status>/<number>_*.md`), by file path, or by a span of session 7fd429fb-e3be-4173-9b0e-df52f507d6a2 ("main" with its transcript line). A scratchpad file named here is in that session's scratchpad directory, which is not kept. Counts were taken over the tracker on 2026-10-10 at master `cb224960`, with the command given. Each part ends with the known issues it solves, the ones it leaves, and how it can fail. Where a way of meeting a failure has no evidence behind it, it is reasoning, and it says so.

## The need

- The agents' process was built from incidents, one rule at a time. On 2026-10-09 the coordinator listed six practices that the session had rebuilt that way: acceptance criteria (6-83), requirements traced to the user (6-67, 6-70), change control, review after a hotfix (6-77), escalation of stuck work (6-68, 6-69) and incident review (6-37). Each one lands in a different document (main, 22:59:21). The user agreed: "yes you got it" (23:00:51).
- Rules are added per incident. Commits that touch `prompts/agents/` per day were 23, 73, 59, 33, 18 and 10 from 2026-10-04 to 2026-10-09 (`git log --since=2026-10-01 --format=%ad --date=short -- prompts/agents | sort | uniq -c`). Of the 21 `* comment` lines under `prompts/agents/`, 16 cite the ticket, run or transcript that the line came from, and 2 more cite a task or a code review (`grep -rn "\* comment" prompts/agents`).
- Rules in different documents already conflict. `prompts/agents/notes/launching.md`, Launching, has an Intent "give no account of how each way the edit can fail is met". Open change 6-86 has each foreseen failure be an Intent item that "gives what holds in that case".
- Nothing finds the overlaps between processes. End-of-run audits were added (change 6-17) while solver passes that report in form already got a transcript review that reads the same transcript. No agent raised the overlap. The user found it by asking: "what is a transcript review? i thought op-auditor took over" (6-161), and "all agents thought the overlap was fine and no one raised it to me before i asked?" (6-85 Words).
- Nothing acts on a fault family. The analyst on 2-596 named a recurring fault and filed nothing: "This is one more instance of the fault in 2-492 and 2-529, which repeats after their fixes 2-495 and 2-530. I filed no change for that recurrence."

## Choice of frame

- **Proposed: ISO/IEC/IEEE 12207:2017**, the software life cycle processes. It names a set of processes and gives each one a purpose and outcomes. Its tailoring annex lets a project drop or merge processes with a stated reason.
    - For: every practice the session rebuilt has a named process in it (table below). Its outcome lists are at the spec level the user asked for.
    - Against: the evidence that the frame finds gaps a lighter frame would not is weak. The two gaps this proposal leans on most were found by the user, not by a frame: the design of a change's code (00:08:19) and the overlap of audits and reviews (01:47:24). Validation is the one gap here that no ticket asked for, and the frame names it.
    - Ground for the standard's content: the names, the clause numbers and the tailoring annex are given from knowledge of the 2017 edition. They were not checked against the text, which is not in the repo. Someone with the text should confirm them before the root cites them.
- **Other option: adopt 12207 completely, with a role for each process it places.** Each process in the table below gets its own agent: a requirements writer, a designer, a risk analyst, a validator, a process assessor, and so on. The ticket analyst then keeps only the causes of faults and the decisions.
    - For: each role's document holds one process, so no one agent carries need, requirements, design, risk and causes together. That load is the user's question. Today the ticket analyst's rendered context is 7145 words (`uv run python scripts/context.py context agent ticket-analyst | wc -w`). Under the default, design definition (the ruling) and requirements (open change 6-86) are added to it. No run shows the analyst failing from load, and no evidence was looked for on that.
    - Against: each handoff between roles is a place where work stops or a part is lost. The evidence of that cost: 6-37 passed between three operators from 17:56 to 20:11, and nothing reached the coordinator (6-68). A design and a Span written by the same analyst still disagreed (6-37), and split roles add a handoff at that same point. The ticket review of change 6-87 took four reviews and three revisions before any text existed (6-87 log), which is the cost of one more review round per change. There are 14 agent definitions under `prompts/agents/` today (`ls prompts/agents/*.md | wc -l`), and the table places about 13 processes. Each new role adds a definition, a brief form and a launch by the operator for each change. That cost was not measured.
    - Outside practice (see Outside practice): MetaGPT's ablation found more roles gave fewer revisions at 1.5x the cost. Practitioner reports found the token cost and the losses at handoffs rise with each agent. No source adopts a full process standard.
    - Solves: the same issues as the default, by the same outcomes. It also solves the load on one analyst, if that load is real. Leaves: no issue on record that the default leaves and this option solves.
- **Other option: a light set of named practices** (acceptance criteria, change control, blameless postmortems), with no standard behind them. It costs fewer lines. No evidence was looked for on how it would do.
- **Other option: a quality management standard** (ISO 9001) or a maturity model (CMMI). They state what an organization must have, more than how a change moves from need to release. No evidence was looked for.

## Outside practice

The figures below come from a web search by a Sonnet agent on 2026-10-10. Its fetcher summarizes pages with a small model, so quotes are as that agent returned them, and no figure was checked again here. Of the sources, AutoGen, CrewAI, AgentVerse, Devin and OpenAI were not opened. SWE-agent, OpenHands and Agentless were read only as abstracts, and the surveys only as search snippets.

- **Anchor to a standard.** No source found anchors to 12207. MetaGPT follows "SOP in software development" in a fixed sequence (https://arxiv.org/html/2308.00352). ChatDev uses a waterfall chat chain (https://arxiv.org/html/2307.07924v5). Ha et al. compared Waterfall, V-Model and Agile in MetaGPT: median tokens were 13,720, 29,783 and 30,787, and "process rigor does not guarantee higher code quality" (https://arxiv.org/html/2509.13942v1). This differs from the proposal: outside practice borrows a light life cycle model, not a full process standard.
- **A role for each process (the full-adoption option).** MetaGPT's role ablation (Table 3), going from an engineer alone to all roles: human revisions fell from 10 to 2.5, executability rose from 1.0 to 4.0 (of 4), and expense rose from $0.915 to $1.385. ChatDev ablated only all roles at once, and its quality fell from 0.3953 to 0.2212. Anthropic reports that multi-agent runs use "about 15x" the tokens of chat (https://www.anthropic.com/engineering/multi-agent-research-system). Its long-running harness cost over 20x a solo run, and components were removed one at a time as models improved (https://www.anthropic.com/engineering/harness-design-long-running-apps). Cognition argues against splitting: "Actions carry implicit decisions, and conflicting decisions carry bad results" (https://cognition.com/blog/dont-build-multi-agents). Anthropic: "find the simplest solution possible, and only increase complexity when needed" (https://www.anthropic.com/engineering/building-effective-agents). No source ablated each role of a full set. These systems build one program per run. They do not maintain a process across many changes, as this project's agents do.
- **Design definition.** In MetaGPT, adding the Architect cut revisions from 6.5 to 4.0. In Anthropic's harness, the planner was kept because "without it the generator under-scoped the app". Both give the design to a role apart from the coder. That supports a design made before the code, and does not say which role makes it. The proposal's default gives it to the role that also writes the requirements, as MetaGPT's product manager and architect do not.
- **Verification.** No source reviews the plan before the build, as this project's ticket review does. Reviews are of code or of the running app. Anthropic's evaluator, before tuning, "talked itself into approving the work". The MAST study (https://arxiv.org/html/2503.13657; 1,642 traces of 7 systems) puts task verification failures at about 23.5% of failure modes, with incorrect verification at 9.1% and incomplete verification at 8.2%, and finds them "even in successful runs". In MAST, a high-level verification step gave +15.6% on ProgramDev, though the authors add that the interventions "do not constitute substantial improvements". This bears on the outcome that a role other than the editor checks the built change.
- **Handoffs and duplicated work.** MAST classes 32.4% of failure modes as misalignment between agents, among them reasoning-action mismatch at 13.2% and loss of history at 2.8%, and 15.7% as step repetition. Anthropic saw duplicated work from vague delegation, and fixed it with task descriptions that give the objective, the output form and the boundaries. This matches the session's evidence on 6-68 and on the overlap of 6-161.
- **Review of the process as a whole.** No source runs one inside the system. MetaGPT: "each software project is executed independently". The closest practices are outside the system: Anthropic re-tests which harness parts are load-bearing at each model release, and MAST built its taxonomy from traces. This differs from the proposal, which makes the assessment a recurring step of the process.

| Practice the project rebuilt | Process of 12207:2017 | Clause |
|---|---|---|
| The user's words to a request (6-67, 6-83) | Stakeholder needs and requirements definition | 6.4.2 |
| The Intent of a `change` as requirements (6-86) | System/software requirements definition | 6.4.3 |
| Declines and decisions brought to the user (6-67, 6-70) | Decision management | 6.3.3 |
| Code shape decided before the code (6-87, duplicates) | Design definition | 6.4.5 |
| Editors' edits | Implementation | 6.4.7 |
| Ticket review, doc review, code review, gate | Verification | 6.4.9 |
| Need met after the merge (6-36, 6-63) | Validation | 6.4.11 |
| Merge, hotfix review (6-77, 6-82) | Integration; Transition | 6.4.8; 6.4.10 |
| Transcript reviews, op-auditor audits, root-cause work | Quality assurance (it includes the handling of incidents and problems) | 6.3.8 |
| Cost and time profiles | Measurement | 6.3.7 |
| "Think through how it fails" | Risk management | 6.3.4 |
| Stuck work, holders, budgets (6-68) | Project assessment and control | 6.3.2 |
| Tracker, worktrees, `depends-on` | Configuration management | 6.3.5 |
| Review of the processes as a whole (6-161) | Life cycle model management | 6.2.1 |

## The root document

- One document, the root of the agents' change process. For each process of the frame that the agents run, it states the purpose, the outcomes (each one checkable), the principles, the owner, and the processes it takes from and gives to. It uses the project's terms, with the standard's name beside them.
- Its place in the order of authority: `prompts/agents/notes/decisions.md`, Rule and intent, already orders the user's goals, Principles (the theory of solvers) and the support lines. The root is support in that order. Its principles of process derive from the user's goals and cite them. Where the root and a line of `decisions.md` conflict, `decisions.md` rules, and the conflict is a finding for the owner of life cycle model management.
- Every other document of the process (the notes, the agent definitions, the operator's code) serves an outcome of the root. A line that serves none is a finding for that owner, who judges whether it guards a real case that the root does not name yet. The line is not cut on that finding alone.
- The root holds what the rules must achieve, not the rules. A rule stays in the document of the agent that follows it.
- Readers: the owner of life cycle model management, and the agent that writes or reviews a change to a process. Other agents read their own rules, as now, so the root adds nothing to their context. Most agents own a process, but an agent works by its rules, and the root is read only when a process changes.
- Solves: rules that conflict across documents (the launching.md and 6-86 case above), because both trace to one outcome.
- Leaves: it makes no agent follow it. Each process below needs its owner.
- How it can fail:
    - The root and `decisions.md` both state principles, and they drift apart. Meets it: the order of authority above.
    - The mapping from rules to outcomes becomes busywork. Meets it (reasoning): the mapping is made once, and then checked only on a change to the root or to a rule.
    - A rule is cut because it maps to no outcome while it guards a case the frame does not name. Meets it: the owner judges it, as above.

## Processes

### Life cycle model management (6.2.1), with tailoring

- Purpose: keep the agents' processes fit for the user's goals, as a whole.
- Principles: the user's goal of reaching the work "with less of the user over time, at low cost" (`prompts/agents/notes/decisions.md`, The user's goals); "Spend no run the work does not need" (The user's preferences).
- Outcomes:
    - The root lists one owner for each process.
    - Work that two processes duplicate, and an outcome that no process produces, reach the coordinator, and from there the user, before the user asks.
    - The root lists, for each kind of work product, the reader that acts on it and the reviews it gets.
- Takes from: quality assurance (fault families), measurement (cost of each process). Gives to: every process, as changes.
- Owner: a process review, run each time a set count of changes to the agents' processes has merged. A ticket analyst with that brief can run it, with no new agent.
- Today: no role. The retro skill is deprecated. The coordinator, asked why no one raised the overlap, gave: "Each one judged only its own ticket. None of those tickets mentions transcript reviews, so no agent compared the two checks" (main L7222, 01:47:42).
- Evidence:
    - 6-17 added end-of-run audits. Its Intent, Motivation and Grounds hold no line on transcript reviews, which `src/operations/passes.py` `run` already launches for each solver pass that reports in form, in the pipelines the operator runs (6-170 Grounds). The overlap stood until the user asked (6-161).
    - Tailoring: a proposal that only the user reads went through a `change` ticket. Change 6-87 got four ticket reviews and three revisions by an analyst in one night, before any text of the proposal existed (6-87 log, 00:35:50 to 01:52:18). The user: "whats the point of that" (01:49:11), and "this is a problem. add it directly. and stop the ticket" (01:49:44). The user then ruled that an analyst writes the proposal and a second analyst reviews its evidence and reasoning (6-85 log, 01:52:54).
- Solves: the overlap no one raised (6-161), and the tracker's overhead on a document only the user reads (6-87).
- Leaves: a duplicate inside one agent's document, below the level of processes.
- How it can fail:
    - The review runs too often. Process changes merge often (10 to 73 commits a day to `prompts/agents/`). A trigger per merged mechanism would fire about as often as a clock. Meets it: the trigger is a count of merged changes, so its cost is bounded by that count. No rate has been measured to set the count.
    - The review recommends cutting a check whose value shows only in rare runs. Meets it: it brings the recommendation, with each check's cost from the profiles, to the coordinator, and cuts nothing itself.
    - It overlaps with root-cause work. Meets it: root-cause work looks at one fault family, and this review looks at the processes. The root states the line between them.

### Stakeholder needs and requirements definition (6.4.2), and requirements definition (6.4.3)

- Purpose: turn the user's words into requirements that a check can confirm, each one traced to those words.
- Principles: the user's words are the need (`prompts/agents/notes/decisions.md`, The user's part: "An option that departs from the user's words ... has such a reason, which no reframe removes").
- Outcomes:
    - Each `change` that serves a request has requirements: statements of what holds once the change is made, each one checkable, each one traced to the quoted Words it serves. No separate statement of the need is kept: the Words are the need, and a second copy would drift ("keep no state in a second copy", The user's preferences).
    - A part of the Words that the change leaves unmet is a decline (decision management).
    - When the user adds words, each requirement is checked against them.
- Takes from: the coordinator's `request`. Gives to: design definition, verification, validation.
- Owner: the ticket analyst writes the requirements. The ticket reviewer checks each trace.
- Today: the Intent of a `change` is the only statement of requirements. `prompts/agents/notes/launching.md` limits it to "the meaning to state, the case that shows the need, and the span the edit may change".
- Evidence:
    - The Intent did not match the Words: 6-70 passed its ticket review at 20:48:29 with a scope wider than the need. The user had to add at 21:01:11: "declined user requests get sent to us, not reuqests intiiated by agents" (6-67 Words).
    - A foreseen case was given as advice and dropped: 6-83 Words, "so the analyst said it might be an issue, and then it gets dropped? how about the analyst gives requirements?".
    - Intent items that are tasks, not checkable statements: 98 of 326 `change` tickets have an Intent item that asks an editor to think a case through (a python search for `think[^.\n]{0,40}through` within `## Intent` of each `kind: change` ticket). 6-70's last item is one: "Have the editors think through how the hold can fail".
    - Later words: 21 of 63 requests had words added after filing. On 6-85, eight coordinator log lines record the user's later words or rulings.
- Solves: an Intent that does not match the Words (6-70), and items that are tasks (the 98). Open change 6-86 already carries the second.
- Leaves: a need the user did not say. The coordinator holds that context (6-67 Words: "you already have the context that i specifically asked for it").
- The action a request asks for:
    - Outcome: the analyst's resolution of a `request` states the action it takes: what is made, by which role, and when. The coordinator checks that action against the user's words before it runs.
    - Evidence:
        - The user's "make hte proposal write into drafts. i want to defer this" and "no i mean. the request is to write a draft" (6-85 Words) were resolved as "deferred by the user; the proposal waits until the user takes it up" (6-87 log, 2026-10-09T23:04:55), so no proposal was written until the user asked where it was.
        - 6-87 gave the writing of the proposal, research on the evidence included, to a doc editor, which edits documents by rule and does no research. The user ruled that a ticket analyst writes it (6-85 Words, 2026-10-10T01:52:33).
        - On later words, analysts judged 6-85 again and wrote that "its resolution stands" (6-85 log, 00:44:52 and 01:49:38) with no check that the resolution's action still matched the words.
    - Solves: a resolution whose action departs from the user's words although each requirement traces to them.
    - How it can fail: the coordinator's check adds a round to each request. Meets it: the check reads one stated action, and only on a `request`.
- How it can fail:
    - Requirements written to be easy to check, not what the user needs. Meets it: each one traces to quoted Words, and validation checks the need in use.
    - Requirements fix the design too early. Meets it: a requirement states what holds, not how.

### Decision management (6.3.3)

- Purpose: make each decision at the level that holds its context, and record it with its grounds.
- Principles: The user's part, and How a decision is made, in `prompts/agents/notes/decisions.md`.
- Outcomes:
    - A decision that departs from the user's words, a ruling of the user, or a line of Principles reaches the user.
    - A decline of part of a need the user stated carries its defense, a concrete cost or risk. The coordinator judges it before the change merges.
    - Each decision is recorded with what it was made from.
- Takes from: every process that decides. Gives to: the user, through the coordinator.
- Owner: the analyst decides. The coordinator judges declines. The user rules on what reaches the user.
- Today: `prompts/agents/notes/decisions.md`. A decline has no field. "decline" appears in 5 ticket files, all from 2026-10-09 on.
- Evidence:
    - 6-37: the user's message case was dropped twice, at 17:54:11 and at 20:08:42, "by the fault line's third option". The coordinator vetoed it at 20:38:33, after the user spoke in 6-67.
    - 18 log lines in 15 files block a ticket on the user. By their notes, about 5 are decisions with options, and the rest are holds on the user's own work. No field tells them apart.
- Solves: the silent decline (6-37). Open change 6-70 carries this part.
- Leaves: a decision the analyst does not see as one.
- How it can fail: every small choice is called a decline and floods the coordinator. Meets it: only a part of a need the user stated counts (6-67 Words, 21:01:11).

### Design definition (6.4.5), with architecture definition (6.4.4)

- Purpose: decide the shape of a change's code before it is written: which existing code it uses or extends, which new operations it adds and where each lives, and how its parts fit.
- Principles: "Keep the process, the code and their semantics in their best state, with maintainable code" (The user's preferences); one idea in one place (`prompts/agents/notes/code.md`, place-kinds).
- Outcomes:
    - Each change that adds a mechanism to code has a design, made from reading the code. It names the existing operations it uses or extends, and each new operation with its module.
    - A second role checks the design against the code before the build.
    - The Scope covers each file the design names.
- Takes from: requirements. Gives to: implementation, and the Scope (configuration management).
- Owner: see the decision at the end.
- Today: no role. The analyst designs the behavior. `prompts/agents/notes/decisions.md` has "Leave the judgment of how the code is written to the agents that read it". `prompts/agents/code-editor.md` has the editor "search every package for what already computes ... Then decide the shape", alone. The code reviewer judges the shape after the merge.
- Evidence:
    - Code review: 372 `refactor` tickets from the code reviewer. 47 carry "one idea in two places" in the title, and 40 of them were fixed. Other titles name a repeat ("twice", "two places"), so 47 is a lower bound.
    - The trace of 16 duplicates (scratchpad `duplicates-why.md`):
        - About 8 come from a search that missed the existing code, or from the editor's choice to write its own: 6-40 `SENT_BY_MESSAGE`, 6-42 `sent_times`, 2-517, 2-584, and the class (b) rows other than 2-809. A design made from the code could have named the existing operation in these.
        - 5 are copies written in the same run (6-43, 2-502, 2-554, 2-737, 6-40). The study: "A search before writing cannot find these, because the second copy is written while the editor builds the first." A design addresses them only if it lists each new operation at that grain. No evidence tests that.
        - 1 is forced by a package boundary (2-809).
    - The design and the Span disagreed: 6-37's design needed `scripts/operator_reads.py` and `scripts/agent_launches.py`, which its Span left out. The same analyst wrote both. The editor reported `blocked`, and the change passed between three operators from 17:56 to 20:11 (6-68).
    - Code editors filed 140 `question` tickets on their own changes while they worked, and 96 closed `fixed by change N`. Gaps in the design are found during the build.
- Solves: about 8 of the 16 traced duplicates, and a Scope that misses a file the design needs (6-37), since the Scope is checked against the named files.
- Leaves: the duplicate a package boundary forces (2-809). The same-run copies, unless the design lists new operations at that grain. And a design role that misses the existing code as the editor did. No evidence shows that a design role searches better.
- How it can fail:
    - The design names files outside the Scope (6-37). Meets it: the second role checks the Scope against the named files. Making the design first is not enough, since in 6-37 one analyst wrote both.
    - The editor follows a wrong design where the code shows a better one. Meets it: the editor may depart from it with a stated reason, which the reviewer judges.
    - It adds a round before each change. It applies only to changes that add a mechanism to code. Their count was not measured, so the cost is not bounded here.
- The design of a change to the agents' documents:
    - Outcome: each change that adds or moves a rule of the agents' documents has a design, made from reading the documents, that gives the document and section the rule goes in, the existing rule it extends or replaces, and each line it must not repeat. The editor keeps the wording.
    - Evidence: the need behind this proposal, that each practice rebuilt from an incident lands in a different document (The need). Rules in different documents already conflict: `prompts/agents/notes/launching.md` against open change 6-86 (The need). The user asked for it: "what about docs" (main, 2026-10-10T02:21:52).
    - Owner: the same role as the design of code, as the decision at the end gives.
    - Leaves: the wording, which the doc editor writes and the doc reviewer checks.
    - How it can fail: the design places a rule in a section whose readers do not reach the case. Meets it: the design names the readers of that section, and the doc reviewer checks them against each reader's rendered context.

### Implementation (6.4.7)

- Purpose: build the change to its design and requirements.
- Principles: the editor's documents.
- Outcomes:
    - Each requirement is shown to hold, by a command and its output, or by a reason.
    - Each item not done is stated with its reason and reaches the role that decides it.
- Takes from: design definition. Gives to: verification.
- Owner: the editors (code editor, doc editor, `handbook-expanded`).
- Today: `prompts/agents/code-editor.md`, and `prompts/agents/notes/changes.md`, Carrying a change.
- Evidence:
    - 6-68: a `blocked` report counted as passed (`src/operations/reports.py`, `DONE = ("done", "blocked")`), and the merge was printed for a change with no edit. Change 6-69 fixed it.
    - Build faults that passed the checks and were found by a later code review: 6-50, "`audit_of`: the alert file of an auditor's finding is never read" (fixed by 6-54), and 6-91 and 6-92 on hotfix 8e871af9.
- Solves: the dropped `blocked` item, as an outcome a later change cannot undo unnoticed.
- Leaves: build faults the checks cannot show (6-50). Verification against requirements is the net.
- How it can fail: "shown to hold" becomes a form filled in by rote. Meets it: verification checks it against the worktree, not the report.

### Verification (6.4.9), for code and for documents alike

- Purpose: confirm that each work product meets its requirements, before it merges.
- Principles: the user's words while this proposal was written: "docs need the same strict reviews too" (as code).
- Outcomes:
    - The plan (the `change` ticket) is checked before the build: each requirement traces to the Words and can be checked, each claim about the current state holds, and the Scope covers the design.
    - The built change is checked against each requirement by a role other than its editor. This holds for documents as for code.
    - For a document change that alters what an agent does, there is evidence before the merge that its reader acts as the requirement states. How that evidence is made is left to the implementation.
    - Lines already in force in the agents' documents get a standing review, as code already in the tree gets the code review.
    - A finding in a later round of a review falls only on text that changed since the earlier round.
- Takes from: implementation, requirements. Gives to: integration.
- Owner: the ticket reviewer for the plan. A change reviewer for the built change (6-86 gives this to a ticket analyst). The doc reviewer for the form of documents. The code reviewer and the gate for code.
- Today:
    - Ticket review: 537 `finding:` lines by ticket reviewers, on 187 of the 326 `change` tickets. 72 had three or more findings, and the most was 23 (2-645). The lines are in scratchpad `proposal-6-85/rev-findings.txt`.
    - A change to code alone gets no review of whether it does what its Intent states. `carry` runs `doc_review` only where a doc editor took part (6-86 Grounds).
    - A change to documents gets a doc review by the steps of `docs/handbook/editing.md`, Reviewing a change. It reads each reader's rendered context, and checks form, conflicts with lines outside the change, and new powers. No step checks the change against its Intent: the reviewer reports "nothing on a decision the one who asked for the change gives as already settled". No step runs a reader on the edited text.
    - Code has the gate, pyright, pytest and a standing code review of the tree. Documents have none of the gate's kind, and no standing review of lines in force. One audit of lines in force was run once (2-360).
- Evidence:
    - Review rounds as a recurring fault: "draft 2-569 took seven rounds, draft 2-575 five, and draft 2-579 ten" (2-596). The fixes 2-495 and 2-530 did not end it. One cause: "a review stops at one finding, or checks only the parts its brief says were revised" (2-529 log). For documents, `prompts/agents/doc-editor.md` cites change 17, where "each fix brought the next finding" across four messages.
    - Change 2-729 closed `fixed` while its editors left most places undone, "27 of which no edit addressed" (2-787).
    - Document changes that passed review and failed in use:
        - 2-422: "change 2-420 added a command-notes line whose trigger an agent cannot know when it acts, and no step before the user caught it". Its Impact: "The line passed the analyst, two ticket reviewers and the coordinator".
        - 2-359: "The doc reviewer (aa59a8450989878c4) judged only the wording, and commit 35f7919f added the line". Later runs did not follow the line (2-338), and 2-351 widened it.
        - 6-39: a line of `prompts/agents/notes/commands.md` stated that a hook exempts a wait, and the hook still blocked it. No step checked the line's claim against the tool.
        - 2-360: "An audit of the 139 instruction lines added to `prompts/agents/` since 2026-10-05 found six places that fail". For two of them, the cause was the reviewer's exemption for what an Intent settles, which 2-365 narrowed.
- Solves: the code-only change with no check against its Intent (6-86). A document change checked for form and not for what its readers then do (2-422, 2-359, 6-39). Lines in force that no one reviews again (2-360). Rounds that find one fault at a time (2-596).
- Leaves:
    - A fault that only use shows, such as a hook a new session reads at its start (2-350). That belongs to validation.
    - An agent that departs from a line that reads right. 2-402: "Of the five Sonnet supervisors since change 2-334, four departed from their poll or end rules"; the fix was a model change. `decisions.md` holds that "An agent's choice that departs from its documents is no fault of its documents".
- How it can fail:
    - Each review adds cost to every change. Meets it: tailoring sets the reviews by the reader of the work product.
    - Reviewers check that a form is filled, not that the thing holds. 6-37's reviewer checked that a "think through" item was present (6-37 log, 17:50:35). Meets it: a requirement is checked against the worktree or a run, not against text.
    - Evidence of a reader's behavior is costly, and one run of a model proves little. Meets it (reasoning): it is needed only for a line that changes what an agent does, and it is evidence for the change reviewer, not a pass or fail on its own.
    - The standing review of documents files many small findings, as transcript reviews do (quality assurance). Meets it: its findings go through the fault options of `decisions.md`, The user's preferences, as any other.

### Validation (6.4.11)

- Purpose: confirm, after the merge, that the change meets the user's need in use.
- Principles: the user's goals; a change is done when the user's need is met, not when it merges.
- Outcomes:
    - For each change that serves a need the user stated, a run that exercises it shows the need met, or the need goes back to the analyst.
    - A fault found in use is traced to the change, and to the requirement or the design that missed it.
- Takes from: integration. Gives to: requirements (a need not met).
- Owner: the coordinator, which reads the next run that exercises the change. Transcript reviews run only on solver passes (`src/operations/passes.py`), and most changes serve the operations and the agents, so they cannot own this.
- Today: a Scope may place a check after the merge (`prompts/agents/notes/changes.md`, Merging a change). Requests close with "fixed by change N", with no line that checks the need.
- Evidence:
    - 6-16 closed `fixed` at 16:56:08. 47 minutes later the user filed 6-36: "operator was sleep waiting in fg and blocked 3 messages". 6-16 had listed that case for its editor to think through.
    - 6-17 closed `fixed` at 17:23:15. The own-run audit loop followed (6-63 at 19:58:05, with duplicates 6-72 and 6-76), until 6-64 at 22:25:20.
    - Change 2-837 merged as 1aa9240f at 2026-10-08T16:09:42Z. About 3.5 minutes later, 2-853 was filed: "it launches ticket analysts on steps from messages that earlier calls of the command already handled".
- Solves: the gap between "merged" and "works for the user" (6-36, 6-63, 2-853). They are found by a step, not by the user.
- Leaves: a need that no run exercises soon.
- How it can fail:
    - A check is placed on each change, and most never run. Meets it: only changes that serve a need the user stated get one.
    - The check is lost before it runs. No lost check is on record. 6-73's analyst gave "no past change arose from a lost check" (6-73 log, 21:43:48). Meets it: the request waits under `tickets/blocked/` until the check runs. Left open, an analyst would take it and judge it again.

### Integration (6.4.8) and transition (6.4.10)

- Purpose: merge a verified change into `master` and make it live, with no change that skips verification.
- Principles: "keep a merge's gate under a minute" (The user's preferences).
- Outcomes:
    - Each merge passes the gate and the checks of `scripts/merge_change.py`.
    - A change merged with no ticket review or no change review (a hotfix) gets both after it merges.
    - A merge that fails or is denied reaches a role that acts on it.
- Takes from: verification. Gives to: validation.
- Owner: the operator, and the coordinator for a denied merge.
- Today: `scripts/merge_change.py`, and `prompts/agents/notes/changes.md`, Merging a change and A denied merge.
- Evidence:
    - Three hotfixes on master (`git log master --oneline -i --grep=hotfix`): f6be0ebc, 8e871af9, cb224960. Code review later found faults in two of them: 6-81 on f6be0ebc, and 6-91 and 6-92 on 8e871af9. Request 6-77: "hotfixes should get reviews after they're resolved".
    - The merge call was blocked by the timeout hook (6-69, 6-93), and the operator logged it and did not make the call again (6-144).
    - Merges denied by the classifier: 2-3, 4-47.
    - Rebase conflicts on record: 2-222, and the one in `tickets/closed/1791220161-a62b1740b0c751183-transcript-review-2.md`, which cost a rerun by a new editor.
- Solves: the unreviewed hotfix (6-77, change 6-82), and a denied merge no one acts on.
- Leaves: nothing more that the evidence shows.
- How it can fail: the review after a hotfix is skipped because the hotfix already works. Meets it: the hotfix's review is a step of the operator's command, not a choice.

### Quality assurance (6.3.8), with the handling of incidents and problems

- Purpose: check that the processes are followed and work, and find the cause of each fault and each family of faults.
- Principles: the fault options of `decisions.md`, The user's preferences; "Prefer simple mechanisms: watch an agent by reading what it does".
- Outcomes:
    - The root states which reviewing process covers which run at its end, so that no run gets two end-of-run reviews. Checks during a run (a hung call, the budget) are separate from them.
    - A fault that recurs after a fix is treated as one family. Its common cause is removed, and the fixes it makes redundant are named.
- Takes from: every process's runs. Gives to: life cycle model management (fault families), and fixes as `change` tickets.
- Owner: transcript reviews and op-auditor audits for runs. The ticket analyst for causes.
- Today: transcript reviews (`prompts/agents/notes/launching.md`, Launching), op-auditor audits (`prompts/agents/op-auditor.md`), and the analyst's step on earlier instances (`prompts/agents/ticket-analyst.md`, Tickets, step 5).
- Evidence:
    - The overlap: see life cycle model management (6-161, 6-170).
    - Low yield: of 66 closed transcript-review tickets, 44 closed `wontfix` (67%), against 15% for the whole tracker. 38 of the 44 give a loss in seconds, from 2 s to 95 s. Before 6-17, 81% of 105 audits found no sign (6-17 Motivation).
    - Recurrence: 2-144 made the step on earlier instances, after "the supervisor's alerts were patched one incident at a time". After that, 2-596 named a recurrence and filed nothing, and 2-579's reviewer found that "the analyst on 2-526 had step 5 ... and skipped both". 6-17 removed a fault that four patches had fixed one form at a time (2-867, 2-871, 2-877, 2-881). 6-145: the price fault recurred after 2-681.
- Solves: the overlap (6-161), and a recurrence that is named and not acted on (2-596).
- Leaves: a family whose instances are filed under different targets, which step 5 reads by target and does not find. The low yield of transcript reviews: their findings already go through the fault options, which close most of them at a measured loss.
- How it can fail: one end-of-run review per run misses what the other would have caught. Meets it: the root states what each one looks for, and the process review checks the split.

### Measurement (6.3.7)

- Purpose: give each decision on cost or time a measured figure.
- Principles: "recompute no output or measurement that a file already holds" (The user's preferences).
- Outcomes: each cost or time figure in a decision cites the command that produced it.
- Takes from: transcripts. Gives to: every decision on cost.
- Owner: the agent that states the figure.
- Today: `scripts/profile_runs.py`.
- Evidence: 6-145, "the coordinator gave two cost agents Opus 5 prices as Opus 5.5 prices, typed into the briefs, and the figures those agents returned were wrong", one more instance of 2-680 and 2-681. `ops-costs.md` priced one model at another's rates, since the table had no row for it.
- Solves: figures stated from memory (6-145).
- Leaves: a price table that is out of date (6-143).
- How it can fail: a cited figure is trusted where the table is wrong. Meets it: the table cites its source and date.

### Risk management (6.3.4)

- Purpose: find, before the build, how a design can fail, and decide what holds in each case.
- Principles: "Think a design through for how it can fail before it is implemented" (The user's preferences).
- Outcomes: each failure case found before the build that would lose work or leave an output wrong is a requirement, which states what holds in that case.
- Takes from: design definition. Gives to: requirements.
- Owner: the analyst, with the design role.
- Today: 98 `change` Intents hold a "think it through" item (the search under requirements). The ticket reviewer checks that such an item is present.
- Evidence:
    - Of four distinct failures after the merges of 6-16, 6-17 and 6-37, one was a case its Intent listed (6-36, from 6-16). One was beside a listed case (the own-run audit loop, 6-63, from 6-17). Two were not listed (6-26 and 6-28 from 6-16, and 6-68 from 6-37).
    - No editor run shows a listed case met in text or a check before its first edit (scratchpad `editor-think-through.md`). The thinking blocks are redacted, so this does not prove the editors skipped it.
- Solves: a listed case no one acts on (6-36). This is the mechanism of open change 6-86. The part adds only its place in the frame.
- Leaves: cases no one foresees (6-26, 6-68). Validation is the net for them.
- How it can fail: each Intent grows a long list of cases. Meets it: only cases that lose work or leave an output wrong become requirements.

### Project assessment and control (6.3.2)

- Purpose: see that work moves, and act when it stops.
- Principles: "Pause or serialize agents only where the user agreed to it" (`prompts/agents/notes/launching.md`).
- Outcomes:
    - Work with no step, or with a holder that is gone, reaches a role that acts on it.
    - Each ticket has at most one live holder.
- Takes from: the tracker and the transcripts. Gives to: the coordinator.
- Owner: the operator's command, and the coordinator past it.
- Today: the operator's command, and holder release (29 `released` log lines on 24 tickets, `grep -hE '^20\S+ \w+ \[[^]]*\]: released'`).
- Evidence:
    - 6-68: 6-37 passed between three operators from 17:56 to 20:11, and "nothing reached the coordinator".
    - 6-1, 6-5, 6-6, 6-8 and 6-9 were held about 21 h by a holder the user had stopped, until an analyst released them.
- Solves: stuck work no role sees (6-68), which 6-69 fixed for that path.
- Leaves: a party outside the tracker. 2-233 waited 36 h on work in the user's own repo.
- How it can fail: an escalation fires on slow work that is not stuck. Meets it: the trigger is the absence of a step, not time alone.

### Configuration management (6.3.5)

- Purpose: know what each change touches, and keep changes that touch the same thing in order.
- Principles: "split work that can run in parallel on disjoint files ... with no contention" (The user's preferences).
- Outcomes:
    - Changes whose Scopes overlap are ordered before the build.
    - Each worktree belongs to one live change.
- Takes from: the Scopes. Gives to: integration.
- Owner: the analyst for `depends-on`. The merge script for worktrees.
- Today: `depends-on` (`prompts/agents/notes/tickets.md`, Change tickets), and `scripts/change_worktree.py`.
- Evidence:
    - 109 of the 537 ticket review findings mention `depends-on` (`grep -ci depends-on` over `rev-findings.txt`). An example is 2-779: "leaves out open changes 2-747 ... and 2-736 ... whose renderings under `.claude/agents/` overlap this Scope". The rule itself was once wrong: "the depends-on rule asks a draft to depend on a change that waits on that draft" (4-48).
    - `git worktree list` shows 14 worktrees, 9 of them on merged branches, and `change-2-883` for a closed change. No ticket cites them as a cause of a fault.
- Solves: about a fifth of the ticket review findings, those on `depends-on`, where the order is found before the review.
- Leaves: overlaps that a Scope does not state.
- How it can fail: ordering slows changes that do not conflict. Meets it: the analyst may override an order with a reason.

## Processes not placed

- Agreement (acquisition, supply): the user is the only acquirer, and The user's part covers the relation. No evidence was looked for.
- Quality management (6.2.5), project planning (6.3.1), information management (6.3.6), system analysis (6.4.6), and infrastructure, portfolio, human resource and knowledge management: no evidence was looked for. Information management may fit the tracker and the transcripts. Knowledge management may fit `docs/wf-solver/case-rule-history.md`.
- Operation, maintenance, disposal: the user ruled that deprecated mechanisms stay ("remove none", `prompts/agents/notes/decisions.md`, The user's preferences), so disposal is not proposed.
- Business or mission analysis: the user's goals in `prompts/agents/notes/decisions.md` cover it.

## A way to implement it

At the level of steps. Nothing is done until the user takes it up.

1. The user rules on the decisions below.
2. A writer writes the root document from the ruling. Agents act on it, so it gets the full chain: requirements, verification of what each outcome makes its readers do, and validation.
3. The owner of life cycle model management maps each rule of the notes and the agent definitions to an outcome, once. A rule that maps to none is a finding. An outcome with no rule is a gap, filed as a `change`.
4. Each later change to a process names the outcome it serves.

## Decisions for the user

Each gives one line per option, the default first, with its consequence for the goals (`prompts/agents/notes/decisions.md`, The user's goals).

- Take up the frame:
    - Default: take up 12207 as the frame of a root document, as above. It gives each process one owner and outcomes to check, at the cost of one more document and a one-time mapping of the rules (goal 3).
    - Adopt 12207 completely, with a role for each process. Each agent then carries one process, at the cost of a handoff, a definition and a launch for each new role (goal 3).
    - Use a light set of named practices. Fewer lines, and gaps between practices stay unshown (goal 3).
    - Change nothing. No cost now, and practices keep landing in separate documents (goal 3).
- Owner of design definition:
    - Default: the ticket analyst writes the design into the change, from the code, and the ticket reviewer checks it and the Scope against the code. One role sees need, design and Scope together. It adds work to the analyst and the reviewer on each change that adds a mechanism (goals 2 and 3).
    - The code editor writes the design as the first step of its run, and a reviewer checks it before the code. The design is made by the role that reads the code most, at the cost of a stop in each editor's run for the review (goals 2 and 3).
- Owner and trigger of the process review:
    - Default: a ticket analyst with a process-review brief, at a set count of merged changes to the agents' processes. Its cost is bounded by the count (goal 3).
    - The coordinator, as part of its work. No new runs, and it competes with the coordinator's other work for the user (goal 3).
