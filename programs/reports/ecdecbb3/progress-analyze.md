# progress-analyze

- `interference`: the PreToolUse:Bash hook (a tool behavior) blocked the pass's first Bash call (`git rev-parse ...; ls ...`) to deliver a context diff that removed the workflow-script NOTE section. Cost: one repeated call and reading the diff. The output was not wrong, and is not wrong now.
