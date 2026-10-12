# Code notes
- The statements on editing and reviewing the code that more than one entry point inlines.

## code-working-rules
- Read nothing under `../arc-synth-bun/`.
- Launch no agent other than the ones your documents give.
- Keep `progress.md` in your scratch directory, with what is done and what is next. After your context is compacted, read it before anything else.

## place-kinds
- Defects:
    - One idea in two places: a computation, selection, rule, rendering or sentence written twice, in one module or across modules.
        - A place of this kind stands where a package boundary forces the second copy.
    - Many ideas in one place: a module whose docstring has to describe more than one subject.
    - Solver text read or written outside the `souffle` package.
    - A lookup that defaults where the value could be unknown, or a closed vocabulary held as `str`.
        - A lookup that defaults stands where the absent value has a known meaning.
    - An iteration whose order reaches output, run in hash order.
    - A value that crosses a package boundary as a string the other side parses.
    - A test that [Tests](CLAUDE.md#tests) does not keep.
    - Prose in code that breaks a rule on prose in code.
    - A name the diff gives a thing, where practitioners of the thing's discipline use a conventional name for it that the diff does not use.
- A defect place of any kind stands where a rule requires it.
    - Each check quotes for itself the handbook passage it rests on, so one passage quoted at several checks stands.
        * comment: Of code review 7's 30 items, 9 stood with reasons, among them one style.md sentence quoted at four checks, which the quote rule requires.
- Places that pose a question:
    - A condition on one solver, one command or one shape of input.
    - A change in the diff that makes false the premise of any line but its own lines, in a document or in prose in code.

## place-tickets
- Cite a place's target as every location of the place.
- Write under `Impact` what the code does there, and quote each location under `Evidence`.
- In the title of a `question` ticket, write the question it poses after the target, in place of what is wrong in it.
