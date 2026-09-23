# Templating a document
- The directives that build a document out of others and fill it with values, for anyone editing the prompts.
* comment:
    - `writing.md` states the line forms these stand among.

* comment: When editing this doc, state a line form only where this document changes it.

## Include

- An `include` directive names a path, and the whole document at that path takes the place of the directive.
    - The path is relative to the file the directive sits in.
    - The included document's title heading and its sections sit one level deeper than that line.
    - It names a file and nothing inside one.
- Attributes under an `include` are its options.
    - `exclude` names the attributes to drop, throughout the included document and what it includes. A node that carries one goes with its subtree.
    - `abridged: all` renders every included document as its `index` attribute says. A list of paths, relative to the including file, abridges those documents alone.
        - A document with no `index` attribute renders in full.
    - A document included with no `abridged` renders in full.
        ```
        * include: ../handbook.md
            + exclude: draft, gloss
            + abridged: all
        ```
- A document's `index` attribute says what it abridges to, and it gives the title heading and the lines above the first section, then the lines the attribute asks for.
    - `index: headings` gives one line per heading.
    - `index: entries` gives one line per `## ` section: its text and the first sentence of its first statement.
- A heading's rendered level comes from its depth in the rendered tree, and not from the count of `#` it carries in the source.
    - A heading that is a direct child of a console message section renders at the top level.

## Inline

- An `inline` directive names a section by `#<id>`, or by `<path>#<id>` on another document, and the lines under that heading take the place of the directive.
- The heading stays behind, so a heading those lines need is written at the site, with the inline under it.
    ```
    ### Reference solver
    * inline: #reference
    ```
- A heading inside the body lands under the section the inline stands in.
- An inline stands where a statement stands, and it takes no options.
- A section written to be inlined is headed by its own slug.
    ```
    ### prior-reports
    - The reports the sessions before you left.
    ```
- The sections under a `Partials` heading are the document's partials, the runs of lines more than one site inlines.
- A section a reader reads keeps a prose heading.
* comment:
    - The heading at the site then reads as the reference to the inlined section.

## Links

- A render rewrites a target taken from the document, one that opens with `./` or `../`, to stand from the repo root.
    ```
    - [Principles](../docs/handbook/principles.md), in a doc under prompts/, renders as [Principles](docs/handbook/principles.md).
    ```
- A target already taken from the root stands as it is, and so do an external target and a slug.

## Variables

- A statement's text may hold a variable: a name between double braces, which the render replaces with the value the caller gives for that name.
    ```
    - Task: {{tid}}
    ```
- A heading and a quote take one too. A code node and a table are literal.
- A backtick span is literal, so a variable written inside one is text, as the ones in this document are.
- A value is a string, and one that holds a line break is an error. Line breaks reach a render through `code`, `quote`, and `text`.
- A double brace with no name between the braces is text.

## Conditions

- `if` keeps the lines under it when the value its name gives holds something, and drops them when it does not.
- `unless` is the reverse.
    ```
    * if: reports
        - The sessions before you left the reports above.
    * unless: reports
        - The sessions before you left no report.
    ```

## Blocks from a value

- `code` renders the value its name gives as a code node, and a `+ language` attribute on the directive gives the fence its info string.
    ```
    #### data/tasks/{{tid}}.json
    * code: task
        + language: json
    ```
- `quote` renders the value its name gives as a quote.
    ```
    * if: notes
        * quote: notes
    ```
- `text` renders the value its name gives as it stands, with no fence and no quote marker, so a value that carries its own markup reaches the reader unchanged.
    ```
    * if: reports
        * text: reports
    ```
- Each of the three stands where a statement stands, and the value it names may hold line breaks.

## The names a document reads

- The names a document reads are declared nowhere: a render reads them off the lines the document inlines and includes.
- A render given values takes the names given to equal the names read.
    - A name missing, and a name nothing reads, are both errors.
- A render given no values fills nothing, and the text stands as written.
- Both branches of an `if` count.
