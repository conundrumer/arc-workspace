"""Delete structure from a solver and report what the pairs still accept."""

import os
import re
from collections.abc import Callable, Iterator
from concurrent.futures import ProcessPoolExecutor

import controlled_markdown as nm
from arc.task import load as load_task
from dl.determine import determine_check
from dl.dlparse import TOP, Decl, Index, ParseError, TypeDecl, parse
from dl.facts import grid_to_facts, parse_output
from dl.lint import _lib_source
from dl.paths import REPO_ROOT
from dl.rewrite_lint import _elem_tables, _lib_scopes
from dl.solve import _profile, res_out, solver_file, solver_name
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

# The kind a deletion reports under when the modified file ungrounds a
# variable: Souffle rejects it, so the run measured nothing.
UNGROUNDED_DELETION = "ungrounded deletion"

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
    pairs. Where the binding column is wider than the elem relation's
    type, the atom narrows the binding and deletes under 'atom'.

    A deletion with no syntactic form — a negation that is the whole of
    a disjunct, say — is skipped rather than yielded malformed.

    An atom deletion can leave a variable with nothing to bind it.
    Nothing detects that ahead of time; the run fails, and the report
    reads the failure off Souffle's error.
    """
    strict = _parses(source)
    for item in _variants(source, determine):
        if not strict or _parses(item[3]):
            yield item


def _column_type(atom: str, var: re.Pattern, lib: dict[str, Decl]) -> str | None:
    """The declared type of the column where `atom` carries `var`, read
    off the lib declaration of the atom's relation. None where the lib
    declares no such relation, and where the column runs past the
    declaration's fields."""
    m = ATOM_RE.match(atom)
    decl = lib.get(atom[:m.end() - 1].strip()) if m else None
    if m is None or decl is None or not atom.endswith(")"):
        return None
    for i, arg in enumerate(_split_top_args(atom[m.end():-1])):
        if var.search(arg):
            return decl.fields[i].type if i < len(decl.fields) else None
    return None


def _bound_enumerator(
    rule: str, span: tuple[int, int], spans: list[tuple[int, int]],
    wider: dict[str, set[str]], lib: dict[str, Decl],
) -> bool:
    """True when the atom at `span` is `x_elem(V)` over a lib elem
    relation and another of the rule's positive atoms carries `V`.

    A binding column of a type wider than the elem relation's own — a
    `dir_elem(D)` over `neighbor`'s Dir8 column — is not that: there the
    atom narrows the binding, which is a claim about the pairs.
    """
    m = ENUM_RE.fullmatch(rule[span[0]:span[1]])
    if m is None or m.group(1) not in wider:
        return False
    var = re.compile(rf"(?<![\w.$]){re.escape(m.group(2))}(?!\w)")
    bound = False
    for s, e in spans:
        if (s, e) == span or not var.search(rule[s:e]):
            continue
        if _column_type(rule[s:e], var, lib) in wider[m.group(1)]:
            return False
        bound = True
    return bound


def _in_head(atom: str, head: str) -> str:
    """The finding text for a body deletion: the atom, then the head of
    the rule it came from. The renderer quotes the text it is given, so
    the two read as separate quoted fragments."""
    return f"{atom}` in `{head}"


def _variants(source: str, determine: bool) -> Iterator[Deletion]:
    lines = source.splitlines()
    elem_type, wider_of = _elem_tables(_lib_source())
    # Per elem relation, the types a binding column may not carry.
    wider = {name: wider_of.get(t, set()) for name, t in elem_type.items()}
    lib = _lib_scopes(_lib_source())[0]
    for a, b in _rule_spans(source, determine):
        rule = " ".join(ln.split("//")[0].strip() for ln in lines[a:b + 1])
        head = rule.split(":-")[0].strip()
        yield (a + 1, "rule", head, "\n".join(lines[:a] + lines[b + 1:]) + "\n")
        for m in NEG_ATOM_RE.finditer(rule):
            k = _close_paren(rule, m.end() - 1)
            k = len(rule) if k is None else k
            atom = rule[m.start():k + 1]
            modified = lines[:a] + [_drop_atom(rule, m.start(), k + 1)] + lines[b + 1:]
            yield (a + 1, "negation", _in_head(atom, head),
                   "\n".join(modified) + "\n")
        spans = list(_positive_atoms(rule))
        for s, e in spans:
            kind = "atom"
            if _bound_enumerator(rule, (s, e), spans, wider, lib):
                kind = BOUND_ENUMERATOR
            modified = lines[:a] + [_drop_atom(rule, s, e)] + lines[b + 1:]
            yield (a + 1, kind, _in_head(rule[s:e], head),
                   "\n".join(modified) + "\n")
        for _, _, spans in _disjunctions(rule):
            for k, (s, e) in enumerate(spans):
                if k + 1 < len(spans):
                    cut = (s, spans[k + 1][0])  # branch plus trailing ';'
                else:
                    cut = (spans[k - 1][1], e)  # leading ';' plus branch
                shrunk = rule[:cut[0]] + rule[cut[1]:]
                modified = lines[:a] + [shrunk] + lines[b + 1:]
                yield (a + 1, "disjunct", _in_head(rule[s:e].strip(), head),
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

    Dropping a column or an atom can leave a variable with nothing to
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
    construction, and the profile's variant names settle it. A pair with
    a tiebreak or a rule alt accepts two grids, and a resolution solver
    profiles grids rather than names, so those read the run again.
    """
    plain = all(
        ex.alt is None or ex.alt.kind not in ("tiebreak", "rule")
        for ex in examples
    )
    if plain and not res_out(source):
        return all(len(names) >= 2 for names in reference)
    for ex in examples:
        try:
            actuals = parse_output(
                _run_source(build_source(source), grid_to_facts(ex.input))
            )
        except Exception:
            return False
        if len({c.case for c in actuals}) < 2:
            return False
        if len({tuple(map(tuple, c.grid)) for c in actuals}) != 1:
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


def _determines(src: str, task) -> bool:
    r = determine_check(src, task)
    return r is not None and not r.error and not r.diff


# What every deletion's test reads, set once in each worker process:
# the task, its pairs, the reference profile, and whether the stored
# source determines.
_judge: dict = {}


def _judge_init(task, reference: list, determines: bool) -> None:
    _judge.update(task=task, examples=list(task.train) + list(task.test),
                  reference=reference, determines=determines)


def _judge_deletion(tagged: tuple[str, Deletion]) -> Finding | None:
    """The finding one deletion raises, or None when it changes a pair."""
    task, examples = _judge["task"], _judge["examples"]
    determines = _judge["determines"]
    mode, (lineno, kind, text, mod) = tagged
    if mode == "solve":
        # The determination check is the expensive one, so it waits on the
        # profile, which most deletions already fail.
        profile = _profile(mod, examples, _judge["reference"])
        if profile != _judge["reference"]:
            # A None profile is a failing pair, and a file Souffle
            # rejects fails every pair; a profile that differs measured
            # the pairs.
            if profile is None and _ungrounds(mod, examples[0]):
                return (lineno,
                        UNPROBED_CASE if kind == CASE_COLUMN
                        else UNGROUNDED_DELETION, text)
            return None
        return ((lineno, kind, text)
                if not determines or _determines(mod, task) else None)
    return ((lineno, f"determination {kind}", text)
            if _determines(mod, task) else None)


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
    stood for it. A deletion whose run fails for an ungrounded variable
    reports under a kind of its own, since that run measured nothing.
    None when the stored source itself fails.

    The deletions are judged in worker processes: on a warm cache the
    judging is Python work, which threads would run one at a time.
    """
    path, task_id = solver_file(stem)
    source = path.read_text()
    task = load_task(task_id)
    examples = list(task.train) + list(task.test)
    reference = _profile(source, examples)
    if reference is None:
        return None

    determines = _determines(source, task)
    # The Determine comp's deletions go first: each runs the determination
    # check, which takes longest, so the pool starts them before the rest.
    dels = ([("determine", d) for d in deletions(source, determine=True)]
            if determines else [])
    dels += [("solve", d) for d in deletions(source)]
    dels += [("solve", d) for d in column_deletions(source)]

    workers = _pool_workers() or os.cpu_count() or 1
    with ProcessPoolExecutor(
        max_workers=workers, initializer=_judge_init,
        initargs=(task, reference, determines),
    ) as executor:
        findings = [r for r in executor.map(_judge_deletion, dels) if r]
    findings = _case_findings(
        source, findings, lambda: _cases_agree(source, examples, reference)
    )
    return (len(dels), sorted(findings))


# The report's prose. Each group is a section of this document, holding the
# header statement and the note under it; the code renders the section with
# its counts and appends the finding rows.
REPORT_DOC = REPO_ROOT / "prompts" / "run_dl.md"


def _section(name: str, pad: str = "", **values) -> list[str]:
    """One section of the report document as printable lines, each under
    `pad`."""
    registry = nm.Registry(REPO_ROOT)
    document = registry.load(REPORT_DOC)
    body = nm.Node(nm.DOCUMENT, source=document.source)
    body.children = list(registry.ids[document.source][name].children)
    text = nm.render(body, registry, values).strip()
    return [pad + line for line in text.split("\n")]


ROW = " " * 4   # the findings and the note sit one level under the header


def render_deletions(stem: str, report: tuple[int, list[Finding]] | None) -> list[str]:
    """The deletion section of the audit, as printable lines: a nested list,
    each group's note and findings under its header statement."""
    if report is None:
        return _section("baseline-fails")
    total, findings = report
    name = solver_name(stem)

    def entries(group: list[Finding]) -> list[str]:
        return [f"{ROW}- {name}:{n}: {kind} `{text}`" for n, kind, text in group]

    apart = (UNPROBED_CASE, UNGROUNDED_DELETION, UNEXERCISED_CASES)
    enumerators = [f for f in findings if f[1].endswith(BOUND_ENUMERATOR)]
    noop = [
        f for f in findings if f[1] not in apart and f not in enumerators
    ]
    unprobed = [f for f in findings if f[1] == UNPROBED_CASE]
    ungrounded = [f for f in findings if f[1] == UNGROUNDED_DELETION]
    unexercised = [f for f in findings if f[1] == UNEXERCISED_CASES]
    # The deletions the probe judged: an ungrounding one is not among them, so
    # every ratio below counts against this and not against the raw total.
    judged = total - len(ungrounded)
    lines = []
    if noop:
        lines += _section("noop", count=len(noop), judged=judged)
        if any(kind == CASE_COLUMN for _, kind, _ in noop):
            lines += _section("case", pad=ROW)
        lines += entries(noop)
    elif not enumerators:
        lines += _section("none", judged=judged)
    if enumerators:
        if lines:
            lines.append("")
        lines += _section("enumerator", count=len(enumerators), judged=judged)
        lines += entries(enumerators)
    if unprobed:
        lines.append("")
        lines += _section(
            "unprobed", count=len(unprobed),
            noun="case column" if len(unprobed) == 1 else "case columns")
        lines += entries(unprobed)
    if ungrounded:
        lines.append("")
        lines += _section(
            "ungrounded", count=len(ungrounded),
            noun="deletion" if len(ungrounded) == 1 else "deletions")
    if unexercised:
        lines.append("")
        lines += _section("unexercised")
        lines += entries(unexercised)
    return lines
