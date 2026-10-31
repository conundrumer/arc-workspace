# Progress: analyze fc10701f

- `interference`: the PreToolUse:Bash hook held back the first Bash call (`git rev-parse ... && ls ...`) to show a document diff, which removed only the workflow-script note from the context. Cost: one Bash call made twice, and reading the diff. Output was not made wrong, and is not.
