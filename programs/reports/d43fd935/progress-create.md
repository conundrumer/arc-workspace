# d43fd935 create: progress notes

- interference: the PreToolUse Bash hook held back the first Bash call of the pass so that it could show a context diff. The only change in that diff was that the workflow note was removed. Cost: one repeated call. Output wrong: no.
- interference: the PreToolUse Bash hook blocked a `for` loop over solver files ("unsupported executable construct 'for'"). I used Grep instead. Cost: one call. Output wrong: no.
