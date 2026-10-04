# Code notes
- The statements on editing and reviewing the code that more than one entry point inlines.

## code-working-rules
- Run every command in the foreground, with an explicit timeout of at most 600000 ms on the Bash call.
- When a run does not finish inside one call, split it into parts that each finish inside one call, or record it as over its limit, and do not run it again.
- Read nothing under `../arc-synth-bun/`.
- Launch no agents.
- Keep `progress.md` in your scratch directory, with your start time, what is done and what is next. After your context is compacted, read it before anything else.
- When your time since the start passes one and a half times your estimate, write what is done and what is left in `progress.md`, and end your turn with a message to main that says the estimate is passed.

## place-kinds
- Defects:
    - One idea in two places: a computation, selection, rule, rendering or sentence written twice, in one module or across modules.
    - Solver text read or written outside the `souffle` package.
    - A lookup that defaults where the value could be unknown, or a closed vocabulary held as `str`.
    - An iteration whose order reaches output, run in hash order.
    - A value that crosses a package boundary as a string the other side parses.
    - A test that [Tests](CLAUDE.md#tests) does not keep.
    - Prose in code that breaks a rule of [Prose in code](src/controlled_markdown/writing.md#prose-in-code).
    - A name the diff gives a thing, where practitioners of the thing's discipline use a conventional name for it that the diff does not use.
- A defect place stands, with its reason, where a package boundary forces the second copy, where a rule requires it, or where an absent value has a known meaning.
    - Each check quotes for itself the handbook passage it rests on, so one passage quoted at several checks stands.
        * comment: Of scan 7's 30 items, 9 stood with reasons, among them one style.md sentence quoted at four checks, which the quote rule requires.
- Places that pose a question:
    - A condition on one solver, one command or one shape of input.

## place-issues
- Cite a place's target as every location of the place. For one idea in two places, the locations include those outside the diff.
- Write under `Effect` what the code does there, and quote that code under `Evidence`.
- In the title of an `undecided` issue, write the question it poses after the target, in place of what is wrong in it.
