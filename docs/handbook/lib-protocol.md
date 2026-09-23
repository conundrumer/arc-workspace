+ index: headings
* comment: when editing this doc
    - Write in the imperative mood.

# Lib addition protocol
- Qualify a new operation for the lib, `programs/lib.dl` and the modules under `programs/lib/`, by real use in the solvers and by generality.
- **Trigger.**
    - When an encoding in the solver needs a form banned in the program, or when a grep for its shape over `programs/solvers/` finds it in four or more other solvers, apply this protocol to that encoding.
    - The grep counts every file under `programs/solvers/`, drafts included.
    - A repeated form that needs no banned form, and that the grep finds in fewer than four other solvers, goes in the review as a lib operation to promote, naming the sites, and gets no entry.
- **Generality.** Treat a proposed operation as general when it states a concept-level relation over a caller-supplied domain and builds in no arrangement beyond the frame.
    - The operation should be as abstract as possible.
    - It involves geometric types only where there is no way to abstract the geometry away.
    - It never involves the Color type.
- **Construction.**
    - Judge whether the operation is a construction.
    - A construction's `.comp` line ends with `// @construction`.

## The entry
- Give a proposed lib operation an entry under [proposals](docs/wf-solver/proposals), `<name>.md` named for that operation.
- `head -n 3 docs/wf-solver/proposals/*.md` lists every entry's title and first sentence.
- **The entry's fields.** An entry contains:
    - a `# <name> — <operation>` title
    - a first sentence that stands alone
    - the code form, when it has one
    - a `Not:` line naming what is not that operation
    - a `Match:` line with a search signature that covers every statement of the operation, including statements whose atoms are in different lines or clauses, and statements where a solver accesses one lib call only through another
        - state the shape in prose and match it with the parser ([test_ast_match.py](tests/test_ast_match.py))
        - restate a `Match:` line that does not meet this spec
            - a signature that names an identifier the lib no longer declares, or a header field that [Header](docs/handbook/solver-file.md#header) no longer has, does not meet this spec, and its restatement uses the current name
    - a `Survey:` line per survey, its time to the minute, each followed by its own result
        - the line names the scope the survey covered, in one of two forms: `Survey: <date time> — every solver.` or `Survey: <date time> — the solvers since <the entry's previous survey time>.`
        - a survey's scope includes drafts
        - the survey result that is relevant to the operation: the near-misses (sites that resemble the operation without stating it), the spec question, and a `Callers` list of the solvers that would call it
            - a citation is the stem and the relation name
        - a survey result is under a `Survey:` line, and the survey command writes the line and that result together
        - text with no `Survey:` line above it counts as no result
        - a survey result stays as written, except for a strike: strike a solver from its `Callers` list when that solver no longer writes the operation, and strike a statement that the entry's current code form, `Not:` line, or `Match:` line contradicts
        - a survey result's spec question is the user's to apply
        - a pass that finds a further site for one names that site in the review
    - a `Closed: <date time>` line with the judgment, when the operation is closed
- Put in the entry what a reader needs to judge the operation, and nothing else.

### Removing the entry
- Remove the entry's file at these times:
    - after its callers are migrated
    - at promotion, when the entry lists no callers

## The sequence
1. Write plain program relations that state the lib operation.
    - When cases share those relations, key them.
    - **Proposal comp.** If the linter would flag those relations, place them in a proposal comp: a `.comp` named for the operation.
    - **Extension of a lib comp.** Write no comp for an extension of a lib comp. Keep its local clause beside the instance.
    - Run the solver and confirm that the operation works in context.
2. Report the operation: name it, describe it, and show the solver-local version.
    - Then read the entries to find one with the same operation.
    - **Match by operation.** Match by what an operation does, not by its name.
    - When an entry exists, use that entry's name for the comp.
    - Read a solver's proposal comp with its entry.
    - The entry's state decides what to do next.
    - If no entry exists, write one.
        - It has no survey result.
    - If an entry is closed and its judgment rests on a survey result, keep that judgment.
        - Encode the solver without the operation, in the way the entry states.
        - For a closed entry with no survey result, and a closing judgment that requires evidence from the solvers, strike its `Closed:` line and survey the entry.
        - For a closed entry with no survey result, and a judgment that can be made without evidence from the solvers, leave the entry closed.
    - If an entry has a survey result, a survey lists this solver.
    - Run the survey again when the pass uses that result for a judgment, including a close.
    - Name an unlisted caller in the review, and the next survey lists it.
    - Count a family (`// @representative:` siblings with their representative) as one caller.
    - **The survey.** `uv run python scripts/survey.py <entry>` surveys an entry and writes the survey result into it.
    - Run it when the pass needs an entry's survey result and the entry has none, or some solvers are newer than its newest `Survey:` time.
    - The state sets the scope:
        - the entry has no result: the scope is every solver
        - some solvers are newer than the entry's newest `Survey:` time: the scope is those solvers, as `uv run python scripts/run_dl.py since <time>` lists them for that time
        - the scope's size is no reason to skip the survey
    - If the command fails, spawn the `survey` role with the entry's path, the scope the command would take, and a scratch path (`.scratch/surveys/<entry name>/`).
        - Append at the end of the entry a blank line, the `Survey:` line in the form the entry's fields give, a blank line, then the role's report.
        - say in the review that the command failed and the role ran
    - If the pass ends with the entry still unsurveyed, say so in the review.
3. Decide whether to close the proposal.
    - **Close grounds.** Base that judgment on whether the operation does not follow principles, or whether it is not general and the solvers encode their tasks without it.
        - The solvers encode their tasks without it when:
        - the lib already provides the operation
        - a plain relation states it and no other solver writes it
        - a relational form replaces the arithmetic
    - **Closing.** When closing a proposal, put the judgment in the entry as the `Closed:` line, remove the proposal comp, and rethink the solver's encoding in relational form.
        - Leave plain relations as written.
        - Write no `Closed:` line before a survey result is in the entry.
        - Include the close in the review as a judgment.
    - **No close.** If the proposal does not close, nothing is decided.
        - Write no text that implies an outcome.
    - **Necessity.** Measure need against the task, not against a case.
        - A comp that serves one case while another case encodes the task without it is not needed.
    - **Not a caller.** Do not count a near-miss as a caller.
        - A lib call that states the proposed operation only over that call's domain is also not a caller.
4. Leave promotion to the user, at the time they choose.
    - The `Callers` list is their evidence.
    - Nothing in the sequence reads its count.
    - [Promote](docs/handbook/procedure.md#promote) states what a pass does at that time.
- **Reimplementations.** A reimplementation states an operation the lib already provides without calling it.
    - An entry lists the reimplementations its surveys found.
- A site is no reimplementation when the lib call would need a value the program bans and no parameter supplies that value.
    - Record it under the entry that states the missing operation, and do not fix it.
- Fix one where it is in a file the pass has open, and strike it from the entry.
- Fix that file even when it has uncommitted edits.
- Leave the rest to the session that opens their files, or to promotion.

## Changes to existing definitions
- Use the same protocol for changes to existing definitions, such as an edit to a relation or component already in the lib.
- Start such a change at item 2 of [The sequence](docs/handbook/lib-protocol.md#the-sequence), with the change as what the survey covers.
- The change has no comp form. Write the whole spec in the entry's fields.
- Count as its callers the places the change would benefit.
