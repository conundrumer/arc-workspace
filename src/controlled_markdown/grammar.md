# The grammar
- The exact rules and the edge cases the other documents leave out, for anyone maintaining the package.
- `writing.md` and `templating.md` state what a writer needs; this states what a parser settles.

* comment: When editing this doc, state a rule once, and only where neither of the other two documents states it.

## Indentation

- Indentation is four spaces per level, spaces only.
- A tab in the indentation is an error, and so is a width that is not a multiple of four.
- A jump of more than one level is an error.

## What the parser settles

- A directive builds the same tree as an empty `-` line with the attribute under it, so the two are one shape to the parser and two conventions to a writer.
- The parser enforces no convention. What an attribute means, and which names a document uses, is how the documents are written.

## Attributes

- A name followed by a colon and nothing else has an empty value, which is not the same as no value.
- `heading` is reserved, and an explicit `+ heading` is an error.
- A `* ` line with no name is an error.

## Blocks

- A quote, a code node, and a table each need a line above them, so one at document level, above the first heading, is an error.
- A quoted line indented deeper than the quote's first line is an error.
- The closing fence is the same character as the opening one, at least as long, at the node's indent, and it carries no info string.
- A code node with no closing fence is an error, and so is a line under it at a shallower indent.

## Headings

- More than six `#` is an error, and so is a trailing `#` closer.
- A setext underline, `===` or `---` under a line, is not a heading.
- A heading with no text is allowed, and it groups the lines under it.
- A heading may stand directly under a directive, at the directive's child indent.
    - Its depth counts its heading ancestors alone, so the directive adds none.
    - The lines under it start from the directive's own level.
        ```
        * if: reference
            ### Reference solver
            - The solver the session reads.
        ```

## Reuse

- An `include` value with a `#` in it is an error, since a section is reached with `inline`.
- A document that reaches itself, by either directive, is an error.

## Front matter

- A front matter block with no closing `---` is an error.

## Canonical form

- `fmt` writes canonical form: heading depth from the tree, four-space indent, the writer's blank lines, the escapes the block-syntax rule needs, and a late attribute moved up. Everything else stands as written.
- Round trip holds: parsing what the formatter writes gives the tree it was written from.

## Rules and cases

- Each rule the check reports has a short name, which the check prints beside its message.
- A case under `tests/controlled_markdown_cases/` pins each rule, holding the document and the name it expects.
