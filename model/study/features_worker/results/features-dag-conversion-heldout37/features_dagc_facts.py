"""The fact layer of the DAG conversion: facts of a pick, as a function of its downset D, its slot and its scope, with no read of order.

`ctx_of` builds the context of a pick from the atoms of D. `pick_facts` gives the family names of features_ofree_facts.row_facts on that context, with the scope's forms in place of rec['opts'], and the family `ddepth`
(the mode depth of D, features_dagc_modes.mode_rounds). `ALLOWED_COLUMNS` and `ALLOWED_TOKENS` list what a model may read, and `check_columns` and `check_tokens` raise BannedFact on any other name.
The atoms of D stand with their marks stripped: a mark sits on the atom written first that binds a label, which is a fact of order.
"""
import fnmatch
import re

import features_dag_order as D
import features_dagc_modes as M
import features_ofree_facts as FL
import features_ofree_text as T
import features_rel_content as C
from features_ofree_facts import BannedFact  # noqa: F401  # re-exported

RN = re.compile(r'&f(\d+)')


def rn(x):
    """A pool form's head &fN reads as &r(1000000+N), as features_ps_data.rn has it."""
    return RN.sub(lambda m: '&r%d' % (1000000 + int(m[1])), x)


FAMILIES = dict(FL.ROW_FAMILIES, ddepth='the mode depth of the downset, as a threshold')
SIZES = FL.SIZES
DDEPTHS = (1, 2, 3, 4, 5, 6)
TIER_FAMILIES = {t: (fams | {'ddepth'} if t != 'scope' else set(fams)) for t, fams in FL.TIER_FAMILIES.items()}

ALLOWED_COLUMNS = ['lq', 'lp', 'gap_top', 'share_kind', 'entropy', 'top_q', 'is_lib', 'is_macro', 'is_fact', 'is_derived', 'is_not', 'is_cmp', 'dead_join', 'own', 'uses', 'arity', 'hit', 'hit_frac',
                   'none_in_scope', 'new_types', 'depth', 'defined', 'method', 'sibling', 'path', 'dsize', 'd_depth', 'root2', 'in_branch', 'nscope', 'nopts', 'nder', 'nalive', 'ncmp', 'prefix_depth',
                   'form_atoms', 'form_not', 'form_or']
ALLOWED_PATTERNS = ['type_*', 'col*_in_scope', 'scope_n_*', 'grid_*']
CONTENT_COLUMNS = list(C.OPTION) + list(C.JOIN) + list(C.PREFIX) + ['t_rows_rel', 'j_match_rank', 'j_cont_rank', 's_cont_rank', 'der_rows_rank']
ALLOWED_TOKENS = ['prefix:', 'scope:'] + sorted(FAMILIES)
# Names that stay out of the lists: ord, k, last*, recency*, prevform*, readers, kept_reads, scopereads*, steer, rank, der_rank, opt_readers*, q_live.


def check_columns(names):
    """Raises BannedFact on a column outside the allowed list. Returns the names."""
    ok = set(ALLOWED_COLUMNS) | set(CONTENT_COLUMNS)
    for n in names:
        if n not in ok and not any(fnmatch.fnmatchcase(n, p) for p in ALLOWED_PATTERNS):
            raise BannedFact(n)
    return names


def check_tokens(names):
    """Raises BannedFact on a sparse token whose prefix is not in ALLOWED_TOKENS (`prefix:`, `scope:`, or a family of ROW_FAMILIES)."""
    for n in names:
        fam, sep, _ = n.partition(':')
        if not sep or (fam + ':') not in ALLOWED_TOKENS and fam not in FAMILIES:
            raise BannedFact(n)
    return names


def ctx_of(atoms, prog):
    """The context list of a pick: one entry per atom of D, as features_ofree_text.ctx_atom builds it. atoms holds trees, or (tree, where) with where `in` for an atom of the pick's own body and `near` for another. The atoms' marks are stripped here."""
    ids, out = {}, []
    for a in atoms:
        tree, where = a if isinstance(a, tuple) else (a, 'in')
        tree = D.strip_marks(tree)
        out.append(T.ctx_atom(prog, T.Atom(tree), where, ids))
    return out


def program_of(lines, reg):
    """The program of a scope's forms (an `&fN` head read as `&r(1000000+N)`), for ctx_of and scope_record."""
    return T.Program([rn(x) for x in lines], reg)


def scope_record(prog):
    """rec for row_facts: opts, scope_heads and anc over every form of the scope, in place of the options of gold's form."""
    opts = []
    for f in prog.forms:
        for g, p in ([(f, q) for q in prog.reg.ports.get(f.comp, [''])] if f.kind == 'INIT' else [(f, '')]):
            tok = '%s.%s' % (g.comp, p) if g.kind == 'INIT' else g.comp if g.kind == 'PROPOSER' else prog.family(g)
            opts.append(dict(f=g.name, p=p, fam=prog.family(g), comp=g.comp, tok=tok, heads=prog.bodyheads[g.name], depth=prog.depth[g.name], nbody=prog.nbody[g.name], readers=len(prog.readers[g.name]), anc=sorted(prog.anc[g.name])))
    return dict(opts=opts, scope_heads=sorted({h for f in prog.forms for h in prog.bodyheads[f.name]}), anc={f.name: sorted(prog.anc[f.name]) for f in prog.forms})


def pick_facts(pick, prog, tier='dag', rec=None):
    """The fact names of a pick: row_facts on its context, and ddepth. pick: place (RULE, DET, key or port), comp, port, under (a list of or, all, not, if), ctx (from ctx_of), d_depth. prog: the scope's program."""
    rec = rec or scope_record(prog)
    row = dict(place=pick['place'], comp=pick.get('comp') or '', port=pick.get('port') or '', under=pick.get('under') or [], ctx=pick['ctx'])
    out = set(FL.row_facts(row, rec, tier if tier != 'dag' else 'dag'))
    if 'ddepth' in TIER_FAMILIES[tier]:
        out |= {'ddepth:%d' % s for s in DDEPTHS if pick['d_depth'] >= s}
    return check_tokens(out)


# ---------------------------------------------------------------- picks of a form, for the invariance check

def pick_of(dag, downset, atom_id):
    """The pick that takes `atom_id` after the leaf atoms `downset` (ids) in the form of `dag`: place, comp, port, under, the atoms of D and their `where`."""
    tree = D.parse(dag.text)
    kind = tree[0]
    body_of = {a.id: b for b in dag.all_bodies for a in b.items}
    leaf_body = {}
    for b in dag.all_bodies:
        for a in b.items:
            for x in a.leaves():
                leaf_body[x.id] = b
    mine = leaf_body[atom_id]
    top = mine.path.split('/')[0]
    root = next(b for b in dag.bodies if b.path == top)
    comp = tree[2] if kind == 'INIT' else ''
    port = ''
    if root.role.startswith('port:'):
        port = '%s.%s' % (comp, root.role[5:]) if comp else root.role[5:]
    place = kind if root.role == 'top' else 'key' if root.role == 'key' else 'port' if root.role.startswith('port:') else root.role
    under = sorted(({'or'} if '/or' in mine.path else set()) | ({'all'} if '/all' in mine.path else set()))
    atoms = [(dag.atoms[i].tree, 'in' if leaf_body[i] is mine else 'near') for i in sorted(downset)]
    return dict(place=place, comp=comp if kind == 'INIT' else '', port=port, under=under, atoms=atoms, d_depth=M.mode_rounds([D.strip_marks(t) for t, _ in atoms]))
