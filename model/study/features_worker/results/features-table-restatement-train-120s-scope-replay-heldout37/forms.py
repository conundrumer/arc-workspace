"""Parses gold forms and sorts each by what its body reads."""
import collections, gzip, json, os, re

def parse(s):
    tok = re.findall(r'[()]|[^\s()]+', s)
    st, cur = [], []
    for t in tok:
        if t == '(':
            st.append(cur); cur = []
        elif t == ')':
            x = cur; cur = st.pop(); cur.append(x)
        else:
            cur.append(t)
    return cur[0] if cur else []

def gold_lines(path):
    with gzip.open(path, 'rt') as f:
        r = json.loads(f.readline())
    return r.get('task'), [x for x in r['gold_sexp'].splitlines() if x.strip()]

def atoms(body):
    """Yields (head, negated, in_or) for each atom of a body."""
    for a in body:
        if not isinstance(a, list) or not a:
            continue
        h = a[0]
        if h == 'NOT':
            for x in atoms(a[1:]):
                yield (x[0], True, x[2])
        elif h == 'OR':
            for branch in a[1:]:
                for x in atoms(branch):
                    yield (x[0], x[1], True)
        else:
            yield (h, False, False)

def views():
    V = 'work/lm/data-study/gold/gold-v3-combined-cut/view-final'
    for e in sorted(os.scandir(V), key=lambda e: e.name):
        p = e.path + '/pairs.jsonl.gz'
        if os.path.exists(p):
            yield e.name, gold_lines(p)[1]
