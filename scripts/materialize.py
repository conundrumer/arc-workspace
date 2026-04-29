"""Materialize every upstream task → data/tasks/<id>.json at its highest variant level."""

from __future__ import annotations

from pathlib import Path

from arc.jsonio import format_file
from arc.materialize import materialize_default
from arc.upstream import UPSTREAM_DIR

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "tasks"


def all_upstream_ids() -> set[str]:
    ids: set[str] = set()
    for dataset_dir in UPSTREAM_DIR.iterdir():
        data_dir = dataset_dir / "data"
        if not data_dir.is_dir():
            continue
        for split_dir in data_dir.iterdir():
            if not split_dir.is_dir():
                continue
            for f in split_dir.glob("*.json"):
                ids.add(f.stem)
    return ids


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()

    ids = sorted(all_upstream_ids())
    written = 0
    failures: list[tuple[str, str]] = []
    for tid in ids:
        try:
            file_dict = materialize_default(tid)
            (OUT_DIR / f"{tid}.json").write_text(format_file(file_dict))
            written += 1
        except Exception as e:
            failures.append((tid, f"{type(e).__name__}: {e}"))

    print(f"wrote {written}/{len(ids)} tasks")
    if failures:
        print(f"\n{len(failures)} failures:")
        for tid, msg in failures[:20]:
            print(f"  {tid}: {msg}")
        if len(failures) > 20:
            print(f"  ... +{len(failures) - 20} more")


if __name__ == "__main__":
    main()
