# The grammar
- The exact rules and the edge cases the other documents leave out, for anyone maintaining the package.

* comment: When editing this doc, state a rule once, and only where neither of the other two documents states it.

## Indentation

- Indentation is four spaces per level, spaces only.
    + xref: src/controlled_markdown/nodes.py:INDENT, src/controlled_markdown/parser.py:parse
- A tab in the indentation is an error, and so is a width that is not a multiple of four.
    + xref: src/controlled_markdown/parser.py:parse
- A jump of more than one level is an error.
    + xref: src/controlled_markdown/parser.py:parse

## What the parser settles

- A directive builds the same tree as an empty `-` line with the attribute under it, so the two are one shape to the parser and two conventions to a writer.
    + xref: src/controlled_markdown/parser.py:parse
- The parser enforces no convention. What an attribute means, and which names a document uses, is how the documents are written.

## Attributes

- A name followed by a colon and nothing else has an empty value, which is not the same as no value.
    + xref: src/controlled_markdown/parser.py:split_named
- `heading` is reserved, and an explicit `+ heading` is an error.
    + xref: src/controlled_markdown/parser.py:RESERVED, src/controlled_markdown/parser.py:parse
- A `* ` line with no name is an error.
    + xref: src/controlled_markdown/parser.py:parse

## Blocks

- A quote, a code node, and a table each need a line above them.
    + xref: src/controlled_markdown/parser.py:parse
- One at document level, above the first heading, is an error.
    + xref: src/controlled_markdown/parser.py:parse
- A quoted line indented deeper than the quote's first line is an error.
    + xref: src/controlled_markdown/parser.py:parse
- The closing fence is the same character as the opening one, at least as long, at the node's indent, and it has no info string.
    + xref: src/controlled_markdown/parser.py:_closes, src/controlled_markdown/parser.py:FENCE_RE
- A code node with no closing fence is an error, and so is a line under it at a shallower indent.
    + xref: src/controlled_markdown/parser.py:parse

## Headings

- More than six `#` is an error, and so is a trailing `#` closer.
    + xref: src/controlled_markdown/parser.py:parse, src/controlled_markdown/parser.py:CLOSER_RE
- A setext underline, `===` or `---` under a line, is not a heading.
    + xref: src/controlled_markdown/parser.py:parse
- A heading with no text is allowed, and it groups the lines under it.
    + xref: src/controlled_markdown/parser.py:parse
- A heading may stand directly under a directive, at the directive's child indent.
    + xref: src/controlled_markdown/parser.py:parse
    - Its depth counts its heading ancestors alone, so the directive adds none.
    - The lines under it start from the directive's own level.
        ```
        * if: reference
            ### Reference solver
            - The solver the session reads.
        ```

## Reuse

- An `include` value with a `#` in it is an error.
    + xref: src/controlled_markdown/renderers.py:_include
* comment:
    - A section is reached with `inline`.
- A document that reaches itself, by either directive, is an error.
    + xref: src/controlled_markdown/renderers.py:_include, src/controlled_markdown/renderers.py:_inline

## Front matter

- A front matter block with no closing `---` is an error.
    + xref: src/controlled_markdown/parser.py:split_front

## Canonical form

- `fmt` writes canonical form: heading depth from the tree, four-space indent, the writer's blank lines, the escapes the block-syntax rule needs, and a late attribute moved up. Everything else stands as written.
    + xref: src/controlled_markdown/formatter.py:write, src/controlled_markdown/__main__.py:main
- Round trip holds: parsing what the formatter writes gives the tree it was written from.
    + xref: src/controlled_markdown/round_trip.py:round_trips

## Rules

- Each rule the check reports has a short name, which the check prints beside its message.
    + xref: src/controlled_markdown/nodes.py:Rule, src/controlled_markdown/nodes.py:ControlledMarkdownError
