# Code notes
- The statements on editing and reviewing the code that more than one entry point inlines.

## code-working-rules
- Read nothing under `../arc-synth-bun/`.
- Launch no agent other than the ones your documents give.
- Keep `progress.md` in your scratch directory, with what is done and what is next. After your context is compacted, read it before anything else.
- Your budget is the N of the latest `Budget: N minutes` line in your brief or a later message from your parent.
- Start your budget timer with your first command, and again at each later message from your parent, after you end the timer that runs: run this command in the background, with N times 60 as `<seconds>`:
    ```
    : 'unattended-wait: budget timer'; sleep <seconds> & echo $! > <scratch directory>/timer.pid; wait
    ```
- When the notification that the timer completed reaches you, where you did not end it, finish the step you are on, write what is done and what is left in `progress.md`, and end your turn with a reply that says the budget is passed.
- When the first message from a subagent other than your parent reaches you, and before your final reply, end the timer that runs: run `kill $(cat <scratch directory>/timer.pid)`, and give that reply only once `kill -0 $(cat <scratch directory>/timer.pid)` fails.

## place-kinds
- Defects:
    - One idea in two places: a computation, selection, rule, rendering or sentence written twice, in one module or across modules.
    - Many ideas in one place: a module whose docstring has to describe more than one subject.
    - Solver text read or written outside the `souffle` package.
    - A lookup that defaults where the value could be unknown, or a closed vocabulary held as `str`.
    - An iteration whose order reaches output, run in hash order.
    - A value that crosses a package boundary as a string the other side parses.
    - A test that [Tests](CLAUDE.md#tests) does not keep.
    - Prose in code that breaks a rule of [Prose in code](src/controlled_markdown/writing.md#prose-in-code).
    - A name the diff gives a thing, where practitioners of the thing's discipline use a conventional name for it that the diff does not use.
- A defect place stands, with its reason, where a package boundary forces the second copy, where a rule requires it, or where an absent value has a known meaning.
    - Each check quotes for itself the handbook passage it rests on, so one passage quoted at several checks stands.
        * comment: Of code review 7's 30 items, 9 stood with reasons, among them one style.md sentence quoted at four checks, which the quote rule requires.
- Places that pose a question:
    - A condition on one solver, one command or one shape of input.
    - A change in the diff that makes false the premise of any line but its own lines, in a document or in prose in code.

## place-tickets
- Cite a place's target as every location of the place. For one idea in two places, the locations include those outside the diff.
- Write under `Impact` what the code does there, and quote each location under `Evidence`.
    - For many ideas in one place, write `many ideas in one place` as what is wrong in the module, write under `Impact` each subject it splits into, with the section banners or the classes that hold it, and quote under `Evidence` the module's line count as `wc -l` prints it.
- In the title of a `question` ticket, write the question it poses after the target, in place of what is wrong in it.
