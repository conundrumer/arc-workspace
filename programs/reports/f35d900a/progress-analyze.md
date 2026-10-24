# progress-analyze

- `interference`: PreToolUse hook on Bash, which blocked the first `cat data/tasks/f35d900a.json` call because the documents had changed (the diff removed the workflow NOTE from the context). Cost: one call repeated. Nothing in the output was wrong.
- `interference`: PreToolUse hook on Bash, which blocked a shell `for` loop that printed solver headers ("unsupported executable construct 'for'"). Cost: one call, run again as a single `awk` over the files. Nothing in the output was wrong.
