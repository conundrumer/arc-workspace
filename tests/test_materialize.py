"""Integration tests against the real migrated patches + materialized tasks.
The tests read the `data/upstream/` submodules, which the `upstream` fixture
sets up."""

import json
from pathlib import Path

import pytest

from arc.materialize import materialize_default

pytestmark = pytest.mark.usefixtures("upstream")

TASKS_DIR = Path(__file__).resolve().parents[1] / "data" / "tasks"


@pytest.mark.parametrize(
    "task_id",
    [
        "e5062a87",  # canonical fix + pure variant (C)
        "0d87d2a6",  # alt → @branch in canonical, shared+permuted source
        "1b8318e3",  # no canonical patch; simple+pure variants (B, C)
        "89565ca0",  # multi → @branch tiebreak in canonical
        "a416fc5b",  # dim-change @replace
        "17829a00",  # v2-only, no variants
    ],
)
def test_default_matches_disk(task_id: str) -> None:
    file_dict = materialize_default(task_id)
    on_disk = json.loads((TASKS_DIR / f"{task_id}.json").read_text())
    assert file_dict == on_disk


def test_shared_permuted_task_has_v2_perm():
    """0d87d2a6 is shared with v2 reordering. Canonical = v1 ordering;
    v2 source carries a non-identity perm mapping its order back to canonical."""
    file_dict = materialize_default("0d87d2a6")
    assert len(file_dict["source"]) == 2
    assert file_dict["source"][0]["dataset"] == "arc-agi-1"
    assert "perm" not in file_dict["source"][0]
    v2 = file_dict["source"][1]
    assert v2["dataset"] == "arc-agi-2"
    assert "perm" in v2
    train_perm = v2["perm"]["train"]
    assert train_perm != list(range(len(train_perm)))


