# faa9f03d progress

- `interference`: a hook (PreToolUse on Bash) blocked a command that ran the probe over five witness files in a shell `for` loop ("unsupported executable construct 'for'"). Cost: one retry, split into separate calls. Nothing in the output was wrong, and nothing is wrong now.
- `interference`: a hook (PreToolUse on Bash) held back the first two commands of the pass (`cat data/tasks/faa9f03d.json` and a directory listing) because the documents had changed since launch. Cost: one round trip, after which both were run again. Nothing in the output was wrong, and nothing is wrong now.
