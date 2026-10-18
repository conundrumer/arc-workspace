+ budget: 4421
* comment: when editing this doc
    - [Code editor](prompts/agents/code-editor.md), [Code reviewer](prompts/agents/code-reviewer.md), [Lib reviewer](prompts/agents/lib-reviewer.md) and [Design reviewer](prompts/agents/design-reviewer.md) inline its sections, for editing the code under `src/` and `scripts/`, reviewing it, and judging a change's design.
    - Acts, each with its section:
        - The rules every run of the code editor keeps: [code-working-rules](#code-working-rules).
        - The rules every run of each of those agents keeps: [reads-and-progress](#reads-and-progress), which code-working-rules inlines, and which the code reviewer, the lib reviewer and the design reviewer inline in place of code-working-rules.
        - Judging a whole unit: [unit-kinds](#unit-kinds), which the code reviewer and the lib reviewer load by a link as they find places.
        - Judging a line: [line-kinds](#line-kinds), which the code reviewer and the lib reviewer load by a link as they find places.
        - Reading the trees of a review: [review-trees](#review-trees), inlined by the code reviewer and the lib reviewer. The items of their checklists link place-judgment, review-tickets and place-tickets.
        - Judging a review's places: [place-judgment](#place-judgment).
        - Filing a review's tickets on places: [review-tickets](#review-tickets).
        - Filing a ticket on a place: [place-tickets](#place-tickets), which review-tickets inlines.
        - Giving a review's final reply: [review-reply](#review-reply), which the code reviewer and the lib reviewer load by the link of their reply files.

# Code notes
- The statements on editing and reviewing the code that more than one entry point inlines.

## code-working-rules
* inline: #reads-and-progress
- Launch no agent other than the ones your documents give.

## reads-and-progress
- Read nothing under `../arc-synth-bun/`.
- Keep `progress.md` in your scratch directory, with what is done and what is next.

## unit-kinds
- Defects of a whole unit:
    * comment: The user's words, session 7fd429fb, 2026-10-15T22:44:57Z: "Let’s try it. Principles are short and well known in training set"; 2026-10-16T02:19:36Z: "almost seems liek a regression".
    - One idea in two places: a computation, selection, rule, rendering or sentence written twice for the same purpose, in one module or across modules, a break of DRY.
        * comment: Code editor a3fa90721fd524e00 keyed the kept reads, which need another file set, by `run_store`'s `SOURCES`, as the fix of this kind (ticket 6-1148). The user, session 7fd429fb, 2026-10-15T22:46:49Z: "Reusing code in an inappropriate way, I forgot the term , was it high coupling?".
        - A place of this kind stands where a package boundary forces the second copy.
    - Many ideas in one place: a module whose docstring has to describe more than one subject, a break of the single-responsibility principle.
    - A unit grown by accretion: a function, a record or a class that has taken a branch, a flag, a field or a parameter for each case it was extended to cover, where a restructure into units of one subject each, or one general rule over those cases, would hold them, a break of the open-closed principle.

## line-kinds
- Defects of a line:
    - Solver text read or written outside the `souffle` package.
    - A lookup that defaults where the value could be unknown, or a closed vocabulary held as `str`.
        - A lookup that defaults stands where the absent value has a known meaning.
    - An iteration whose order reaches output and is an order of encodings, such as hash order or the order of interning, and no order of the content.
    - A value that crosses a package boundary as a string the other side parses.
    - A test that [Tests](prompts/agents/notes/tests.md#tests) does not keep.
    - Prose in code that breaks a rule on prose in code.
    - A name the diff gives a thing, where practitioners of the thing's discipline use a conventional name for it that the diff does not use.
- A defect place of any kind stands where a rule requires it.
    - Each check quotes for itself the handbook passage it rests on, so one passage quoted at several checks stands.
        * comment: Of code review 7's 30 items, 9 stood with reasons, among them one style.md sentence quoted at four checks, which the quote rule requires.
- Places that pose a question:
    - A condition on one solver, one command or one shape of input.
    - A change in the diff that makes false the premise of any line but its own lines, in a document or in prose in code.

## review-trees
- Read the earlier baseline and this review's commit through `git worktree add` on the baseline's tag and on that commit, in your scratch directory, and remove each such worktree with `git worktree remove`.
- Run no other git command that changes state.

## place-judgment
- Judge each defect place on whether it is a defect, and, where it is one, on whether it stands, by the lines on its kind.

## review-tickets
- Leave out a place that an earlier `refactor` or `question` ticket cites, where that ticket is not closed `fixed`. `uv run python scripts/file_ticket.py citing`, called once with the paths of all your places, lists the tickets that cite each.
- File each defect as a ticket of kind `refactor`, and each place that poses a question as a ticket of kind `question`, with `commit` as `<domain>`, and as `<subject>` the hash `git rev-parse --short <commit>` prints, with this review's commit as `<commit>`.
    - Cite each place as below.
        * inline: #place-tickets
- Close with `wontfix` the ticket of each defect place that stands, and give the judgment in the note after it.

## review-reply
- Your final reply goes to the agent that launched you, in at most six lines: the pattern that matches the names of the tickets you left under `tickets/open/`, and the count of tickets under each kind of place.

## place-tickets
- Cite a place's target as every location of the place.
- Write under `Impact` what the code does there, and quote each location under `Evidence`.
- In the title of a `question` ticket, write the question it poses after the target, in place of what is wrong in it.
