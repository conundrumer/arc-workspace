"""Check a judge's recovery clause against a pair's tables.

usage: verify_recovery.py <tables.json> '<clause>'
Evaluates the RULE body over the mutant table, the available tables and `input`,
per train input and per kept assignment, and compares the bound columns with G.
Prints a JSON verdict: verified, or the reason it is not (lib relation, unknown
name, mismatch with row counts).
"""
import itertools, json, re, sys

OPS = {'<': lambda a, b: a < b, '<=': lambda a, b: a <= b, '>': lambda a, b: a > b, '>=': lambda a, b: a >= b,
       '=': lambda a, b: a == b, '!=': lambda a, b: a != b}
BOXES = ('Box', 'Position', 'Offset')


def parse(s):
    tokens = re.findall(r'\(|\)|[^\s()]+', s)
    pos = 0
    def node():
        nonlocal pos
        t = tokens[pos]; pos += 1
        if t == '(':
            out = []
            while tokens[pos] != ')':
                out.append(node())
            pos += 1
            return out
        return t
    tree = node()
    if pos != len(tokens):
        raise ValueError('trailing tokens')
    return tree


def sites(atom):
    """[(column path, term)] of a relation atom; a nested (:key (:Col term)) gives column 'key.Col' and 'Col'."""
    out = []
    for site in atom[1:]:
        if not (isinstance(site, list) and len(site) == 2 and isinstance(site[0], str) and site[0].startswith(':')):
            raise ValueError('bad site ' + json.dumps(site))
        col, term = site[0][1:], site[1]
        if isinstance(term, list):
            for sub, t in sites([None] + [term] if term and isinstance(term[0], str) and term[0].startswith(':') else [None] + term):
                out.append((col + '.' + sub, t))
        else:
            out.append((col, term))
    return out


def column_index(table, col):
    names = [c['name'] for c in table['columns']]
    for cand in (col, col.split('.')[-1]):
        if names.count(cand) == 1:
            return names.index(cand)
    if col.startswith('key.') and col[4:].isdigit():
        return int(col[4:])
    raise ValueError(f"column {col} not in {table['name']} ({', '.join(names)})")


def zero(ty):
    return [0, 0, 0, 0] if ty in BOXES else [0]


def evaluate(body, tables, ex):
    """All bindings (dict var -> value) of the body on train input ex; returns (bindings, bound variable order)."""
    return evaluate_from([dict()], body, tables, ex)


def evaluate_from(bindings, body, tables, ex, bare_bind=frozenset()):
    """bare_bind: labels a later OR branch may name bare although the branch has not made them; the first branch made them."""
    order = []
    for atom in body:
        if not isinstance(atom, list) or not atom:
            raise ValueError('bad atom')
        head = atom[0]
        if head in OPS:
            a, b = atom[1], atom[2]
            new = []
            for env in bindings:
                va = env[a] if a in env else [0] if a == '0' else None
                vb = env[b] if b in env else [0] if b == '0' else None
                if head == '=' and va is None and vb is not None and a in bare_bind:
                    env = dict(env); env[a] = vb; va = vb
                    if a not in order: order.append(a)
                if va is None or vb is None:
                    raise ValueError(f'comparison on unbound variable in {atom}')
                if head in ('<', '<=', '>', '>='):
                    if len(va) != 1 or len(vb) != 1:
                        raise ValueError('order comparison on a box')
                    ok = OPS[head](va[0], vb[0])
                else:
                    if a == '0' or b == '0':
                        other = vb if a == '0' else va
                        ok = OPS[head](list(other), [0] * len(other))
                    else:
                        ok = OPS[head](list(va), list(vb))
                if ok: new.append(env)
            bindings = new; continue
        if head == 'OR':
            # A label the first branch makes is exported when every later branch names it; otherwise it is local to its branch.
            branches = atom[1:]
            for branch in branches:
                if not isinstance(branch, list) or not all(isinstance(x, list) for x in branch):
                    raise ValueError('bad OR branch')
            results = []; first_order = None
            for i, branch in enumerate(branches):
                allow = frozenset(first_order) if i else frozenset()
                sub, sub_order = evaluate_from(bindings, branch, tables, ex, allow)
                if first_order is None: first_order = sub_order
                results.append((sub, sub_order))
            exported = [v for v in first_order if all(v in o for _, o in results[1:])]
            new = []
            for sub, sub_order in results:
                local = set(sub_order) - set(exported)
                for env in sub:
                    new.append({k: v for k, v in env.items() if k not in local})
            bindings = new
            for v in exported:
                if v not in order: order.append(v)
            continue
        negate = head == 'NOT'
        if negate:
            atom = atom[1]; head = atom[0]
        if head not in tables:
            raise ValueError(f'relation {head} not available')
        table = tables[head]; rows = table['rows'][ex]
        spec = []
        for col, term in sites(atom):
            spec.append((column_index(table, col), term, table['columns'][column_index(table, col)]['type']))
        new = []
        for env in bindings:
            matches = []
            for row in rows:
                env2 = dict(env); ok = True
                for i, term, ty in spec:
                    v = row[i]
                    if term == '0':
                        ok = v == zero(ty)
                    elif term.startswith('*') or term.startswith('^'):
                        name = term[1:]
                        if name in env2:
                            ok = env2[name] == v
                        else:
                            env2[name] = v
                    elif term in env2:
                        ok = env2[term] == v
                    elif term in bare_bind:
                        env2[term] = v
                    else:
                        raise ValueError(f'variable {term} used before it is bound')
                    if not ok: break
                if ok:
                    matches.append(env2)
            if negate:
                if not matches: new.append(env)
            else:
                new.extend(matches)
        bindings = new
        if not negate:
            for col, term in sites(atom):
                name = term[1:] if term.startswith('*') or term.startswith('^') else term if term in bare_bind else None
                if name and name not in order: order.append(name)
    seen = set(); out = []
    for env in bindings:
        key = tuple((v, tuple(env[v])) for v in sorted(env))
        if key not in seen:
            seen.add(key); out.append(env)
    return out, order


def check(tables_path, clause):
    T = json.load(open(tables_path))
    tree = parse(clause)
    if not (isinstance(tree, list) and tree[0] == 'RULE' and len(tree) >= 3):
        return dict(verified=False, reason='not a RULE clause')
    body = tree[2:]
    def relations(atoms):
        out = []
        for a in atoms:
            if not isinstance(a, list) or not a or a[0] in OPS: continue
            if a[0] == 'OR':
                for br in a[1:]: out += relations(br)
            elif a[0] == 'NOT': out += relations([a[1]])
            else: out.append(a[0])
        return out
    lib = relations(body)
    verdicts = []
    for a, A in enumerate(T['assignments']):
        tables = {A['mutant']['name']: dict(name=A['mutant']['name'], columns=A['mutant']['columns'], rows=[m[0] if m else [] for m in A['mutant']['train']])}
        for t in A['available']:
            tables.setdefault(t['name'], dict(name=t['name'], columns=t['columns'], rows=t['train']))
        unknown = [n for n in lib if n not in tables]
        if unknown:
            return dict(verified=False, reason='relations not in the tables: ' + ', '.join(unknown), unknown=unknown)
        gold = A['gold']; gtypes = [c['type'] for c in gold['columns']]
        per_ex = []
        try:
            for ex in range(T['ntrain']):
                rows, order = evaluate(body, tables, ex)
                per_ex.append((rows, order))
        except ValueError as exc:
            return dict(verified=False, reason=str(exc))
        order = per_ex[0][1]
        # choose variables for G's columns: injective, type-compatible, same rows on every train input
        var_types = {}
        for rows, _ in per_ex:
            for env in rows:
                for v, val in env.items():
                    var_types[v] = 'box' if len(val) == 4 else 'num'
        cands = [[v for v in order if var_types.get(v, 'box' if ty in BOXES else 'num') == ('box' if ty in BOXES else 'num')] for ty in gtypes]
        found = None
        for choice in itertools.product(*cands):
            if len(set(choice)) != len(choice): continue
            ok = True
            for ex, (rows, _) in enumerate(per_ex):
                got = {tuple(tuple(env[v]) for v in choice) for env in rows}
                want = {tuple(tuple(c) for c in row) for row in (gold['train'][ex][0] if gold['train'][ex] else [])}
                if got != want: ok = False; break
            if ok: found = choice; break
        if found is None:
            counts = [(len(rows), len(gold['train'][ex][0]) if gold['train'][ex] else 0) for ex, (rows, _) in enumerate(per_ex)]
            verdicts.append(dict(assignment=a, verified=False, rows_vs_gold=counts, bound=order))
        else:
            verdicts.append(dict(assignment=a, verified=True, columns=list(found)))
    return dict(verified=all(v['verified'] for v in verdicts), assignments=verdicts)


if __name__ == '__main__':
    print(json.dumps(check(sys.argv[1], sys.argv[2])))
