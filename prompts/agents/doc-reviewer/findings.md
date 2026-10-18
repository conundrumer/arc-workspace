+ budget: 1800
* comment: when editing this doc
    - The doc reviewer reads this document by the links of the items `File the tickets` and `Send the findings` of its [checklist](prompts/agents/doc-reviewer/checklist.md), once it has made the findings of a review.
    - Acts, each with its section:
        - Filing a review's findings as tickets, sending the others, and holding back those left for a decision: [Filing and sending findings](#filing-and-sending-findings).

# Filing and sending findings
- When you file the findings of a review, file as a `bug` ticket each finding that does not block the change, as [Findings that block a change](prompts/agents/notes/launching.md#findings-that-block-a-change) gives.
- When you send a finding that blocks the change, send it with SendMessage, with the line, the rule it breaks, the reader it fails, and whether it needs a decision. Send each, by the part your brief gives each editor, to the first of these editors that the change has: for a line of the document set or the text of an `mctx` fragment, the editor whose part gives the documents; the editor whose part, other than the whole change, gives the files of the finding's line; the editor whose part is the whole change.
- In the last round of review your brief gives, send no finding.
- Hold back each finding an editor's message gives as left for a decision: send it no more, until a later message gives it as kept or dropped, or gives its decision.
