# progress — analyze f823c43c

- `interference`: command `for f in $(grep -l ...); do awk ... $f; done` (to print the headers of the wallpaper and noise solvers) was blocked by the PreToolUse hook ("unsupported executable construct 'for'"). Cost: one extra call; I printed the headers with one `awk` over a list of files instead. The output was not wrong, and nothing is still wrong.
