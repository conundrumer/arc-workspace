"""Q6 Keys for the mutants that survive the hard rules: link atoms, an output near-filter, a narrowed unread-box key
and two comparison keys.

Each key is a count (form keys) or a 0 or 1 (table keys), and None where the test does not apply. A feature reads only
the train inputs and outputs, the available tables, X, the candidate's form, the clauses before the point and the
library interfaces. The link-atom keys also read the counts of label uses in the gold RULE clauses of other tasks
(see "Link counts"); a key at a task never uses that task's gold.

Class (when the rule can decide):
    SP: static, decided on a prefix; the atom or binder that completes the violation is placed and no extension repairs it.
    SC: static, on completion; an obligation that a later atom can still meet.
    DA: data-dependent, anti-monotone: removed rows and added atoms keep the violation.
    DC: data-dependent, on completion; it needs the whole of X.
Soundness (a rule is sound if it never rejects a valid clause):
    S: the violation contradicts the train output, or a library law makes the clause unsatisfiable.
    R: the library makes the atom valid, constant or an alias, or gives an equal clause in a canonical spelling.
    H: the rule rests on what gold writes. Every key here is H; the held-out run counts the gold clauses that fire.

Keys:
    q6a_link_atoms: `link_strict` and `link_loose`, the uses of a label that lack a link atom that gold nearly always
        has (share 0.98 and 0.90 of the uses in other tasks). Rule points only.
        Class SC, soundness H. Needs: form, finished. Monotone: no (a later atom can be the link).
    q6b_link_specific: the static form of the link rules that carry most of q6a, with no counts. Rule points only.
        `relative_base_no_inside`: `relative` Base site, label made by a `port box` B column, no positive `inside` that
        reads the label at B.
        `relative_x_input_no_test`: `relative` X site, label made by `input.P`, no atom that tests the label.
        `same_dist_box_no_inside`: a `same_dist` site (P1 or P2), label made by a `port box` B column, no positive
        `inside` that reads the label at B.
        `dir8_opposite_axis4_no_ray`: a `dir8_opposite` site (D or D2), label made by `axis4_of.D`, no positive
        `port ray` atom that reads the label at D.
        `ray_p_input_no_test`: a `port ray` P site, label made by `input.P`, no atom that tests the label.
        Class SC, soundness H. Needs: form, finished. Monotone: no.
    q6c_unread_box: `unread_box_B_nodet` is `q3d_box_measures.unread_box_B` (a label that a `port box` B column makes and
        no site reads), None at a Det point, where an unread label is still an output column.
        Class SC, soundness H. Needs: form, finished. Monotone: no (a later atom can read the label).
    q6d_output_near: `differs_inexact`, where `OUT` reads the candidate's relation (A1: `p.out_reads` is True):
        `final_vs_output.differs` is 1 and `k3_color_counts.exact` is below 1. None elsewhere, and where X has
        no Position (or Box) and Color column or no rows.
        Class DC, soundness H (an output clause that builds a smaller grid with `apply` or `compose` has rows beyond
        the color counts). Needs: full X. Monotone: no.
    q6e_ne_top: `ne_numbers_top`, the `!=` atoms outside NOT, OR, IF and ALL whose two operands are labels of type
        Number, Nat or Int that a site makes.
        Class SP, soundness H. Needs: form. Monotone: yes.
    q6f_idle_nonstrict: `idle_nonstrict`, the `<=` and `>=` atoms at the top level of the body (outside NOT, OR, IF and
        ALL) between two labels that are Number columns of X and are made at the top level, where X has a row and no
        row has the two columns equal, in any assignment, example or model. The atom allows a tie that X never shows.
        The top-level conditions keep both labels columns of X when atoms are added (a label that an OR branch makes
        is a column only if every later branch names it).
        Class DA for added conjuncts and removed rows (a conjunct removes rows and cannot create a tie); a branch added
        to an OR of the prefix adds rows and can create one, so a sampler that adds branches treats the key as DC.
        Soundness H. Needs: full X. Monotone: yes (for added conjuncts).

Label uses. A label has one binder: the one site that makes it (`*L`), unless that site stands in an OR branch and
the label is read outside that branch (the star of a label that a branch makes and the other branches name moves to the
first branch when the branches are reordered, so that binder has no canonical spelling; such a label has no binder
here). A site is named `(relation, column)`: a port `&inst.port` is `port:<port>`, a declared table is `declared`
with no column, a comparison is its operator with `>` read as `<` and `>=` as `<=`, and the two columns of a symmetric
lib relation (`featlib.SYMMETRIC`) are one column `P1|P2`. A use of a label is a site that reads it. Its key K is
(site, below NOT, binder). Its companions are the sites (each with its NOT) of the other atoms that read the label,
and `FILTER` where one of those atoms is a test: it is below NOT or makes no label.

Link counts. For each K, over the distinct gold RULE clauses of the other tasks: the uses, the tasks that have them,
and per companion the uses that have it. K requires a companion c when there are at least MIN_USES uses in at least
MIN_TASKS other tasks and a share `thr` or more of the uses have c. A use whose K requires a companion that it lacks
is counted by the key. The counts are in `study/q6_counts/link_counts.json`, built from the gold programs
(`fstore/points/*/gold.arclog`) and nothing else by `study/q6_counts/build.py` (see its docstring for the command).
After a rebuild, raise COUNTS_BUILD below to the file's `build`: the fit's cache keys this module's values on this
file and not on the counts file.
"""
import collections as C
import functools
import importlib.util
import json
from pathlib import Path

from featlib import FEATURES, SYMMETRIC, feature

# Raise COUNTS_BUILD with the `build` of a rebuilt counts file: the fit's cache keys this module's values on this file.
COUNTS_BUILD = 1
COUNTS = Path(__file__).resolve().parents[1] / 'q6_counts' / 'link_counts.json'
MIN_USES, MIN_TASKS = 10, 4
STRICT, LOOSE = 0.98, 0.90
FILTER = 'FILTER'
NUMBERS = ('Number', 'Nat', 'Int')
CMP_SIDE = {'>': '<', '>=': '<='}


def _sibling(name):
    """A private copy of the feature module `name` next to this file, to reuse its helpers; its features are not registered."""
    saved = dict(FEATURES)
    spec = importlib.util.spec_from_file_location('_q6_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        FEATURES.clear()
        FEATURES.update(saved)
    return module


q2 = _sibling('q2_table_tests')
q3 = _sibling('q3_form_filters')
r9k = _sibling('r9k')

_body = q3._body


# ------------------------------------------------------------------------------------------------ label uses

def site_of(arg):
    """(relation, column) of a site, in the spelling the link counts use."""
    atom = arg.atom
    if atom.operator:
        return CMP_SIDE.get(atom.operator, atom.operator), ''
    r = atom.relation
    if r.startswith('&'):
        if '.' in r:
            return 'port:' + r.rsplit('.', 1)[1], arg.column
        return 'declared', ''
    sym = SYMMETRIC.get(r)
    if sym and arg.column in sym:
        return r, '|'.join(sorted(sym))
    return r, arg.column


def _stable(arg):
    """Whether the star of a binder stays at its atom when the branches of an OR are reordered: the binder is outside
    every OR branch, or the label is read only inside the binder's own branch. (A label that a branch makes and the
    other branches name moves its star to the first branch.)"""
    branch = arg.atom.branch
    return not branch or all(o.atom.branch[:len(branch)] == branch for o in arg.variable.occurrences if o.atom is not None)


def binder_arg(var):
    """The one site that makes the label, or None where it has none, two, or one whose star moves with the order of
    OR branches."""
    bs = [b for b in var.binders if b.atom is not None and not b.key]
    return bs[0] if len(bs) == 1 and _stable(bs[0]) else None


def binder_of(var):
    """The (relation, column) of the label's binder, or None."""
    b = binder_arg(var)
    return None if b is None else site_of(b)


def is_test(atom):
    """An atom that tests labels made elsewhere: below NOT, or making no label (a star that moves with the order of OR
    branches does not make one)."""
    return bool(atom.negated or not any(x.binds and not x.key and x.variable is not None and _stable(x)
                                        for x in atom.arguments))


def uses(scope):
    """(K, companions, test, argument) for each use of a label that has a binder. K = (site, below NOT, binder);
    companions = {(site, below NOT)} of the other atoms that read the label; test: one of those atoms is a test."""
    for var in scope.variables.values():
        binder = binder_of(var)
        if binder is None:
            continue
        occ = [o for o in var.occurrences if o.atom is not None]
        for u in occ:
            if u.binds:
                continue
            comp, test = set(), False
            for o in occ:
                if o.atom is u.atom or o.binds:
                    continue
                comp.add((site_of(o), bool(o.atom.negated)))
                test = test or is_test(o.atom)
            yield (site_of(u), bool(u.atom.negated), binder), comp, test, u


def key_text(k):
    (rel, col), neg, (brel, bcol) = k
    return f'{rel}.{col}|{int(neg)}|{brel}.{bcol}'


def comp_text(c):
    (rel, col), neg = c
    return f'{rel}.{col}|{int(neg)}'


def use_record(k, comp, test):
    """(key text, companion texts) of a use, as the counts file stores them."""
    return key_text(k), sorted({comp_text(c) for c in comp} | ({FILTER} if test else set()))


# ------------------------------------------------------------------------------------------------ link counts

@functools.lru_cache(maxsize=1)
def _table():
    """{key text: (uses, {task: [uses, {companion text: uses}]}, {companion text: uses over all tasks})}."""
    if not COUNTS.exists():
        raise FileNotFoundError(f'{COUNTS} is missing: build it with q6_counts/build.py (see this module\'s docstring)')
    data = json.loads(COUNTS.read_text())
    if data.get('build') != COUNTS_BUILD:
        raise ValueError(f'{COUNTS} is build {data.get("build")}, this module expects {COUNTS_BUILD}')
    out = {}
    for k, by_task in data['keys'].items():
        total = C.Counter()
        for n, comps in by_task.values():
            total.update(comps)
        out[k] = (sum(n for n, _ in by_task.values()), by_task, total)
    return out


@functools.lru_cache(maxsize=None)
def required(key, task, thr):
    """{companion text: share of the uses} for the companions that K requires at share thr, from the other tasks' gold."""
    got = _table().get(key)
    if got is None:
        return {}
    n, by_task, total = got
    own = by_task.get(task)
    uses_n = n - (own[0] if own else 0)
    tasks = len(by_task) - (1 if own else 0)
    if uses_n < MIN_USES or tasks < MIN_TASKS:
        return {}
    out = {}
    for c, t in total.items():
        t -= own[1].get(c, 0) if own else 0
        if t / uses_n >= thr:
            out[c] = t / uses_n
    return out


def _missing(p, comp_texts, key, thr):
    return any(c not in comp_texts for c in required(key, p.task, thr))


def _rule_body(p):
    return _body(p) if p.kind == 'Rule' else None


@feature
def q6a_link_atoms(p):
    """Q6a Link atoms mined from the gold of other tasks. `link_strict` and `link_loose`: uses of a label whose K
    requires a companion (thr 0.98 and 0.90 over the other tasks' gold RULE clauses) that the use lacks. Everything
    that fires strict fires loose. A symbolic summary of what gold always writes next to a label's consumer: a deleted
    `inside (:A P) (:B B)` leaves the box generator joined to the cell only through `relative` or `same_dist`.
    None outside Rule points.

    Class SC, soundness H. Needs: form, finished. Monotone: no.
    """
    body = _rule_body(p)
    if body is None:
        return None
    strict = loose = 0
    for k, comp, test, _ in uses(body):
        text, got = use_record(k, comp, test)
        have = set(got)
        strict += _missing(p, have, text, STRICT)
        loose += _missing(p, have, text, LOOSE)
    return {'link_strict': strict, 'link_loose': loose}


# ------------------------------------------------------------------------------------------------ the specific links

BOX_PORT = ('port:box', 'B')


def _inside_b(comp):
    return (('inside', 'B'), False) in comp


def _ray_d(comp):
    return (('port:ray', 'D'), False) in comp


# key -> (site of the use, binder, test on the companions that says the link is missing)
SPECIFIC = {
    'relative_base_no_inside': (('relative', 'Base'), BOX_PORT, lambda comp, test: not _inside_b(comp)),
    'relative_x_input_no_test': (('relative', 'X'), ('input', 'P'), lambda comp, test: not test),
    'same_dist_box_no_inside': (('same_dist', 'P1|P2'), BOX_PORT, lambda comp, test: not _inside_b(comp)),
    'dir8_opposite_axis4_no_ray': (('dir8_opposite', 'D|D2'), ('axis4_of', 'D'), lambda comp, test: not _ray_d(comp)),
    'ray_p_input_no_test': (('port:ray', 'P'), ('input', 'P'), lambda comp, test: not test),
}


def _specific(body, name, linked=False):
    """The uses of the specific key `name`: those at its site and binder, below no NOT, and (unless linked) the ones
    whose companions lack the link."""
    site, binder, missing = SPECIFIC[name]
    n = 0
    for (s, neg, b), comp, test, _ in uses(body):
        if s == site and b == binder and not neg and (linked or missing(comp, test)):
            n += 1
    return n


@feature
def q6b_link_specific(p):
    """Q6b The link atoms that the strict level of q6a rests on, as static rules with no counts. Each key counts the
    uses at one site whose label has one binder and lacks one link (see the module docstring for each). None outside
    Rule points.

    Class SC, soundness H. Needs: form, finished. Monotone: no.
    """
    body = _rule_body(p)
    if body is None:
        return None
    return {name: _specific(body, name) for name in SPECIFIC}


# ------------------------------------------------------------------------------------------------ unread box label

@feature
def q6c_unread_box(p):
    """Q6c `unread_box_B_nodet`: `q3d_box_measures.unread_box_B` (labels that a `port box` B column makes and no site
    reads), None at a Det point. The Det point where gold fires has the unread label as an output column. None where
    q3d is None (no body, an INIT key clause).

    Class SC, soundness H. Needs: form, finished. Monotone: no.
    """
    if p.kind == 'Det':
        return None
    got = q3.q3d_box_measures(p)
    if got is None or got.get('unread_box_B') is None:
        return None
    return {'unread_box_B_nodet': got['unread_box_B']}


# ------------------------------------------------------------------------------------------------ output clause

@feature
def q6d_output_near(p):
    """Q6d `differs_inexact`: 1 where X, with `OUT` reading the candidate's relation (A1), paints a position another color
    or leaves a position without a row (`final_vs_output.differs`) and its rows per color differ from the output's counts
    in some example (`k3_color_counts.exact` below 1); else 0. Each of the two holds for every pick of columns that `OUT`
    can make (`k3_color_counts` takes the Color column with the fewest misses, so its `exact` is below 1 only if every
    Color column's is). None elsewhere, and where X has no Position (or Box) and Color
    column, or no rows.

    Class DC, soundness H. Needs: full X. Monotone: no.
    """
    if not p.out_reads:
        return None
    fo = q2.final_vs_output(p)
    k3 = r9k.k3_color_counts(p)
    differs = fo.get('differs') if fo else None
    exact = k3.get('exact') if k3 else None
    if differs is None or exact is None:
        return None
    return {'differs_inexact': int(differs > 0 and exact < 1)}


# ------------------------------------------------------------------------------------------------ comparisons

def _top(atom):
    """An atom outside NOT, OR, IF and ALL."""
    return not atom.negated and not atom.branch and atom.quantifier is None and atom.conditional is None


def _number_label(arg):
    """Whether the operand is a label that some site makes and whose type is Number, Nat or Int."""
    v = arg.variable if arg is not None and arg.joins else None
    return v is not None and bool(v.binders) and v.resolved_type in NUMBERS


@feature
def q6e_ne_top(p):
    """Q6e `ne_numbers_top`: `!=` atoms at the top level of the clause (not below NOT, in an OR branch, IF or ALL)
    between two labels of type Number, Nat or Int that a site makes. Gold writes a Number `!=` as the second branch of an OR that has the
    two operands as one label in the first. None without a body.

    Class SP, soundness H. Needs: form. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    return {'ne_numbers_top': sum(1 for a in body.comparisons if a.operator == '!=' and _top(a) and
                                  _number_label(a.first) and _number_label(a.second))}


def _top_label(arg):
    """Whether the operand is a label made at the top level of the body."""
    b = binder_arg(arg.variable) if arg is not None and arg.joins and arg.variable is not None else None
    return b is not None and _top(b.atom)


@feature
def q6f_idle_nonstrict(p):
    """Q6f `idle_nonstrict`: `<=` or `>=` atoms at the top level of the body between two labels that are made at the top
    level and are Number columns of X, where X has a row and no row of X has the two columns equal (in any assignment,
    example or model). None without a body or rows, and at a point whose X has no such pair of columns.

    Class DA (for added conjuncts), soundness H. Needs: full X. Monotone: yes.
    """
    body = _body(p)
    if body is None:
        return None
    cols = {v.label: name for name, v in p.clause.x_columns.items() if v is not None and v.scope is body}
    pairs = []
    for a in body.comparisons:
        if (a.operator in ('<=', '>=') and _top(a) and
                _top_label(a.first) and _top_label(a.second) and a.first.label in cols and a.second.label in cols):
            i, j = (p.x.column(cols[a.first.label]), p.x.column(cols[a.second.label]))
            if i is not None and j is not None and i.type == 'Number' and j.type == 'Number':
                pairs.append((i.index, j.index))
    if not pairs:
        return None
    rows = [r for e in p.x.all_entries for r in e['rows']]  # X's own rows, the test entries too
    if not rows:
        return None
    return {'idle_nonstrict': sum(1 for i, j in pairs
                                  if all(tuple(r[i].get('value') or ()) != tuple(r[j].get('value') or ()) for r in rows))}


# ------------------------------------------------------------------------------------------------ constructs
#
# The held-out run counts exposure for a form key as the distinct gold clauses that contain the construct the key
# tests. A construct is a function of a Pair (the gold view): True where the clause has the construct, False where it
# has not, None where the key does not apply to the clause. They are not features.

def _c_link(thr):
    def construct(p):
        body = _rule_body(p)
        if body is None:
            return None
        return any(required(key_text(k), p.task, thr) for k, _, _, _ in uses(body))
    return construct


def _c_specific(name):
    def construct(p):
        body = _rule_body(p)
        return None if body is None else _specific(body, name, linked=True) > 0
    return construct


def _c_unread_box(p):
    if p.kind == 'Det':
        return None
    body = _body(p)
    if body is None or body.name == 'key':
        return None
    return any(a.binds and q3._src(a) == 'port:box.B' for a in body.arguments)


def _c_ne(p):
    body = _body(p)
    return None if body is None else any(a.operator == '!=' and a.first is not None and a.second is not None and
                                         a.first.joins and a.second.joins for a in body.comparisons)


def _c_nonstrict(p):
    body = _body(p)
    return None if body is None else any(a.operator in ('<=', '>=') and a.first is not None and a.second is not None and
                                         a.first.joins and a.second.joins for a in body.comparisons)


def _c_zero_order(p):
    body = _body(p)
    return None if body is None else any(a.operator in ('<', '<=', '>', '>=') and a.first is not None and
                                         a.second is not None and a.first.is_zero != a.second.is_zero
                                         for a in body.comparisons)


EXPOSURE = {
    'q6a_link_atoms.link_strict': _c_link(STRICT),
    'q6a_link_atoms.link_loose': _c_link(LOOSE),
    'q6c_unread_box.unread_box_B_nodet': _c_unread_box,
    'q6e_ne_top.ne_numbers_top': _c_ne,
    'q6f_idle_nonstrict.idle_nonstrict': _c_nonstrict,
    'f4_zero_bound.le0': _c_zero_order,
}
EXPOSURE.update({f'q6b_link_specific.{name}': _c_specific(name) for name in SPECIFIC})
