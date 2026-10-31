# progress-analyze

- `interference`: `timeout 60 uv run python -u work/task/fcc82909/check_concept.py`, calling `lib_components.components.Components8` as step 2 of Analyze has a script do ("call the component in place of rebuilding it"), raises `RuntimeError: no souffle binary on PATH` (`src/souffle/install.py`); no souffle binary is on PATH or in `.venv/bin`.
    - Cost: one failed run and a search for the binary; the check was then rewritten to label the 8-connected blocks in plain Python.
    - Output: nothing was wrong in the output; the plain-Python check stands in for the lib component, and still does.
