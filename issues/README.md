# Issues
- Each file here is a doc or tool issue that an Analyze, Create or Refine pass hit, filed at the end of that pass in the form [issue-filing](prompts/agents/notes.md#issue-filing) gives.
- Take the fields and sections you know, and skip the rest.
- The filer wrote from the rendering it loaded, which may be older than the current docs, so check the file's evidence against the current state.

## Statuses
- The directories `new`, `assigned` and `resolved` are statuses, and moving a file between them is its transition.
- Claim a file by moving it with `mv`: of two concurrent moves of one file, one fails.
- After the move, append a line to the file's log, in the form `<time> <status> [<actor>]: <note>`.
    - The log is the file's last section, `## Log`, and the first transition adds it.
    - The line into `resolved` leads its note with the resolution: `fixed`, `duplicate`, `cannot-reproduce`, `wontfix` or `invalid`.
