* comment: when editing this doc
    - The lead of the `arclog` agent: [arclog](prompts/agents/arclog.md) includes it, and it holds no text of its own other than the line that gives the renames, the line on the table tool and the undisclosed list.
    - Parts of the reading, in order:
        - The terms: the line that gives the renames.
        - The table tool: the line on `scripts/arclog.py`.
        - The theory of tasks, models and encodings: [Principles](docs/handbook/principles.md), with each section that has the attribute `arcdata` and each statement that has the attribute `formal` left out, and [Encoding](docs/handbook/encoding.md), with each part that has the attribute `souffle` left out.
        - The language, lean: [arclog](docs/arclog/arclog.md), with each section that has the attribute `undisclosed` left out.
        - The lib: [The arclog lib](docs/arclog/lib.md), whole. It leaves out the items that [The arclog lib: rare items](docs/arclog/lib-rare.md) holds.
        - The parts read when their condition holds: [Undisclosed](#undisclosed).
    - Each section of [arclog](docs/arclog/arclog.md) that has the attribute `undisclosed` has a line under [Undisclosed](#undisclosed), and so does each document of `docs/arclog/` that the included text leaves out. The sections of [Principles](docs/handbook/principles.md) that have the attribute `arcdata` share the line of [arcdata](docs/arclog/arcdata.md).

# Arclog documents
* comment: The user's words, session e3928061-1720-4a0f-b4df-246232db80a7, 2026-11-01: "there's a @docs/paper-terms.md and @docs/lib-spec.md related docs somewhere explaining the renames". The coordinator's rule 15 of that day: "The shared handbook text keeps its terms. One line points to `docs/paper-terms.md` and the disposition table in `docs/lib-spec.md`." Without the line, a reader of Principles and Encoding, which say `model`, `Ordinal`, `Canon` and `in`, has no way to tell that the arclog documents' `hypothesis`, `Order`, `Quotient` and `input` are the same things.
- The theory below keeps the handbook's terms, and the arclog documents use the new names. [Terms for the paper](docs/paper-terms.md) gives the renames of the terms, and the table "Disposition of the present lib" in [Lib specification](docs/lib-spec.md) gives those of the lib.

* comment: The user's words, session e3928061-1720-4a0f-b4df-246232db80a7, 2026-11-01: "we should make it easy to inspect tables".
- `uv run python scripts/arclog.py` runs an arclog program on a task and gives the columns and row counts of its tables, or the rows of one relation as JSON or drawn on grids. Its `--help` gives its use.

* include: ../docs/handbook/principles.md
    + exclude: arcdata, formal

* include: ../docs/handbook/encoding.md
    + exclude: souffle

* include: ../docs/arclog/arclog.md
    + exclude: undisclosed

* include: ../docs/arclog/lib.md

## Undisclosed
* comment: The user's words, session e3928061-1720-4a0f-b4df-246232db80a7, 2026-11-01T16:00:10Z: "outline noting what is undisclosed", answered by the coordinator's outline of 16:00:20Z, which the user confirmed at 16:01:48Z with "ok".
- The documents and sections below are not in your context. Read one when its condition holds.
    - The file holds, or the edit adds, `ONE` or `CHOOSE`: [Constraints](docs/arclog/constraints.md).
    - The file holds, or the edit adds, a `RIGID_DET`: [Rigid](docs/arclog/rigid.md).
    - The file holds, or the edit adds, a `DEMONSTRATED`: [Demonstrated](docs/arclog/arclog.md#demonstrated), then `DemonstrationConsistency` in [The arclog lib: rare items](docs/arclog/lib-rare.md).
    - The file holds, or the edit adds, a `DET` or a `DET_OR_RULE` line that ends in `(ONE)` or `(SET)`: [Open values](docs/arclog/arclog.md#open-values).
    - The file holds, or the edit adds, an instance of a component with a type parameter `under` a type, or with an instance that leaves a type parameter other than `Key` unbound: [Type parameters](docs/arclog/arclog.md#type-parameters).
    - The file holds, or the edit adds, an `Unfold` instance: [Unfold](docs/arclog/arclog.md#unfold).
    - The file holds, or the edit adds, a lib name that has no entry in [The arclog lib](docs/arclog/lib.md): [The arclog lib: rare items](docs/arclog/lib-rare.md).
    - The brief asks to lower bits: [Bits](docs/arclog/bits.md).
    - The brief asks to read or change arcdata files: in [Principles](docs/handbook/principles.md), [The generator](docs/handbook/principles.md#the-generator), [Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters), [Witnesses](docs/handbook/principles.md#witnesses), [Equivalence and subsumption](docs/handbook/principles.md#equivalence-and-subsumption), [Open parameters](docs/handbook/principles.md#open-parameters) and [Cases](docs/handbook/principles.md#cases), then [arcdata](docs/arclog/arcdata.md).
