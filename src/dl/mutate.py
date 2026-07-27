"""Delete structure from a solver and report what the pairs still accept."""

import re
from concurrent.futures import ThreadPoolExecutor

from arc.task import load as load_task
from dl.paths import SOLVERS_DIR
from dl.solve import _profile
from dl.souffle import _pool_workers
from dl.source import _comp_span

NEG_ATOM_RE = re.compile(r"(?<![=!])!(?!=)\s*[\w.]+\s*\(")


def _rule_spans(source: str) -> list[tuple[int, int]]:
    """Inclusive line spans of rules, Fit comp excluded.

    Style-parsed: head and `:-` share the first line; `.` ends the statement.
    """
    lines = source.splitlines()
    fs, fe = _comp_span(source, "Fit")
    fit = set(range(fs - 1, fe + 1)) if (fs, fe) != (0, 0) else set()
    spans = []
    i = 0
    while i < len(lines):
        code = lines[i].split("//")[0]
        if i in fit or ":-" not in code or code.lstrip().startswith("."):
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


def mutants(source: str):
    """Yield (lineno, kind, text, mutated_source) structural mutants.

    Kinds: 'rule' deletes the whole rule; 'negation' deletes one negated
    body atom (the mutated rule collapses to one line). The Fit comp does
    not run in solve mode, so it is not mutated.
    """
    lines = source.splitlines()
    for a, b in _rule_spans(source):
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
            mutated = lines[:a] + [_drop_atom(rule, m.start(), k + 1)] + lines[b + 1:]
            yield (a + 1, "negation", atom, "\n".join(mutated) + "\n")


def mutation_report(stem: str) -> tuple[int, list[tuple[int, str, str]]] | None:
    """Structural mutants that survive every train+test pair.

    A surviving mutant keeps the full variant profile without the deleted
    structure: the pairs never instantiate it. Informational — a survivor
    points at an unwitnessed guard or rule, not a violation. None when the
    stored source itself fails.
    """
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    task = load_task(stem.split("_", 1)[0])
    examples = list(task.train) + list(task.test)
    reference = _profile(source, examples)
    if reference is None:
        return None
    muts = list(mutants(source))

    def test(m):
        lineno, kind, text, mod = m
        return (lineno, kind, text) if _profile(mod, examples) == reference else None

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        survivors = [r for r in executor.map(test, muts) if r]
    return (len(muts), sorted(survivors))
