# fea12743 progress

- `interference`: the PreToolUse Bash hook blocked a header listing written as a shell `for` loop ("unsupported executable construct 'for'"). It cost one call, and I reran the listing as `grep -l | xargs grep -l`. Nothing in the output was wrong.
- `interference`: the first Bash call was held back by the hook because the context had changed at HEAD b3ca356d (the workflow NOTE was removed). It cost one call. Nothing in the output was wrong.
