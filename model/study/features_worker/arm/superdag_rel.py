"""The bundle's superdag with the node scores in the relation pick: a relation option of a scope form has its weight multiplied by exp(beta * (node score - mean over the scope's options)). Each slot of a form takes the score of the node of its table. With REL_NOREP, an option the clause has read takes no boost. Nothing else changes, and beta 0 is the bundle's loop.
"""
import math, os, re, sys
A = os.path.dirname(os.path.abspath(__file__)) + '/model/study/sampler'
sys.path.insert(0, A)
import live  # noqa: E402
import superdag as D  # noqa: E402
BETA = float(os.environ.get('REL_BETA', 0))
SLOT = re.compile(r'&r\d+')
NOREP = bool(os.environ.get('REL_NOREP'))
SC = {}
SLOTS, KEYS = {}, []  # form id -> {slot offset in the form: node id}; the table keys of the current take
_init, _scope, _rel = D.Pool.__init__, D.Run.scope, live.LiveDrawer.rel_factors
_take, _key = D.Pool.take, D.table_key
POOL = []


def init(self, *a, **k):
    _init(self, *a, **k)
    POOL[:] = [self]


def table_key(tb):
    got = _key(tb)
    KEYS.append(got[0])
    return got


def take(self, f, pg, kind, nscope):
    KEYS.clear()
    form = _take(self, f, pg, kind, nscope)
    if form is not None:
        at = live.M.slot_no(live.head_of(f.program_form().split('\n')[nscope]))
        SLOTS[form.id] = {s - at: self.keys[k] for (s, _), k in zip(D.relation_tables(pg.before), KEYS)}
    return form


def scope(self, forms):
    got = _scope(self, forms)
    SC.clear()
    if POOL and BETA:
        pool = POOL[0]
        sc = getattr(pool.policy, 'score2', None) or pool.policy.score
        for r, f in got[1].written.items():
            if f.startswith('&f') and f[2:].isdigit():
                at = live.M.slot_no(r)
                for off, n in SLOTS.get(int(f[2:]), {}).items():
                    if n in sc:
                        SC['&r%d' % (at + off)] = sc[n]
        if SC:
            m = sum(SC.values()) / len(SC)
            for r in SC:
                SC[r] = math.exp(BETA * (SC[r] - m))
    return got


def rel_factors(self, fr, n, popts, k, scope_types, key, rel, joined, leaf):
    got = _rel(self, fr, n, popts, k, scope_types, key, rel, joined, leaf)
    if not SC:
        return got
    out, read = [], set(key)
    for x, g in zip(popts, got):
        m = SLOT.match(self.V.name(x))
        e = SC.get(m[0], 1.0) if m else 1.0
        out.append(g * (min(e, 1.0) if NOREP and x in read else e))
        if m:
            POOL[0].c['rel:derived option ' + ('scored' if m[0] in SC else 'unscored')] += 1
    return out


D.Pool.__init__, D.Pool.take, D.table_key, D.Run.scope, live.LiveDrawer.rel_factors = init, take, table_key, scope, rel_factors
if __name__ == '__main__':
    if float(os.environ.get('FIRST_PASS_SECONDS', 0)):
        import superdag_search as Q
        Q.install('draws')
    D.main()
