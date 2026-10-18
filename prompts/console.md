# Console messages
- The messages the console sends a worker, one section per message.
* comment
    - A section's heading is the name the console asks for.

## create
* inline: #task
- You are the first session of a chained flow: you create the solver, then a separate session takes over from your report.
* inline: #every-pass-rules
* inline: #ops-head
* inline: #op-write
* inline: #op-develop
* inline: #op-determine
* inline: #op-witness
* inline: #op-simplify
* inline: #op-prune
* inline: #pass-head
* inline: #scope
* inline: #draft-mark
- When a question about the data comes up, run something that answers it rather than working it out by hand.
* inline: #handoff-end
* inline: #report-complete
* inline: #handoff-wrap

## advance
* inline: #task
* inline: #prior-reports
* inline: #advance-head
* inline: #read-first
* inline: #every-pass-rules
* inline: #ops-head
* inline: #op-develop
* inline: #op-determine
* inline: #op-witness
* inline: #op-simplify
* inline: #op-prune
* inline: #pass-rules
* if: more
    * inline: #handoff-tail
* unless: more
    * inline: #review-tail

## no-solver
* inline: #task
* inline: #prior-reports
* inline: #advance-head
- The sessions before you left no solver: programs/solvers/{{tid}}.dl does not exist.
- Take the reports above as input to the first operation.
* inline: #every-pass-rules
* inline: #ops-head
* inline: #op-write
* inline: #op-develop
* inline: #op-determine
* inline: #op-witness
* inline: #op-simplify
* inline: #op-prune
* inline: #pass-rules
* if: more
    * inline: #handoff-tail
* unless: more
    * inline: #review-tail

## finalize
* inline: #task
- You are the final session of a chained flow.
* if: reports
    * inline: #prior-reports
    * inline: #read-first
    * inline: #every-pass-rules
    * inline: #ops-head
    * inline: #op-develop
    * inline: #op-determine
    * inline: #op-witness
    * inline: #op-simplify
    * inline: #op-prune
    * inline: #pass-rules
* unless: reports
    - No earlier session left a report, so the solver file is the whole account.
    - Read programs/solvers/{{tid}}.dl first.
    * inline: #finished
    * inline: #every-pass-rules
    * inline: #ops-head
    * inline: #op-develop
    * inline: #op-determine
    * inline: #op-witness
    * inline: #op-simplify
    * inline: #op-prune
    * inline: #pass-head
    * inline: #judge
    * inline: #scope
    * inline: #draft-mark
    * inline: #review-tail

## handoff
- Write the handoff report for the session that takes over from you, holding everything the pass routes to a reader:
    * inline: #handoff-items
- Cover the whole session, including turns after any earlier report.
* inline: #report-complete
* inline: #handoff-wrap

## refused-handoff
* comment: Sent in place of `handoff` when the worker refuses that ask.

- Write the handoff report as a document for the session that takes over from you, from the files and the run output in front of you: the model hypothesis, the solver's current structure, the edits this pass made, what was run and what came back, and the open items.
* inline: #handoff-wrap

## callout
* comment: The counts behind each rate live in `prompts.py`, which passes each kind its rate and its band.

- Your pass is in.
- Now step back from the pass and write the callouts: the items the pass left open, and anything else that deserves attention.
- Decide every call from the principles and your reading of them.
- Report a call only when the reading is a stretch, naming the rule and the tighter reading.
- Rank each callout P1-P3 by kind: match the callout against a description below and take that kind's band.
- Match on the description, not the label.
- A callout outside every description ranks on your own judgment.
- The rate is how often the user engages the kind when a report raises it:
    * inline: #callout-kinds
- What a description excludes, such as a name local to this solver, is not a callout at all: leave it out.
* inline: #p0
* inline: #callouts-reply

## refused-callout
* comment: Sent in place of `callout` when the worker refuses that ask as reasoning extraction. The words ask for a record of the pass, not for what the session considered.

- Write the callouts as a document for the user: the items the pass left open, and the calls whose reading of the principles is a stretch, each naming the rule and the tighter reading.
- Rank each callout P1-P3 by kind, matched on the description:
    * inline: #callout-kinds
* inline: #p0
* inline: #callouts-reply

## nudge
- Your last turn was cut off at the output limit before it ran anything.
- Stop trying to settle the task before you run anything.
- Take the smallest thing you are still unsure about and run something that answers it.
- Partial and wrong is fine.
- If the next turn also ends without running anything, it will be your final turn.

## bail
- Two turns ended without running anything, so your pass ends here. Stop solving.
- Write a short state of play from what is already in front of you, without working anything out again:
    - how you read the task
    - what you ran, and what came back
    - where you got stuck, and what you would try next
- Keep it brief and factual.
- What the reader needs is your dead ends and your open question, not a full account.
- Put it between `<handoff>` and `</handoff>` tags.

## scratch-note
* comment: Part of the system prompt of a worker and of a survey session.

### Scratch
- Files you write to answer a question go under `.scratch/`, not the repo root.
* comment:
    - Git ignores that path.

### Git
- No git writes.

### Grids
- A color: the marks are `3` on a field of `5`. A row: `3 5 5 5 3`. A `0` cell is written `0`. A grid:
    ```
    3 5 5 5 3
    5 5 5 5 5
    3 5 5 5 3
    ```
- A grid location is cited as pair, side, places — `train0 input (11,2), (13,2); test1 output rows 2–4, cols 1–3`, or a single `row N` / `col N` — all 0-based cell coordinates.

## survey
* comment: Sent by `tools/console/solver_console/surveys.py`, which `scripts/survey.py` runs.

- Survey the lib operation the entry {{entry}} specifies, over the scope ({{scope}}).
- Write the files you need under {{scratch}}, and change no file outside that path.
- Your reply is the report.

## Partials

### every-pass-rules

#### Every pass
* inline: ../docs/handbook/procedure.md#every-pass

#### Review items
* inline: ../docs/handbook/procedure.md#review-items

### op-write

#### Write
* inline: ../docs/handbook/procedure.md#write

### op-develop

#### Develop
* inline: ../docs/handbook/procedure.md#develop

### op-determine

#### Determine
* inline: ../docs/handbook/procedure.md#determine

### op-witness

#### Witness
* inline: ../docs/handbook/procedure.md#witness

### op-simplify

#### Simplify
* inline: ../docs/handbook/procedure.md#simplify

### op-prune

#### Prune
* inline: ../docs/handbook/procedure.md#prune

### ops-head

#### Operations
- Run the operations below, through Prune, in this order.

### pass-head

#### Your pass

### judge
- Judge the model and the code yourself, and edit what falls short.

### task
- Task: {{tid}}

#### data/tasks/{{tid}}.json
* code: task
    + language: json

### prior-reports
* if: reports
    * text: reports
* unless: reports
    - The session before you left no report.

### read-first
- Read programs/solvers/{{tid}}.dl first, and edit that file.
* comment:
    - The reports describe the solver; the file is what changes.
* inline: #finished

### pass-rules
* inline: #pass-head
* inline: #judge
- Do not redo work the reports already did.
- What a report leaves unsettled is yours to settle.
* inline: #scope
* inline: #draft-mark
- A callout in a report above is an open item, not an instruction.
- Judge it yourself, from its sites, not from the report that gave it.
- Re-raise only what stays open after that.

### advance-head
- You are a later session of a chained flow: the sessions before you left the reports above.

### scope
- Your edits stay in programs/solvers/{{tid}}.dl, programs/witnesses/{{tid}}.wit.json, .scratch/{{tid}}/, and the files an operation this message gives names.
- Any other file is the user's to change, and a fix you have for one goes in your report.

### draft-mark
- The solver has `// @draft` on its own line under the task-id line, and only the user's approval takes it off.

### finished
- A solver that already holds up under your judgment needs no edit from you: say so.

### handoff-wrap
* comment: Keep this in every message that asks for a report: a resumed session may hold an older brief.

- Put the report between `<handoff>` and `</handoff>` tags: the console takes that block as your pass's result, in whichever turn it appears.

### handoff-items
* comment: Stated once here; a message adds only what its own stage owes.

- the model hypothesis as it now stands, what you changed and why, each choice point with the alternatives you considered and what ruled them out, and the open items
- Those alternatives include the ones the data rules out, which a review omits and the report gives.
* comment:
    - The next session then does not derive them again.
- A witness the report relies on and did not record goes in the report itself, as the input grid and each model's output on it.

### handoff-end
- End your turn with a handoff report for the session that takes over from you, holding everything the pass routes to a reader:
    * inline: #handoff-items

### report-complete
- Make it complete enough that the next session reruns nothing.

### handoff-tail
* comment: Sent where a stage has a successor.

* inline: #handoff-end
- The report covers your own pass: your rulings, your edits, your changes.
- What the reports above already establish stays with them.
* inline: #handoff-wrap

### review-tail

#### Review
- The review comes after the pass.
* inline: ../docs/handbook/procedure.md#review
- Your review is your reply.

### callouts-reply
- Reply with only the callouts, between `<callouts>` and `</callouts>` tags: a numbered list, each callout one or two lines opening with its rank, `[P0]` to `[P3]`.
- With nothing to raise, the block holds the single word `none`.

### callout-kinds
- Lib candidates and proposal comps: a solver-local form proposed for programs/lib.dl or docs/wf-solver/proposals/, with its entry and survey result.
    - P{{lib-candidates-band}}, engaged {{lib-candidates-rate}}% of the time.
- Doc issues: an issue with something in docs/handbook that interfered with the pass.
    - P{{doc-issues-band}}, engaged {{doc-issues-rate}}% of the time.
- Naming and vocabulary: a name with shared scope — a lib comp, a type, doc wording, a proposals entry; a name local to one solver is not this kind.
    - P{{naming-band}}, engaged {{naming-rate}}% of the time.
- Lint and tooling: an improvement or a defense of the linter, run budgets, timing, or index tooling; a broken tool is P0, not this kind.
    - P{{lint-and-tooling-band}}, engaged {{lint-and-tooling-rate}}% of the time.
- Simplification: redundancy or awkward reading in the shipped solver, such as a relation with one consumer or a line that misleads.
    - P{{simplification-band}}, engaged {{simplification-rate}}% of the time.
- Unwitnessed divergences: a divergence between models that no pair in the task exhibits, stated with the constructed witness that would separate them.
    - P{{unwitnessed-divergences-band}}, engaged {{unwitnessed-divergences-rate}}% of the time.
- Correctness risk: a defect, or an implicit assumption the solver leans on, such as a property every input happens to satisfy.
    - P{{correctness-risk-band}}, engaged {{correctness-risk-rate}}% of the time.
- Hedges: a trailing qualification on a settled call, not a discrete open item.
    - P{{hedges-band}}, engaged {{hedges-rate}}% of the time.

### p0
- P0 stands apart from that scale: use it only for a clear mechanical problem with the tooling, such as the runner, the linter, or the audit crashing, giving a wrong result, or lacking something an operation needed.
- A judgment never takes a P0.
