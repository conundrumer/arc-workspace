"""Delete structure from a solver and report what the pairs still accept."""

import re
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

from arc.task import load as load_task
from dl.dlparse import TOP, Index, ParseError, parse
from dl.fit import fit_check
from dl.paths import SOLVERS_DIR
from dl.solve import _profile
from dl.souffle import _pool_workers
from dl.source import _comp_span

NEG_ATOM_RE = re.compile(r"(?<![=!])!(?!=)\s*[\w.]+\s*\(")

type Deletion = tuple[int, str, str, str]  # lineno, kind, text, modified source


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


def _disjunctions(rule: str) -> list[tuple[int, int, list[tuple[int, int]]]]:
    """Parenthesized groups holding `;` branches, as (open, close,
    branch spans). A `;` belongs to the innermost open paren."""
    out: list[tuple[int, int, list[tuple[int, int]]]] = []
    stack: list[int] = []
    seps: dict[int, list[int]] = {}
    for i, ch in enumerate(rule):
        if ch == "(":
            stack.append(i)
            seps[i] = []
        elif ch == ";" and stack:
            seps[stack[-1]].append(i)
        elif ch == ")" and stack:
            start = stack.pop()
            if seps[start]:
                cuts = [start, *seps[start], i]
                spans = [
                    (cuts[k] + 1, cuts[k + 1]) for k in range(len(cuts) - 1)
                ]
                out.append((start, i, spans))
    return out


def _drop_atom(code: str, start: int, end: int) -> str:
    """Remove code[start:end] plus one adjoining comma separator."""
    after = code[end:].lstrip()
    if after.startswith(","):
        return code[:start] + after[1:].lstrip()
    before = code[:start].rstrip()
    if before.endswith(","):
        return before[:-1] + code[end:]
    return code[:start] + code[end:]


def _parses(source: str) -> bool:
    try:
        parse(source)
    except ParseError:
        return False
    return True


def deletions(source: str, fit: bool = False) -> Iterator[Deletion]:
    """Yield (lineno, kind, text, modified_source) structural deletions.

    Kinds: 'rule' deletes the whole rule; 'negation' deletes one negated
    body atom; 'disjunct' deletes one branch of a disjunction (either
    way the modified rule collapses to one line). With `fit`, the
    deletions come from the Fit comp's rules; otherwise from the rest.

    A deletion with no syntactic form — a negation that is the whole of
    a disjunct, say — is skipped rather than yielded malformed.
    """
    strict = _parses(source)
    for item in _variants(source, fit):
        if not strict or _parses(item[3]):
            yield item


def _variants(source: str, fit: bool) -> Iterator[Deletion]:
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
        for _, _, spans in _disjunctions(rule):
            for k, (s, e) in enumerate(spans):
                if k + 1 < len(spans):
                    cut = (s, spans[k + 1][0])  # branch plus trailing ';'
                else:
                    cut = (spans[k - 1][1], e)  # leading ';' plus branch
                shrunk = rule[:cut[0]] + rule[cut[1]:]
                modified = lines[:a] + [shrunk] + lines[b + 1:]
                yield (a + 1, "disjunct", rule[s:e].strip(),
                       "\n".join(modified) + "\n")


def _split_top_args(text: str) -> list[str]:
    args, depth, cur = [], 0, []
    for c in text:
        depth += c in "(["
        depth -= c in ")]"
        if c == "," and depth == 0:
            args.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    if cur:
        args.append("".join(cur))
    return args


def _drop_column(source: str, name: str, col: int) -> str | None:
    """Remove argument `col` from every `name(...)` — the decl field
    list included, since it matches the same shape."""
    out, i = [], 0
    pat = re.compile(rf"(?<![\w.]){name}\s*\(")
    while (m := pat.search(source, i)) is not None:
        depth, j = 1, m.end()
        while j < len(source) and depth:
            depth += source[j] == "("
            depth -= source[j] == ")"
            j += 1
        args = _split_top_args(source[m.end():j - 1])
        if col >= len(args):
            return None
        del args[col]
        out.append(source[i:m.end()] + ", ".join(a.strip() for a in args) + ")")
        i = j
    out.append(source[i:])
    return "".join(out)


def column_deletions(source: str) -> Iterator[Deletion]:
    """Yield (lineno, 'column', 'name.field', modified_source): one
    column dropped from a top-level relation, everywhere it appears. A
    drop that breaks the program reads as a change, so only a column no
    result depends on survives the report."""
    try:
        ix = Index(parse(source))
    except ParseError:
        return
    for name, decl in ix.decls[TOP].items():
        if name == "out" or len(decl.fields) < 2:
            continue
        for col, field in enumerate(decl.fields):
            mod = _drop_column(source, name, col)
            if mod is not None:
                yield (decl.line, "column", f"{name}.{field.name}", mod)


def deletion_report(stem: str) -> tuple[int, list[tuple[int, str, str]]] | None:
    """Structural deletions that change no pair's output or derived fill.

    A deletion that changes nothing removed structure the pairs never
    instantiate. Deletions from the Fit comp are judged by the fit check;
    the rest must hold the variant profile and, where the solver fits,
    the fit check too — body and Parse rules feed both. Informational —
    such a deletion points at an unwitnessed guard or rule, not a
    violation. None when the stored source itself fails.
    """
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    task = load_task(stem.split("_", 1)[0])
    examples = list(task.train) + list(task.test)
    reference = _profile(source, examples)
    if reference is None:
        return None

    def fit_ok(src: str) -> bool:
        r = fit_check(src, task)
        return r is not None and not r.error and not r.diff

    fits = fit_ok(source)
    dels = [("solve", d) for d in deletions(source)]
    dels += [("solve", d) for d in column_deletions(source)]
    if fits:
        dels += [("fit", d) for d in deletions(source, fit=True)]

    def test(tagged: tuple[str, Deletion]) -> tuple[int, str, str] | None:
        mode, (lineno, kind, text, mod) = tagged
        if mode == "solve":
            # The fit check is the expensive one, so it waits on the
            # profile, which most deletions already fail.
            if _profile(mod, examples) != reference:
                return None
            return (lineno, kind, text) if not fits or fit_ok(mod) else None
        return (lineno, f"fit {kind}", text) if fit_ok(mod) else None

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        unchanged = [r for r in executor.map(test, dels) if r]
    return (len(dels), sorted(unchanged))
