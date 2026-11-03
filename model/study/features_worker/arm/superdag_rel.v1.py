"""The bundle's superdag with the node scores in the relation pick: a relation option of a scope form has its weight multiplied by exp(beta * (form score - mean over the scope's forms)). A form's score is the best policy score of its nodes. Nothing else changes, and beta 0 is the bundle's loop.
"""
import math, os, re, sys
A = os.path.dirname(os.path.abspath(__file__)) + '/model/study/sampler'
sys.path.insert(0, A)
import live  # noqa: E402
import superdag as D  # noqa: E402
BETA = float(os.environ.get('REL_BETA', 0))
SLOT = re.compile(r'&r\d+')
SC = {}
_init, _scope, _rel = D.Pool.__init__, D.Run.scope, live.LiveDrawer.rel_factors
POOL = []


def init(self, *a, **k):
    _init(self, *a, **k)
    POOL[:] = [self]


def scope(self, forms):
    got = _scope(self, forms)
    SC.clear()
    if POOL and BETA:
        pool = POOL[0]
        for r, f in got[1].written.items():
            if f.startswith('&f') and f[2:].isdigit() and int(f[2:]) in pool.forms:
                sc = getattr(pool.policy, 'score2', None) or pool.policy.score
                ss = [sc[n] for n in pool.forms[int(f[2:])].nodes if n in sc]
                if ss:
                    SC[r] = max(ss)
        if SC:
            m = sum(SC.values()) / len(SC)
            for r in SC:
                SC[r] = math.exp(BETA * (SC[r] - m))
    return got


def rel_factors(self, fr, n, popts, k, scope_types, key, rel, joined, leaf):
    got = _rel(self, fr, n, popts, k, scope_types, key, rel, joined, leaf)
    if not SC:
        return got
    out = []
    for x, g in zip(popts, got):
        m = SLOT.match(self.V.name(x))
        out.append(g * SC.get(m[0], 1.0) if m else g)
        if m:
            POOL[0].c['rel:derived option ' + ('scored' if m[0] in SC else 'unscored')] += 1
    return out


D.Pool.__init__, D.Run.scope, live.LiveDrawer.rel_factors = init, scope, rel_factors
if __name__ == '__main__':
    D.main()
