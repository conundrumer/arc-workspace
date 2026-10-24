# f25fbde4 — Analyze progress

## Notes
- `interference`: [Analyze](context) step 2 "call the component in place of rebuilding it": `Components8(Primitive.NUMBER, sizes=..., node=...)` from `lib_components.components`, run by `uv run python -u work/task/f25fbde4/probe.py pairs`, raised `RuntimeError: no souffle binary on PATH` (src/souffle/install.py). Cost: one failed probe run, and the probe now does its own 4- and 8-adjacency flood fill instead of calling the lib. Nothing in the output was wrong, and nothing is now: the fallback labels connected components the same way (a probe check, not the lib's).
