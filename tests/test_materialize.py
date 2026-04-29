"""Integration tests against the real migrated patches + materialized tasks."""

import json
from pathlib import Path

import pytest

from arc.materialize import materialize_default
from arc.upstream import load

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
def test_default_matches_disk(task_id):
    file_dict = materialize_default(task_id)
    on_disk = json.loads((TASKS_DIR / f"{task_id}.json").read_text())
    assert file_dict == on_disk


def test_default_records_highest_variant():
    """1b8318e3 has B and C variants; default should apply both and report C,
    and the materialized grids should differ from raw upstream."""
    default = materialize_default("1b8318e3")
    raw, _ = load("1b8318e3")
    assert default["variant"] == "C"
    assert default["train"][0]["input"] != raw.train[0].input


def test_default_omits_variant_when_no_variants():
    file_dict = materialize_default("17829a00")
    assert "variant" not in file_dict


def test_alt_kind_present_on_examples_with_branches():
    file_dict = materialize_default("89565ca0")
    has_alt = any(
        "alt" in ex and ex["alt"]["kind"] in ("rule", "tiebreak")
        for ex in file_dict["train"] + file_dict["test"]
    )
    assert has_alt


def test_v2_only_task_has_single_source():
    file_dict = materialize_default("17829a00")
    assert len(file_dict["source"]) == 1
    assert file_dict["source"][0]["dataset"] == "arc-agi-2"
    assert "perm" not in file_dict["source"][0]


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


def test_unpatched_task_materializes_as_canonical_passthrough():
    """An unpatched task materializes with just id + source + train/test."""
    file_dict = materialize_default("00576224")
    assert "patches" not in file_dict
    assert "variant" not in file_dict
    assert len(file_dict["train"]) > 0


def test_patches_list_collects_canonical_and_variants():
    """A task with both a canonical fix and variant patches lists each in order."""
    file_dict = materialize_default("e5062a87")  # canonical fix + C variant
    levels = [p["level"] for p in file_dict["patches"]]
    assert levels == ["canonical", "C"]
    assert "comment" in file_dict["patches"][0]
    assert "issue" in file_dict["patches"][0]


def test_patches_list_for_variant_only_task():
    """A task with no canonical patch but with variants lists only the variants."""
    file_dict = materialize_default("1b8318e3")  # no canonical, B + C
    levels = [p["level"] for p in file_dict["patches"]]
    assert levels == ["B", "C"]
