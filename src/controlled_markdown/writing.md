# Writing a document
- The lines of a document and the markers that open them.
- [Controlled Markdown](src/controlled_markdown/README.md) says what the format is and what the other documents hold.

* comment: when editing this doc
    - Use each marker before the rule that states it, so a reader of the source sees the marker in use.
    - Keep the sections in the order a writer meets them: the statement, the indent, then `+`, `*`, `>`, a fence, `|`, `#`.

## Statements

- A line that starts with `- ` is a statement.
- A statement is one line, with no wrapping.
- A statement never starts with a character that Markdown reads as structure.
    - Those are `-`, `+`, `*`, `>`, `|`, and `#` when a space follows them, a number followed by `.` or `)`, `---`, `===`, `[ ]`, a code fence, and an HTML tag.
    - A backslash before the character escapes it, as in `\>` and `\---`.
    - A statement that begins with a bold phrase needs no escape.
- A numbered statement is written with its number, a period, and a space.
    1. The numbers under one parent run from 1 with no gap.
    2. The rendered document shows them as an ordered list.
    3. The source shows the numbers.
    * comment:
        - A reader of either view then cites an item by number.
- An empty `-` line is a statement with no text, and it groups the lines under it.

## Links

- A reference to another document is a Markdown link, `[text](path)`, the path taken from the repo root.
    ```
    - [Principles](docs/handbook/principles.md) states what a case is.
    ```
- A `#` and a slug after the path point to a section of that document, and the link text is that heading's text.
    ```
    - [Models and tasks](docs/handbook/principles.md#models-and-tasks) defines a case.
    ```
- A link with no path points to a heading of the same document, as `[text](#slug)`.
- The check resolves every link: it reports a path that does not exist, a slug no heading has, and text that is not the heading's.
- A path that opens with `./` or `../` is taken relative to the document that contains it.
- A target with a scheme, such as `https:`, is an external address, and the check passes it over.
- A link written inside a backtick span is text.

## Prose in code

- A string a program puts in an agent's context is wrapped in `mctx`, and the check reads it there.
    - In Python, `mctx` takes a string, or a dict whose every value is one. A call whose string the check cannot read without running the program is an error.
    - In JavaScript, `mctx` tags a template literal. A backtick inside one opens a nested literal, which the check does not read.
- A fragment is the string inside an `mctx` call.
- A fragment that opens with a marker is read as lines of a document, and every rule applies to it. Any other fragment is read as the text of one statement, and the rules on a statement's text apply to it.
    - A block may stand at a fragment's top level, and the text that places the fragment supplies the line above.
- A hole is `{name}` in Python and `${name}` in JavaScript, and the check reads one opaque word in its place.
    - A hole that is a whole line places a fragment of its own, which the check reads where that fragment stands.
    - A `${…}` that is not a name is an error: the value it takes is computed above the literal and given a name.
- A fence inside a JavaScript fragment is written with tildes.
- A string that names a document by path names one the tree holds, and the check reports one it does not. A path holding a hole or a wildcard names a shape and is passed over.
- A `///` or `//!` comment in a Souffle file is the text of one statement, and it takes the rules on a statement's text.

## Nesting

- Indent by four spaces per level, with spaces only, and one space follows a marker.
- A line indented one level under another is a child of it, and it says something about its parent.
- A blank line may stand between any two lines.

## Attributes

- A `+ ` line nested under a statement is an attribute of that statement.
- An attribute describes the line it is nested under: what the line is, or what a program does with it.
    - No line is nested under a `+ ` line.
    - A name appears once under one line, and the `+ ` lines under one parent come before every other line under it.
- The rendered document shows no attributes. An attribute is a note for the editor, and a render may act on it.
- An attribute is a name, or a name and a value after a colon and a space. A name may hold spaces.
    - An attribute with no value says what the line is.
        ```
        - The claim the line makes.
            + unverified
        ```
    - In an attribute with a value, the name says what the value is.
        ```
        * code: task
            + language: json
        ```
- Any name is allowed, and a program reads the names it knows.

## Directives

- A line that starts with `* ` is a directive: an instruction on the lines under it, with no statement of its own.
- The rendered document shows the lines under a directive where the directive stands, and no line for the directive itself.
- A `+ ` line under a `* ` line is another attribute of the same directive, which is how a directive takes an option.
- `comment` is the directive every editor uses: it heads a note for the editor, and no render shows the lines under it.
    - A note of one line is the value.
        ```
        * comment: Sent in place of `handoff` when the worker refuses that ask.
        ```
    - A note of several lines goes under a bare `comment`, or under one whose value says when the lines apply.
- The rest of the directives compose a document and fill it with values, and [Templating a document](src/controlled_markdown/templating.md) states them.

## Quotes

- A line that starts with `> ` is a quoted line, and consecutive quoted lines at one indent are one quote.
- Quoted lines hold prose taken from elsewhere. A blank line ends a quote.
- A quote sits under a statement or under a heading, and nothing goes under it.
- Code inside a quote goes in a code node instead.

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
- One line has one block at most, a block being a code node, a quote, or a table. A second example goes under a statement of its own, as the ones in this document do.

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
    - A record with a cell that needs a second clause, a list, or a qualification goes in a list of lists.
- A list of lists holds a record with a field of prose. The record's name or its definition is the statement, and its other fields are the statements under it.
    - A field may be a sentence, and it may nest further.
    ```
    - Offset: the distance a shape moves between the input and the output.
        - Written as a pair of signed integers.
    ```
- A record that is one sentence with one datum at most goes in one statement. A record with a second datum goes in a list of lists.

## Headings

- A line that starts with `# ` is a heading, and a heading is a statement.
- A heading stands at column zero, and so do the lines under it.
    - The lines under a heading run to the next heading of the same depth or a shallower one.
- The count of `#` follows the tree: the document's heading is `#`, its sections are `##`, and theirs are `###`.
- A `+ ` line on the line after a heading is an attribute of that heading.
- A heading's id is the slug of its text: lower case, each run of spaces as one hyphen, and every character other than a letter, a digit, an underscore, a space or a hyphen dropped.
    - Only a heading has an id. Two headings of one document with the same slug are an error, and renaming one of them settles it.
- The lines above the first heading are the document's lead, and they belong to the document.
    - A `+ ` line there is an attribute of the document as a whole.

## Front matter

- A document may open with a front matter block, `---`, the lines under it, and a closing `---`.
    - The block stays as it is written, and the rendered document leaves it out.
    - Structured data goes in that block, where a program reads it.
