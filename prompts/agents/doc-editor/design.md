+ budget: 1100
* comment: when editing this doc
    - The doc editor reads this document by the link of the item `Write the edit` of its [checklist](prompts/agents/doc-editor/checklist.md), once it has worked out the readers of the places it edits.
    - Acts, each with its section:
        - Building its ticket's `Design`, and sending the code change a move of an `mctx` fragment needs: [Building the Design](#building-the-design).

# Building the Design
- Build the `Design` of your change's ticket, where it gives one for the documents. Where the documents show a better place or a better existing line to extend, build that, and give in your report the departure with its reason.
- Where you move the text of an `mctx` fragment, send the code change that move needs, with SendMessage, to a code editor of your change that your brief or a message gives.
    + xref: src/controlled_markdown/prose.py:mctx
