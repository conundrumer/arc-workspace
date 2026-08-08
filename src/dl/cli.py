"""Commands the runner exposes, and the argv dispatch over them."""

import argparse
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from dl.deletions import deletion_report
from dl.fit import FitResult, render_fit, run_fit
from dl.fit_plan import probe_report, render_fit_plan
from dl.lint import lint_body
from dl.paths import SOLVERS_DIR, all_stems
from dl.render import render_pair_failure
from dl.rewrite_lint import HINTS, lint_rewrites
from dl.solve import PairResult, TaskResult, _pair_work, case_coverage, run_pair, run_task
from dl.souffle import _pool_workers, build_functors
from dl.sweep import render_sweep, sweep_report

type Findings = list[tuple[str, int, str, str]]

LINT_TIERS = ("lint", "rewrite", "hint")


def _lint_tiers(source: str, hints: bool) -> list[Findings]:
    """Findings per tier, in LINT_TIERS order; the hint tier is empty
    unless enabled."""
    style: Findings = lint_body(source)
    dec: Findings = []
    adv: Findings = []
    for f in lint_rewrites(source, hints):
        (adv if f[0] in HINTS else dec).append(f)
    return [style, dec, adv]


def _finding_line(stem: str, tier: str, cat: str, lineno: int, match: str) -> str:
    if tier == "lint":
        match = f"`{match}`"  # style matches are bare code fragments
    return f"{stem}.dl:{lineno}: {cat}: {match}"


def _print_findings(stems: list[str], hints: bool) -> int:
    """Print the tier sections for `stems`; return the finding count."""
    by_tier: list[dict[str, Findings]] = [{}, {}, {}]
    for stem in stems:
        source = (SOLVERS_DIR / f"{stem}.dl").read_text()
        for held, tier in zip(by_tier, _lint_tiers(source, hints),
                              strict=True):
            if tier:
                held[stem] = tier

    total = 0
    for label, held in zip(LINT_TIERS, by_tier, strict=True):
        if not held:
            continue
        print()
        count = sum(len(v) for v in held.values())
        total += count
        print(f"--- {label} findings: {count} across {len(held)} solver(s) ---")
        for stem in sorted(held):
            for cat, lineno, match, _ in held[stem]:
                print(f"  {_finding_line(stem, label, cat, lineno, match)}")
    return total


def cmd_lint(
    stem: str | None, hints: bool = False,
) -> int:
    """Lint only: no solver runs, no fit checks, no Souffle needed."""
    if stem is not None and _missing(stem):
        return 2
    total = _print_findings([stem] if stem else all_stems(), hints)
    if total == 0:
        print("lint: ok")
        return 0
    return 1


def _missing(stem: str) -> bool:
    if (SOLVERS_DIR / f"{stem}.dl").exists():
        return False
    print(f"no solver at {SOLVERS_DIR / f'{stem}.dl'}", file=sys.stderr)
    return True


def cmd_one(stem: str, hints: bool = False) -> int:
    if _missing(stem):
        return 2
    build_functors()
    result = run_task(stem)
    for p in result.pairs:
        if p.ok:
            n = len(p.variants)
            suffix = f" ({n} variants)" if n > 1 else ""
            print(f"{p.kind}[{p.idx}]: PASS{suffix}")
        else:
            for line in render_pair_failure(p):
                print(line)

    coverage = case_coverage(result.pairs)
    if coverage:
        print()
        print(f"--- {len(coverage)} case-coverage finding(s) in {stem}.dl ---")
        for line in coverage:
            print(f"  {line}")

    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    tiers = _lint_tiers(source, hints)
    for label, findings in zip(LINT_TIERS, tiers, strict=True):
        if not findings:
            continue
        print()
        print(f"--- {len(findings)} {label} finding(s) ---")
        for cat, lineno, match, _ in findings:
            print(f"  {_finding_line(stem, label, cat, lineno, match)}")

    fit = run_fit(stem)
    print()
    if not any(tiers):
        print("lint: ok")
    if fit is not None:
        for line in render_fit(fit):
            print(line)

    return 0 if result.all_pass else 1


def cmd_all(hints: bool = False) -> int:
    build_functors()
    stems = all_stems()

    # Flatten all (stem, pair) work so the pool sees one big queue.
    all_work: list[tuple] = []
    for stem in stems:
        all_work.extend(_pair_work(stem))

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        all_pairs = list(executor.map(lambda w: run_pair(*w), all_work))

    by_stem: dict[str, list[PairResult]] = defaultdict(list)
    for w, p in zip(all_work, all_pairs, strict=True):
        by_stem[w[0]].append(p)
    results = [TaskResult(stem=stem, pairs=by_stem.get(stem, [])) for stem in stems]

    for r in results:
        marker = "PASS" if r.all_pass else "FAIL"
        print(f"{r.stem}: {r.passes}/{r.total} {marker}")

    failed = [r for r in results if not r.all_pass]
    if failed:
        print()
        print(f"--- {len(failed)} failing solver(s) ---")
        for r in failed:
            print(f"\n{r.stem}:")
            for p in r.pairs:
                if p.ok:
                    continue
                for line in render_pair_failure(p):
                    print(f"  {line}")

    coverage_findings = {
        r.stem: cov for r in results if (cov := case_coverage(r.pairs))
    }
    if coverage_findings:
        print()
        total = sum(len(v) for v in coverage_findings.values())
        print(f"--- case-coverage findings: {total} across "
              f"{len(coverage_findings)} solver(s) ---")
        for stem in sorted(coverage_findings):
            for line in coverage_findings[stem]:
                print(f"  {stem}.dl: {line}")

    _print_findings(stems, hints)

    fit_results: dict[str, FitResult] = {}
    for stem in stems:
        r = run_fit(stem)
        if r is not None:
            fit_results[stem] = r
    if fit_results:
        problems = {
            s: r for s, r in fit_results.items() if r.diff or r.error or r.circular
        }
        print()
        ok = len(fit_results) - len(problems)
        print(f"--- fit checks: {ok}/{len(fit_results)} ok ---")
        for s in sorted(problems):
            for line in render_fit(problems[s]):
                print(f"  {s}.dl: {line}")

    print()
    print(f"summary: {len(results) - len(failed)}/{len(results)} solvers")
    return 0 if not failed else 1


def cmd_sweep(stem: str, max_candidates: int = 64) -> int:
    if _missing(stem):
        return 2
    build_functors()
    for line in render_sweep(sweep_report(stem, max_candidates)):
        print(line)
    return 0


def _print_deletions(stem: str) -> int:
    report = deletion_report(stem)
    if report is None:
        print("baseline fails: stored source does not pass train+test")
        return 1
    total, unchanged = report
    if not unchanged:
        print(f"every deletion changes the result ({total} tested)")
    else:
        print(f"{len(unchanged)}/{total} deletions change nothing:")
        for lineno, kind, text in unchanged:
            print(f"  {stem}.dl:{lineno}: {kind} `{text}`")
    return 0


def cmd_deletions(stem: str) -> int:
    if _missing(stem):
        return 2
    build_functors()
    return _print_deletions(stem)


def cmd_audit(stem: str) -> int:
    """Both evidence audits of a finished solver: fill sweep + deletions."""
    if _missing(stem):
        return 2
    build_functors()
    print("--- sweep ---")
    for line in render_sweep(sweep_report(stem)):
        print(line)
    print()
    print("--- deletions ---")
    return _print_deletions(stem)


def cmd_fit_plan(stem: str) -> int:
    """Which Consts slots need Fit relations, from the proposer probe."""
    if _missing(stem):
        return 2
    build_functors()
    for line in render_fit_plan(probe_report(stem)):
        print(line)
    return 0


COMMANDS = ("run", "lint", "sweep", "deletions", "audit", "fit-plan")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Souffle solvers and their checks.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser(
        "run", help="pairs, lint, fit checks; the default when no command is named",
    )
    lint = sub.add_parser("lint", help="lint only, no solver runs")
    for p in (run, lint):
        p.add_argument("stem", nargs="?",
                       help="one solver; all of them when omitted")
        p.add_argument("--hints", action=argparse.BooleanOptionalAction,
                       default=True, help="include the hint tier")

    sweep = sub.add_parser("sweep", help="fill sweep only")
    sweep.add_argument("stem")
    sweep.add_argument("cap", nargs="?", type=int, default=64,
                       help="max candidates per slot")

    sub.add_parser("deletions", help="deletion report only").add_argument("stem")
    sub.add_parser("audit", help="fill sweep + deletion report").add_argument("stem")
    sub.add_parser(
        "fit-plan", help="which Consts slots need Fit relations",
    ).add_argument("stem")
    return parser


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in (*COMMANDS, "-h", "--help"):
        argv = ["run", *argv]
    args = _parser().parse_args(argv)
    match args.cmd:
        case "lint":
            return cmd_lint(args.stem, args.hints)
        case "sweep":
            return cmd_sweep(args.stem, args.cap)
        case "deletions":
            return cmd_deletions(args.stem)
        case "audit":
            return cmd_audit(args.stem)
        case "fit-plan":
            return cmd_fit_plan(args.stem)
        case _:
            if args.stem:
                return cmd_one(args.stem, args.hints)
            return cmd_all(args.hints)
