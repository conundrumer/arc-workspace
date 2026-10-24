# f8c80d96 Analyze progress

## Issues
- `interference`: `timeout 60 uv run python -u work/task/f8c80d96/check_concept.py`, calling `lib_components.components.Components` as step 2 has it ("call the component in place of rebuilding it"), raised `RuntimeError: no souffle binary on PATH` from `src/souffle/install.py`.
    - Cost: one failed run, and a rebuild of 4-adjacency labelling in the check script in place of the component.
    - Output: nothing wrong in the output; the check runs on the rebuilt labelling, which is plain 4-adjacency flood fill. The component still does not run in this environment.
