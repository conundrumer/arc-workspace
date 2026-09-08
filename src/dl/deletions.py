"""Delete structure from a solver and report what the pairs still accept."""

import re
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor

from arc.task import load as load_task
from dl.determine import determine_check
from dl.dlparse import TOP, Decl, Index, ParseError, TypeDecl, parse
from dl.facts import grid_to_facts, parse_output
from dl.lint import _lib_source
from dl.paths import SOLVERS_DIR
from dl.rewrite_lint import _elem_tables
from dl.solve import _profile, res_out
from dl.souffle import _pool_workers, _run_source
from dl.source import _comp_span, build_source

NEG_ATOM_RE = re.compile(r"(?<![=!])!(?!=)\s*[\w.]+\s*\(")
ATOM_RE = re.compile(r"(?<![\w.$])[\w.]+\s*\(")
ENUM_RE = re.compile(r"(\w+_elem)\s*\(\s*([A-Za-z]\w*)\s*\)")
UNGROUNDED_RE = re.compile(r"^Error: Ungrounded variable ", re.M)

# What can stand immediately before a body atom: a disjunction's open
# paren or a literal separator. Anything else — an operator, a `!`, an
# aggregate's brace — marks something that is not one.
ATOM_LEAD = ",;("

# Kinds a case column — a column typed as the solver's Choice ADT — reports
# under, apart from the plain 'column' every other relation column uses.
CASE_COLUMN = "case column"
UNPROBED_CASE = "unprobed case column"

# The kind a positive `*_elem` atom reports under when another positive
# atom of its rule carries its variable: the readable form of a
# per-member test, so its deletion makes no claim about the pairs.
BOUND_ENUMERATOR = "bound enumerator"

# The kind the solver's Choice type reports under when the pairs never
# part its cases and no case column stood in for the hypothesis.
UNEXERCISED_CASES = "unexercised cases"

type Deletion = tuple[int, str, str, str]  # lineno, kind, text, modified source
type Finding = tuple[int, str, str]  # lineno, kind, text


def _rule_spans(source: str, determine: bool = False) -> list[tuple[int, int]]:
    """Inclusive line spans of rules — the Determine comp's when `determine`,
    the rest otherwise.

    Style-parsed: head and `:-` share the first line; `.` ends the statement.
    """
    lines = source.splitlines()
    fs, fe = _comp_span(source, "Determine")
    determine_lines = set(range(fs - 1, fe + 1)) if (fs, fe) != (0, 0) else set()
    spans = []
    i = 0
    while i < len(lines):
        code = lines[i].split("//")[0]
        if ((i in determine_lines) != determine or ":-" not in code
                or code.lstrip().startswith(".")):
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


def _close_paren(code: str, start: int) -> int | None:
    """Index of the `)` matching the `(` at `start`, or None when the
    text runs out first."""
    depth, i = 0, start
    while i < len(code):
        if code[i] == "(":
            depth += 1
        elif code[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def _nesting(rule: str) -> list[tuple[int, int]]:
    """Per character, how many atom argument lists and how many aggregate
    braces enclose it. An open paren belongs to an atom when a name runs
    up to it; a disjunction's open paren follows a separator instead."""
    out: list[tuple[int, int]] = []
    stack: list[bool] = []
    braces = 0
    for i, ch in enumerate(rule):
        out.append((sum(stack), braces))
        if ch == "(":
            head = rule[:i].rstrip()
            stack.append(bool(head) and (head[-1].isalnum() or head[-1] in "_."))
        elif ch == ")" and stack:
            stack.pop()
        elif ch == "{":
            braces += 1
        elif ch == "}" and braces:
            braces -= 1
    return out


def _positive_atoms(rule: str) -> Iterator[tuple[int, int]]:
    """Spans of the rule's positive top-level body atoms.

    An atom is one only where a separator leaves off, so the head, a
    negated atom, the right side of a comparison and a functor call are
    all passed over. An ADT constructor and a nested functor sit inside
    an argument list, and an aggregate's atoms sit inside braces; neither
    is top level. Atoms in a disjunction's branches are, since a
    disjunction's parens are not an argument list.
    """
    sep = rule.find(":-")
    if sep < 0:
        return
    body = sep + 2
    nesting = _nesting(rule)
    for m in ATOM_RE.finditer(rule, body):
        before = rule[body:m.start()].rstrip()
        if before and before[-1] not in ATOM_LEAD:
            continue
        if nesting[m.start()] != (0, 0):
            continue
        end = _close_paren(rule, m.end() - 1)
        if end is not None:
            yield (m.start(), end + 1)


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


def deletions(source: str, determine: bool = False) -> Iterator[Deletion]:
    """Yield (lineno, kind, text, modified_source) structural deletions.

    Kinds: 'rule' deletes the whole rule; 'negation' deletes one negated
    body atom; 'atom' deletes one positive body atom; 'disjunct' deletes
    one branch of a disjunction (either way the modified rule collapses
    to one line). With `determine`, the deletions come from the Determine
    comp's rules; otherwise from the rest.

    A positive atom over a lib `*_elem` relation whose one variable
    another positive atom of the rule carries deletes under
    BOUND_ENUMERATOR instead of 'atom'. The other atom binds the
    variable, so the enumerator is the readable form of a per-member
    test, and its deletion changing nothing says nothing about the
    pairs.

    A deletion with no syntactic form — a negation that is the whole of
    a disjunct, say — is skipped rather than yielded malformed.

    An atom deletion can leave a variable with nothing to bind it. The
    run then fails, so the deletion reads as a change; nothing is done to
    detect the case ahead of time.
    """
    strict = _parses(source)
    for item in _variants(source, determine):
        if not strict or _parses(item[3]):
            yield item


def _bound_enumerator(
    rule: str, span: tuple[int, int], spans: list[tuple[int, int]],
    elems: frozenset[str],
) -> bool:
    """True when the atom at `span` is `x_elem(V)` over a lib elem
    relation and another of the rule's positive atoms carries `V`."""
    m = ENUM_RE.fullmatch(rule[span[0]:span[1]])
    if m is None or m.group(1) not in elems:
        return False
    var = re.compile(rf"(?<![\w.$]){re.escape(m.group(2))}(?!\w)")
    return any(var.search(rule[s:e]) for s, e in spans if (s, e) != span)


def _variants(source: str, determine: bool) -> Iterator[Deletion]:
    lines = source.splitlines()
    elems = frozenset(_elem_tables(_lib_source())[0])
    for a, b in _rule_spans(source, determine):
        rule = " ".join(ln.split("//")[0].strip() for ln in lines[a:b + 1])
        head = rule.split(":-")[0].strip()
        yield (a + 1, "rule", head, "\n".join(lines[:a] + lines[b + 1:]) + "\n")
        for m in NEG_ATOM_RE.finditer(rule):
            k = _close_paren(rule, m.end() - 1)
            k = len(rule) if k is None else k
            atom = rule[m.start():k + 1]
            modified = lines[:a] + [_drop_atom(rule, m.start(), k + 1)] + lines[b + 1:]
            yield (a + 1, "negation", atom, "\n".join(modified) + "\n")
        spans = list(_positive_atoms(rule))
        for s, e in spans:
            kind = "atom"
            if _bound_enumerator(rule, (s, e), spans, elems):
                kind = BOUND_ENUMERATOR
            modified = lines[:a] + [_drop_atom(rule, s, e)] + lines[b + 1:]
            yield (a + 1, kind, rule[s:e], "\n".join(modified) + "\n")
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


def _case_decl(source: str) -> TypeDecl | None:
    """The `.type` of `out`'s trailing column, when the file declares it
    as an ADT of two or more branches. Its values name the cases, and
    the output check separates them pair by pair."""
    try:
        program = parse(source)
    except ParseError:
        return None
    adts = {
        it.name: it for it in program.items
        if isinstance(it, TypeDecl) and len(it.branches) >= 2
    }
    for it in program.items:
        if isinstance(it, Decl) and it.name == "out" and it.fields:
            return adts.get(it.fields[-1].type)
    return None


def case_type(source: str) -> str | None:
    """The name of the solver's case type, when it has one."""
    decl = _case_decl(source)
    return None if decl is None else decl.name


def column_deletions(source: str) -> Iterator[Deletion]:
    """Yield (lineno, kind, 'name.field', modified_source): one column
    dropped from a top-level relation, everywhere it appears. A drop
    that breaks the program reads as a change, so only a column no
    result depends on survives the report.

    A column typed as the solver's Choice ADT reports under a kind of its
    own: such a column stands for the coverage hypothesis, so its deletion
    needs a reading of its own.
    """
    try:
        ix = Index(parse(source))
    except ParseError:
        return
    case = case_type(source)
    for name, decl in ix.decls[TOP].items():
        if name == "out" or len(decl.fields) < 2:
            continue
        for col, field in enumerate(decl.fields):
            mod = _drop_column(source, name, col)
            if mod is not None:
                kind = CASE_COLUMN if case and field.type == case else "column"
                yield (decl.line, kind, f"{name}.{field.name}", mod)


def _ungrounds(source: str, example) -> bool:
    """True when Souffle rejects this source for an ungrounded variable.

    Dropping a case column can leave the case variable with nothing to
    bind it. The run then fails for every solver alike, so the probe
    reports a change it did not measure.
    """
    try:
        _run_source(build_source(source), grid_to_facts(example.input))
    except RuntimeError as err:
        return UNGROUNDED_RE.search(str(err)) is not None
    except Exception:
        return False
    return False


def _cases_agree(source: str, examples: list, reference: list) -> bool:
    """True when the pairs never separate the cases: every pair emits
    two or more variants, all of them the same grid.

    The reference profile already holds every variant to an accepted
    grid, so on a pair that accepts one grid the variants agree by
    construction, and the profile's variant names settle it. A tiebreak
    pair accepts two grids, and a resolution solver profiles grids
    rather than names, so those read the run again.
    """
    plain = all(ex.alt is None or ex.alt.kind != "tiebreak" for ex in examples)
    if plain and not res_out(source):
        return all(len(names) >= 2 for names in reference)
    for ex in examples:
        try:
            actuals = parse_output(
                _run_source(build_source(source), grid_to_facts(ex.input))
            )
        except Exception:
            return False
        if len({variant for variant, _, _, _ in actuals}) < 2:
            return False
        if len({tuple(map(tuple, grid)) for _, grid, _, _ in actuals}) != 1:
            return False
    return True


def _case_findings(
    source: str, findings: list[Finding], agree: Callable[[], bool]
) -> list[Finding]:
    """The findings with the coverage hypothesis settled by the pairs.

    `agree` says whether the pairs never part the cases; it runs only
    when the answer decides something. Where a case column fired, the
    pairs decide its reading: when some pair parts the cases, a no-op
    drop reads as any other column's does, and an unprobed drop raises
    nothing at all. Where none fired but the solver has cases and the
    pairs never part them, the hypothesis goes unexercised all the same, so
    the case type reports it under UNEXERCISED_CASES.
    """
    cases = (CASE_COLUMN, UNPROBED_CASE)
    if any(k in cases for _, k, _ in findings):
        if agree():
            return findings
        return [
            (lineno, "column" if kind == CASE_COLUMN else kind, text)
            for lineno, kind, text in findings
            if kind != UNPROBED_CASE
        ]
    hypothesis = _case_decl(source)
    if hypothesis is not None and agree():
        return [*findings, (hypothesis.line, UNEXERCISED_CASES, hypothesis.name)]
    return findings


def deletion_report(stem: str) -> tuple[int, list[Finding]] | None:
    """Structural deletions that change no pair's output or derived value.

    A deletion that changes nothing removed structure the pairs never
    instantiate. Deletions from the Determine comp are judged by the
    determination check; the rest must hold the variant profile and, where
    the determination holds, the determination check too — program and Parse
    rules feed both. Informational —
    such a deletion points at an unwitnessed guard or rule, not a
    violation. A case column reports under its own kinds, since the
    pairs decide what its deletion can show, and a solver whose pairs
    never part its cases reports that once, whether or not a case column
    stood for it. None when the stored source itself fails.
    """
    source = (SOLVERS_DIR / f"{stem}.dl").read_text()
    task = load_task(stem.split("_", 1)[0])
    examples = list(task.train) + list(task.test)
    reference = _profile(source, examples)
    if reference is None:
        return None

    def determine_ok(src: str) -> bool:
        r = determine_check(src, task)
        return r is not None and not r.error and not r.diff

    determines = determine_ok(source)
    dels = [("solve", d) for d in deletions(source)]
    dels += [("solve", d) for d in column_deletions(source)]
    if determines:
        dels += [("determine", d) for d in deletions(source, determine=True)]

    def test(tagged: tuple[str, Deletion]) -> tuple[int, str, str] | None:
        mode, (lineno, kind, text, mod) = tagged
        if mode == "solve":
            # The determination check is the expensive one, so it waits on the
            # profile, which most deletions already fail.
            if _profile(mod, examples) != reference:
                if kind == CASE_COLUMN and _ungrounds(mod, examples[0]):
                    return (lineno, UNPROBED_CASE, text)
                return None
            return ((lineno, kind, text)
                    if not determines or determine_ok(mod) else None)
        return ((lineno, f"determination {kind}", text)
                if determine_ok(mod) else None)

    with ThreadPoolExecutor(max_workers=_pool_workers()) as executor:
        findings = [r for r in executor.map(test, dels) if r]
    findings = _case_findings(
        source, findings, lambda: _cases_agree(source, examples, reference)
    )
    return (len(dels), sorted(findings))


NOOP_NOTE = [
    "  note: each removed structure the pairs never instantiate — an unwitnessed",
    "        guard, rule, or column. This is coverage, not a defect to fix.",
]

ENUMERATOR_NOTE = [
    "  note: an enumerator over a variable another atom binds: the readable",
    "        form of a per-member test, not a claim. Dropping it changes",
    "        nothing, and that says nothing about the pairs.",
]

CASE_NOTE = [
    "  note: the cases agree on every pair, so dropping the case column",
    "        changes nothing. The column carries the coverage hypothesis",
    "        and the pairs do not exercise it. This is not dead code.",
]

UNPROBED_NOTE = [
    "  note: dropping the case column ungrounds a variable, so the probe",
    "        result says nothing about the cases. The pairs emit one and the",
    "        same grid for every case, so this column carries a coverage",
    "        hypothesis the pairs do not exercise.",
]

UNEXERCISED_NOTE = [
    "  note: the cases agree on every pair: the pairs emit one and the same",
    "        grid for every case, so they do not exercise the coverage",
    "        hypothesis. The review's constructed witness carries it. This is",
    "        not dead code.",
]


def render_deletions(stem: str, report: tuple[int, list[Finding]] | None) -> list[str]:
    """The deletion section of the audit, as printable lines."""
    if report is None:
        return ["baseline fails: stored source does not pass train+test"]
    total, findings = report

    def entries(group: list[Finding]) -> list[str]:
        return [f"  {stem}.dl:{n}: {kind} `{text}`" for n, kind, text in group]

    apart = (UNPROBED_CASE, UNEXERCISED_CASES)
    enumerators = [f for f in findings if f[1].endswith(BOUND_ENUMERATOR)]
    noop = [
        f for f in findings if f[1] not in apart and f not in enumerators
    ]
    unprobed = [f for f in findings if f[1] == UNPROBED_CASE]
    unexercised = [f for f in findings if f[1] == UNEXERCISED_CASES]
    lines = []
    if noop:
        lines.append(f"{len(noop)}/{total} deletions change nothing:")
        lines += NOOP_NOTE
        lines += entries(noop)
        if any(kind == CASE_COLUMN for _, kind, _ in noop):
            lines += CASE_NOTE
    elif not enumerators:
        lines.append(f"every deletion changes the result ({total} tested)")
    if enumerators:
        if lines:
            lines.append("")
        lines.append(
            f"{len(enumerators)}/{total} deletions remove an enumerator over a"
            " bound variable:"
        )
        lines += entries(enumerators)
        lines += ENUMERATOR_NOTE
    if unprobed:
        noun = "case column" if len(unprobed) == 1 else "case columns"
        lines.append("")
        lines.append(f"{len(unprobed)} {noun} the probe cannot judge:")
        lines += entries(unprobed)
        lines += UNPROBED_NOTE
    if unexercised:
        lines.append("")
        lines.append("the pairs do not exercise the coverage hypothesis:")
        lines += entries(unexercised)
        lines += UNEXERCISED_NOTE
    return lines
