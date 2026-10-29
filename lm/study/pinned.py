"""The pinned copies of the repo's Python modules that the stages of allpoints.py and the small-set scripts import.

Other sessions commit to lm/ and engine/arclog-py often. A stage that imported those files from the tree would see
each commit, and its stamps (the reuse keys, the checks digest, the loader's version) would change with it. So the
stages import copies under work/lm/.venv/pinned, beside the wheel record, laid out as in the repo:

    work/lm/.venv/pinned/lm/<LM_FILES>
    work/lm/.venv/pinned/engine/arclog-py/<ENGINE_FILES>
    work/lm/.venv/pinned/data -> the repo's data/            (the modules find the task files from their own place)
    work/lm/.venv/pinned/work/arclog -> the repo's work/arclog/
    work/lm/.venv/pinned/pin.json                             (the engine state the copies come from)

`use()` puts the pinned lm/ first on sys.path (lm/export_rollouts.py then puts the pinned engine/arclog-py first in
turn). Where there is no pin, it uses the repo's lm/. `allpoints.py run --wheel` makes the pin again from the tree
(`pin_tree`).
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[0]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import json, os, shutil, sys
from pathlib import Path

ROOT = MAIN_ROOT
PIN = ROOT / "work/lm/.venv/pinned"
LM_FILES = ("encoder.py", "export_rollouts.py", "rollout_labels.py", "sample.py", "train.py", "value_eval.py")
ENGINE_FILES = ("tables_export.py", "export_rows.py", "export_checks.py")


def lm_dir():
    """The lm/ directory the stages import: the pinned one where it exists, else the repo's."""
    return PIN / "lm" if (PIN / "pin.json").exists() else REPO_ROOT / "lm"


def use():
    """Puts lm_dir() first on sys.path, and gives it."""
    d = lm_dir()
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
    return d


def pin_tree(state):
    """Makes the pin from the files of the tree, with `state` (the engine state) in pin.json."""
    files = {f"lm/{f}": ROOT / "lm" / f for f in LM_FILES}
    files.update({f"engine/arclog-py/{f}": ROOT / "engine/arclog-py" / f for f in ENGINE_FILES})
    write(files, state)


def write(sources, state):
    """Writes the pin: each {pinned path: source file} copied, the links to data/ and work/arclog/, and pin.json."""
    new = PIN.with_name(PIN.name + ".new")
    shutil.rmtree(new, ignore_errors=True)
    for path, source in sources.items():
        (new / path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, new / path)
    os.symlink(ROOT / "data", new / "data")
    (new / "work").mkdir()
    os.symlink(ROOT / "work/arclog", new / "work/arclog")
    (new / "pin.json").write_text(json.dumps(state, indent=1) + "\n")
    shutil.rmtree(PIN, ignore_errors=True)
    new.rename(PIN)
