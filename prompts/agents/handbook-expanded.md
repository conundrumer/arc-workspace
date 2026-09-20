---
name: handbook-expanded
description: "The handbook, with the lib's full interface: every component's relations and their docs."
model: opus
effort: high
tools: Read, Grep, Glob, Bash, Edit, Write
---

+ lib: interface

- A heading with nothing under it names a section this rendering abridges.
    - `uv run python scripts/context.py section '<doc>#<heading>'` prints that section in full, the doc being the `##` heading the section sits under.
- An entry shown as one bold phrase and a sentence is abridged the same way, and its bold phrase is the heading to name.

* inline: notes.md#citations

* include: ../handbook.md
    + exclude: draft, gloss
    + abridged: ../../docs/handbook/patterns.md
