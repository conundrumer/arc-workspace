# f9012d9b: Analyze progress

- `interference`: the command `for f in ...; do awk '/^$/{exit} 1' programs/solvers/$f.dl; done`, which applies the header command from step 1 of `.claude/analyze-next.md` to several solvers at once, was blocked by the PreToolUse hook ("unsupported executable construct 'for'"). It cost one extra call, and one `awk` over every file did the same job. Nothing in the output was wrong.
