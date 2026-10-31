# ef135b50 Analyze progress

- `interference`: command `timeout 60 uv run python -u work/task/ef135b50/check_concept.py`, where the step 2 line "call the component in place of rebuilding it" had me call `lib_components.components.Components`. The call raised `RuntimeError: no souffle binary on PATH` from `src/souffle/install.py`. Cost: one failed run, plus a rewrite of the check to label the 4-connected components in plain Python. Output: nothing was wrong in it; the components of a solid, non-touching rectangle scene are plain to label. The lib call still fails in this environment.
