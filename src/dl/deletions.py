"""Delete structure from a solver and report what the pairs still accept."""

import re
from concurrent.futures import ThreadPoolExecutor

from arc.task import load as load_task
from dl.fit import fit_check
from dl.paths import SOLVERS_DIR
from dl.solve import _profile
from dl.souffle import _pool_workers
from dl.source import _comp_span

NEG_ATOM_RE = re.compile(r"(?<![=!])!(?!=)\s*[\w.]+\s*\(")


def _rule_spans(source: str, fit: bool = False) -> list[tuple[int, int]]:
    """Inclusive line spans of rules — the Fit comp's when `fit`, the rest otherwise.

    Style-parsed: head and `:-` share the first line; `.` ends the statement.
    """
    lines = source.splitlines()
    fs, fe = _comp_span(source, "Fit")
    fit_lines = set(range(fs - 1, fe + 1)) if (fs, fe) != (0, 0) else set()
    spans = []
    i = 0
    while i < len(lines):
        code = lines[i].split("//")[0]
        if (i in fit_lines) != fit or ":-" not in code or code.lstrip().startswith("."):
            i += 1
            continue
        j = i
        while j < len(lines) and not lines[j].split("//")[0].rstrip().endswith("."):
            j += 1
        if j == len(lines):
            break
        spans.append((i, j))
        i = j + 1
    return spans


def _drop_atom(code: str, start: int, end: int) -> str:
    """Remove code[start:end] plus one adjoining comma separator."""
    after = code[end:].lstrip()
    if after.startswith(","):
        return code[:start] + after[1:].lstrip()
    before = code[:start].rstrip()
    if before.endswith(","):
        return before[:-1] + code[end:]
    return code[:start] + code[end:]


def deletions(source: str, fit: bool = False):
    """Yield (lineno, kind, text, modified_source) structural deletions.

    Kinds: 'rule' deletes the whole rule; 'negation' deletes one negated
    body atom (the modified rule collapses to one line). With `fit`, the
    deletions come from the Fit comp's rules; otherwise from the rest.
    """
    lines = source.splitlines()
    for a, b in _rule_spans(source, fit):
        rule = " ".join(ln.split("//")[0].strip() for ln in lines[a:b + 1])
        head = rule.split(":-")[0].strip()
        yield (a + 1, "rule", head, "\n".join(lines[:a] + lines[b + 1:]) + "\n")
        for m in NEG_ATOM_RE.finditer(rule):
            depth, k = 0, m.end() - 1
            while k < len(rule):
                if rule[k] == "(":
                    depth += 1
                elif rule[k] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            atom = rule[m.start():k + 1]
            modified = lines[:a] + [_drop_atom(rule, m.start(), k + 1)] + lines[b + 1:]
            yield (a + 1, "negation", atom, "\n".join(modified) + "\n")


def deletion_report(stem: str) -> tuple[int, list[tuple[int, str, str]]] | None:
    """Structural deletions that change no pair's output or derived fill.

    A deletion that changes nothing removed structure the pairs never
    instantiate. Fit deletions are judged by the fit check instead of the
    variant profile. Informational — such a deletion points at an
    unwitnessed guard or rule, not a violation. None when the stored
    source itself fails.
    """
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    task = load_task(stem.split("_", 1)[0])
    examples = list(task.train) + list(task.test)
    reference = _profile(source, examples)
    if reference is None:
        return None

    def fit_ok(src):
        r = fit_check(src, task)
        return r is not None and not r.error and not r.diff

    dels = [("solve", d) for d in deletions(source)]
    if fit_ok(source):
        dels += [("fit", d) for d in deletions(source, fit=True)]

    def test(tagged):
        mode, (lineno, kind, text, mod) = tagged
        if mode == "solve":
            no_change = _profile(mod, examples) == reference
            return (lineno, kind, text) if no_change else None
        return (lineno, f"fit {kind}", text) if fit_ok(mod) else None

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        unchanged = [r for r in executor.map(test, dels) if r]
    return (len(dels), sorted(unchanged))
