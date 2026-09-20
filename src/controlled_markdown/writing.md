# Writing a document
- The lines and the markers, for anyone editing a document.
- `README.md` says what the format is and what the other documents hold.

* comment: when editing this doc
    - Put each marker to use before its rule, so a reader of the source sees the marker at work.
    - Keep the sections in the order a writer meets them: the statement, the indent, then `+`, `*`, `>`, a fence, `|`, `#`.

## Statements

- A line that starts with `- ` is a statement.
- A statement is one line, with no wrapping.
- A statement never starts with a character that Markdown reads as structure.
    - Those are `-`, `+`, `*`, `>`, `|`, and `#` when a space follows them, a number followed by `.` or `)`, `---`, `===`, `[ ]`, a code fence, and an HTML tag.
    - A backslash before the character escapes it, as in `\>` and `\---`.
    - A statement that begins with a bold phrase needs no escape, since `**` has no space after the first `*`.
- A numbered statement is written with its number, a period, and a space.
    1. The numbers under one parent run from 1 with no gap.
    2. The rendered document shows them as an ordered list.
    3. The source shows the numbers, so a reader of either view cites an item by number.
- An empty `-` line is a statement with no text, and it groups the lines under it.

## Links

- A reference to another document is a Markdown link, `[text](path)`, the path taken from the repo root, since that is where a session runs.
    ```
    - [Principles](docs/handbook/principles.md) states what a case is.
    ```
- A `#` and a slug after the path name a section of that document, and the link text is that heading's text.
    ```
    - [Models and tasks](docs/handbook/principles.md#models-and-tasks) defines a case.
    ```
- The check resolves every link: it reports a path that names nothing, a slug no heading carries, and text that is not the heading's.
- A path that opens with `./` or `../` is taken from the document that holds it instead.
- A target with a scheme, such as `https:`, is an external address, and the check passes it over.
- A link written inside a backtick span is text.
- A code file the check's config lists is read for its links alone, each at the file's own line, and nothing else in it is read as a document.

## Nesting

- Indent by four spaces per level, with spaces only, and one space follows a marker.
- A line indented one level under another is a child of it, and it says something about its parent.
- Blank lines are free between lines.

## Attributes

- A `+ ` line nested under a statement is an attribute of that statement.
- An attribute describes the line it hangs under: what the line is, or what a program does with it.
    - An attribute heads nothing. Nothing indents under a `+ ` line.
    - A name appears once under one line, and the `+ ` lines under one parent come before every other line under it.
- The rendered document shows no attributes. An attribute is a note for the editor, and a render may act on it.
- An attribute is a name, or a name and a value after a colon and a space. A name may hold spaces.
    - An attribute with no value says what the line is.
        ```
        - The claim the line makes.
            + unverified
        ```
    - An attribute with a value names what the value is.
        ```
        * code: task
            + language: json
        ```
- A name is open: any name is allowed, and a program reads the ones it knows.

## Directives

- A line that starts with `* ` is a directive: an instruction on the lines under it, with no statement of its own.
- Where a `+ ` line hangs under a statement, a `* ` line stands above the lines it governs.
- The rendered document shows a directive's lines in its own place, with no line of its own.
- A `+ ` line under a `* ` line is another attribute of the same directive, which is how a directive takes an option.
- `comment` is the directive every editor uses: it heads a note for the editor, and no render shows the lines under it.
    - A note of one line is the value.
        ```
        * comment: Sent in place of `handoff.md` when the worker refuses that ask.
        ```
    - A note of several lines goes under a bare `comment`, or under one whose value says when the lines apply, as the note at the top of this document does.
- The rest of the directives compose a document and fill it with values, and `templating.md` states them.

## Quotes

- A line that starts with `> ` is a quoted line, and consecutive quoted lines at one indent are one quote.
- Quoted lines hold prose taken from elsewhere. A blank line ends a quote.
- A quote sits under a statement or under a heading, and nothing goes under it.
- A reader of the source sees the quote's body as Markdown, so code goes in a code node instead.

## Code

- A line that opens with a fence, three or more backticks or tildes, opens a code node, and the lines up to the closing fence are its content.
- A code node holds what is read verbatim: code, a header, or an example of a document.
    ~~~
    - The header of a solver:
        ```
        // <task_id>
        // @draft
        ```
    ~~~
- An example that holds a fence takes a longer fence, or a tilde fence, so the inner fence does not close it.
- A code node sits under a statement or under a heading, and nothing goes under it.
- One line carries one block at most, a block being a code node, a quote, or a table. A second example goes under a statement of its own, as the ones in this document do.

## Tables

- A line that starts with `| ` is a table line, and consecutive table lines at one indent are one table.
- A table goes on its own lines under its parent, with no `>` and no fence, and nothing goes under it.
    ~~~
    ## Terms
    | Former | Current |
    | --- | --- |
    | Shift | Offset |
    ~~~
- A table holds records of one shape whose every cell is one value the reader takes in while scanning the column: a name, a number, a short phrase, or a short sentence where that is the value.
    - A cell that wants a second clause, a list, or a qualification belongs to a record that wants a list of lists.
- A list of lists holds a record with a field of prose. The record's name or its definition is the statement, and its other fields are the statements under it.
    - A field may be a sentence, and it may nest further.
    ```
    - Offset: the distance a shape moves between the input and the output.
        - Written as a pair of signed integers.
    ```
- One statement holds a record that is one sentence carrying one datum at most. A second datum means the record wants a list of lists.

## Headings

- A line that starts with `# ` is a heading, and a heading is a statement.
- A heading stands at column zero, and so do the lines under it.
    - The lines under a heading run to the next heading of the same depth or a shallower one.
    - Indentation starts from zero again under every heading, so a document never indents far.
- The count of `#` follows the tree: the document's heading is `#`, its sections are `##`, and theirs are `###`.
- A `+ ` line on the line after a heading is an attribute of that heading.
- A heading carries the slug of its text as its id: lower case, each run of spaces as one hyphen, and the punctuation other than a hyphen dropped.
    - A heading is the only line that carries an id, and two sections of one document whose slugs meet is an error, settled by renaming a heading.
- The lines above the first heading belong to the document.
    - A `+ ` line there is an attribute of the document, and it describes the document rather than any line in it.

## Front matter

- A document may open with a front matter block, `---`, the lines under it, and a closing `---`.
    - The block stays as it is written, and the rendered document leaves it out.
    - Structured data goes in that block, where a program reads it.
