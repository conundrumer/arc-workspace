# f35d900a create: progress notes

- interference, command `uv run python scripts/run_dl.py f35d900a`: the PreToolUse hook blocks it outside `scripts/run_heavy.py`, and the pace lines give the bare form. Cost: one failed call and one read of `prompts/agents/notes/project-commands.md`. Every later run went through `run_heavy.py`. Output not wrong.
- interference, command `uv run python scripts/run_dl.py derive f35d900a`: it wrote a witness for each of 7 `reach_cap` derivations, each on the `long-side` input. Four of them (ConstInDim, Period, TileCount, TileDim) give a grid dimension or a span-sized period, so they never cap anything. That made the first audit print 1270 lines. Cost: about 3 minutes to read it and sort out the derivations. Output not wrong.
