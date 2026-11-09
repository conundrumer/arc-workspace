"""The command of `arclog_convert.lint`: it checks the files of `GEN` or the paths given, and exits with status 1 where it
reports a violation. A file under `GEN` is read through `arclog_convert.readback.read_checked`, so a file that is not
current is reported as the violation `stale`; any other path is read as it stands. The command is in this module, and
not in `arclog_convert.lint`, which the converter imports."""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

from arclog_convert import lint, out as output_dir
from arclog_convert.lint import GEN, Linter, arcdata_errs
from arclog_convert.readback import Stale, read_checked


def read_file(path: Path) -> str:
    """The text of the file `path`: through `read_checked` where it stands under `GEN`, and `read_text` elsewhere."""
    return read_checked(path) if GEN.resolve() in path.resolve().parents else path.read_text()


def lint_group(paths: list[Path]) -> list[tuple[Path, list]]:
    """Each path's violations, an arcdata file's read with the Linter of
    the group's arclog file."""
    lint.READER = read_file
    linted: dict[Path, Linter] = {}
    out = []
    for p in sorted(paths, key=lambda x: x.suffix == ".arcdata"):
        try:
            if p.suffix == ".arcdata":
                errs = arcdata_errs(p, linted.get(p.with_suffix(".arclog")))
            else:
                lt = Linter(p)
                lt.run()
                errs = lt.errs
                linted[p] = lt
        except Stale as e:
            errs = [(0, "stale", str(e))]
        out.append((p, errs))
    return out


def main(argv: list[str]) -> int:
    if "-h" in argv or "--help" in argv:
        print(lint.__doc__)
        return 0
    show_all = "--all" in argv
    argv = [a for a in argv if a != "--all"]
    paths = [Path(a) for a in argv] or (sorted(GEN.glob("*.arclog")) + sorted(output_dir().glob("*.arcscene"))
                                        + sorted(GEN.glob("*.arcdata")))
    counts: Counter = Counter()
    files: dict[str, set] = defaultdict(set)
    quiet = len(paths) > 20 and not show_all
    shown: Counter = Counter()
    # an arcdata file is linted with its arclog file's Linter, so the two go to one worker
    groups: dict[Path, list[Path]] = defaultdict(list)
    for p in paths:
        groups[p.with_suffix(".arclog") if p.suffix == ".arcdata" else p].append(p)
    order = sorted(groups.values(), key=lambda g: -sum(x.stat().st_size for x in g if x.exists()))
    if len(order) > 20:
        from concurrent.futures import ProcessPoolExecutor

        from engine.pool import pool_size
        with ProcessPoolExecutor(min(len(order), pool_size())) as pool:
            found = dict(x for got in pool.map(lint_group, order) for x in got)
    else:
        found = dict(x for g in order for x in lint_group(g))
    for p in paths:
        for line, code, msg in found[p]:
            counts[code] += 1
            files[code].add(p.name)
            if not quiet or shown[code] < 4:
                shown[code] += 1
                print(f"{p}:{line}: {code}: {msg}")
    print()
    for code, n in counts.most_common():
        print(f"  {code:18} {n:6} in {len(files[code])} files")
    for suffix in sorted({p.suffix for p in paths}):
        some = [p for p in paths if p.suffix == suffix]
        clean = sum(1 for p in some if not any(p.name in f for f in files.values()))
        print(f"{clean} of {len(some)} {suffix} files clean")
    return int(bool(counts))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
