"""atom_labels, mode_holds, atom_binds and atoms_bound, copied verbatim from model/study/sampler/sample2_col.py at commit cf777b9aee796cd55a295137c2bb2f355ac2245e
(blob of that commit). The pin d1c0f40e661d91f62a3c6ecf872febb5c885edfb has none of them: they came in commit 07a9f1b79. The sampler files are not edited and the pin's hash
stands. `mode_holds` asks the pinned engine. Added here: `mode_rounds` (d_depth), and the second tier of item 3 lives in features_dagc_orders.py."""
import functools

import arclog  # the pinned engine, on PYTHONPATH

OPS = {'=': 'cmp:Eq', '!=': 'cmp:Ne', '<': 'cmp:Lt', '<=': 'cmp:Le', '>': 'cmp:Gt', '>=': 'cmp:Ge'}  # sample.py of the pin


def atom_labels(x, marked=False):
    """The labels of an atom or of a list of atoms; with marked, those that a * or ^ marks somewhere in x."""
    if isinstance(x, str):
        name = x.lstrip('*^')
        return {name} if name[:1].isupper() and (not marked or name != x) else set()
    return set().union(*[atom_labels(y, marked) for y in (x[1:] if x and isinstance(x[0], str) else x)])

@functools.lru_cache(maxsize=None)
def mode_holds(rel, bound, unbound):
    """Whether an atom of a lib relation may stand where its sites at the columns bound are bound and those at the columns unbound aren't,
    by the engine's safety check, which alone knows a relation macro's modes."""
    atom = [(c, 'B%d' % j) for j, c in enumerate(sorted(bound))] + [(c, '*U%d' % j) for j, c in enumerate(sorted(unbound))]
    text = '(RULE &x %s (%s %s))\n(RULE &y (input (:P *P) (:Col *Col)))\n(OUT (&y ^P ^Col))' % (' '.join('(= *%s 0)' % x for _, x in atom if x[0] == 'B'), rel, ' '.join('(:%s %s)' % x for x in atom))
    try:
        arclog.StudyProgram.from_sexp(text, arclog.DecodeSettings())
    except arclog.Refusal as e:
        return 'no mode of the atom' not in str(e)
    return True

def atom_binds(a, bound, outer):
    """The labels that the atom a binds where the labels of bound are bound, or None where a may not stand there. outer is the labels that
    stand outside a, in the rest of its body or before the body; a label of a compound that outer doesn't hold is local to a part of it.
    A positive atom binds its labels once a mode of its relation holds. `=` binds its labels once one of them is bound. A NOT, an ALL and
    another comparison bind none, and need the labels they read from outside. An OR or an IF binds what every part binds, and needs
    each outer label that some part leaves unbound."""
    if not a or a[0] in ('ONE', 'SET'):
        return set()
    labels = atom_labels(a)
    if a[0] == '=':
        return labels if labels & bound or len(labels) < 2 else None
    if a[0] in OPS or a[0] == 'NOT':
        return set() if labels <= bound else None
    if a[0] == 'ALL':
        return set() if labels & outer <= bound else None
    if a[0] in ('OR', 'IF'):
        parts = [p for p in a[1:] if isinstance(p, list)]
        parts = [parts[0] + parts[1], parts[2]] if a[0] == 'IF' else parts
        got = [atoms_bound(p, bound, outer) for p in parts]
        shared = set.intersection(*got)
        return shared if labels & outer <= bound | shared else None
    if a[0].startswith('&'):
        return labels
    sites = [(x[0][1:], atom_labels(x)) for x in a[1:] if isinstance(x, list) and x]
    held = frozenset(c for c, ls in sites if ls <= bound)
    return labels if mode_holds(a[0], held, frozenset(c for c, _ in sites) - held) else None


def atoms_bound(atoms, bound, outer):
    """The labels bound after the atoms of a list that may stand in some order, where the labels of bound are bound."""
    atoms = [a for a in atoms if isinstance(a, list)]
    bound, left = set(bound), list(range(len(atoms)))
    while left:
        kept = []
        for i in left:
            got = atom_binds(atoms[i], bound, outer | atom_labels(atoms[:i] + atoms[i + 1:]))
            if got is None:
                kept.append(i)
            else:
                bound |= got
        if len(kept) == len(left):
            break
        left = kept
    return bound


def mode_rounds(atoms) -> int:
    """Mode depth of a list of atom trees with no marks: the fixpoint rounds of atom_binds. Round 1 holds the atoms that may stand with nothing bound. Round r holds those that may stand
    once the atoms of rounds before r are bound. The result is the last round, 0 for no atoms. An atom that no round holds counts in none."""
    atoms = [a for a in atoms if isinstance(a, list)]
    bound, left, rounds = set(), list(range(len(atoms))), 0
    while left:
        got = {i: atom_binds(atoms[i], bound, atom_labels(atoms[:i] + atoms[i + 1:])) for i in left}
        ready = [i for i in left if got[i] is not None]
        if not ready:
            break
        rounds += 1
        for i in ready:
            bound |= got[i]
        left = [i for i in left if i not in ready]
    return rounds
