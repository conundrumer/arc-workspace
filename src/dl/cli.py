"""Commands the runner exposes, and the argv dispatch over them."""

import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from dl.fit import FitResult, render_fit, run_fit
from dl.lint import lint_body
from dl.deletions import deletion_report
from dl.paths import SOLVERS_DIR, all_stems
from dl.fit_plan import probe_report, render_fit_plan
from dl.render import render_pair_failure
from dl.solve import PairResult, TaskResult, _pair_work, case_coverage, run_pair, run_task
from dl.souffle import _pool_workers, build_functors
from dl.sweep import render_sweep, sweep_report


def cmd_one(stem: str) -> int:
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
    findings = lint_body(source)
    if findings:
        print()
        print(f"--- {len(findings)} lint finding(s) in {stem}.dl ---")
        for cat, lineno, match, line in findings:
            print(f"  L{lineno}: {cat} `{match}`  →  {line.strip()}")

    fit = run_fit(stem)
    print()
    if not findings:
        print("lint: ok")
    if fit is not None:
        for line in render_fit(fit):
            print(line)

    return 0 if result.all_pass else 1


def cmd_all() -> int:
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

    lint_findings: dict[str, list] = {}
    for stem in stems:
        source = (SOLVERS_DIR / f"{stem}.dl").read_text()
        findings = lint_body(source)
        if findings:
            lint_findings[stem] = findings

    if lint_findings:
        print()
        total = sum(len(v) for v in lint_findings.values())
        print(f"--- lint findings: {total} across {len(lint_findings)} solver(s) ---")
        for stem in sorted(lint_findings):
            for cat, lineno, match, line in lint_findings[stem]:
                print(f"  {stem}.dl:L{lineno}: {cat} `{match}`  →  {line.strip()}")

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
            print(f"  L{lineno}: {kind} `{text}`")
    return 0


def cmd_deletions(stem: str) -> int:
    build_functors()
    return _print_deletions(stem)


def cmd_audit(stem: str) -> int:
    """Both evidence audits of a finished solver: fill sweep + deletions."""
    build_functors()
    print("--- sweep ---")
    for line in render_sweep(sweep_report(stem)):
        print(line)
    print()
    print("--- deletions ---")
    return _print_deletions(stem)


def cmd_fit_plan(stem: str) -> int:
    """Which Consts slots need Fit relations, from the proposer probe."""
    build_functors()
    for line in render_fit_plan(probe_report(stem)):
        print(line)
    return 0


def _usage() -> str:
    return "\n".join([
        f"usage: {sys.argv[0]} "
        "[--audit <stem> | --sweep <stem> [cap] | --deletions <stem> | "
        "--fit-plan <stem> | <stem>]",
        "",
        "  (none)                run every solver: pairs, lint, fit checks",
        "  <stem>                run one solver: pairs, lint, fit check",
        "  --audit <stem>        fill sweep + deletion report",
        "  --sweep <stem> [cap]  fill sweep only; cap = max candidates per slot",
        "  --deletions <stem>    deletion report only",
        "  --fit-plan <stem>     which Consts slots need Fit relations",
    ])


def main(argv: list[str]) -> int:
    if len(argv) == 0:
        return cmd_all()
    if argv in (["-h"], ["--help"]):
        print(_usage())
        return 0
    if len(argv) == 1:
        return cmd_one(argv[0])
    if len(argv) == 2 and argv[0] == "--sweep":
        return cmd_sweep(argv[1])
    if len(argv) == 3 and argv[0] == "--sweep":
        return cmd_sweep(argv[1], int(argv[2]))
    if len(argv) == 2 and argv[0] == "--deletions":
        return cmd_deletions(argv[1])
    if len(argv) == 2 and argv[0] == "--audit":
        return cmd_audit(argv[1])
    if len(argv) == 2 and argv[0] == "--fit-plan":
        return cmd_fit_plan(argv[1])
    print(_usage(), file=sys.stderr)
    return 2
