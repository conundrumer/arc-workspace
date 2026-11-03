"""The texts of order_check.sh: for each stem, T (the start text) and A (T:a, the forms and atoms in another valid order) as {stem: lines} files in orderchk/.

  <runtime python> gold_dagcut2_ordertexts.py STEM...

T is dag-kit/scratch/v2-lines-<stem>.json (142ca369: lines-142ca369.json). A is key `A` of dag-kit/scratch/v2-<stem>.json where that file exists (142ca369: lines-142ca369-a.json); else it is made as dag-kit/scratch/v2_make.py makes it (random.Random(1): a random order of the forms that keeps every form after the forms it reads, then another atom order of each form that the reader takes). The dag-kit files are read, not changed.
"""
import json, os, random, re, sys
import gold_fork_reads as F
import gold_shapecut_one as S
from gold_dag_orders import Orders

KS = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad/dag-kit/scratch/'
NAME = re.compile(r'&[A-Za-z_0-9]+')


def made(ls):
    rng = random.Random(1)
    head = {NAME.search(x.split()[1])[0]: j for j, x in enumerate(ls) if not x.startswith('(OUT') and NAME.search(x.split()[1])}
    rd = [{head[n] for n in NAME.findall(x) if n in head} - {j} for j, x in enumerate(ls)]
    left, order = set(range(len(ls))), []
    while left:
        c = sorted(j for j in left if not rd[j] & left)
        j = rng.choice(c)
        left.remove(j)
        order.append(j)
    p = [ls[j] for j in order]
    q = []
    for x in p:
        got = x
        if not x.startswith('(OUT'):
            try:
                o = Orders(x)
                if o.bodies:
                    for _ in range(30):
                        y = o.render(o.sample(rng))
                        if y != x and S.reader_takes(q + [y] + [z for z in p if z.startswith('(OUT')], len(q)):
                            got = y
                            break
            except ValueError:
                pass
        q.append(got)
    return q


def main():
    F.load_sampler()
    os.makedirs('orderchk', exist_ok=True)
    for t in sys.argv[1:]:
        tpath = KS + ('lines-142ca369.json' if t == '142ca369' else 'v2-lines-%s.json' % t)
        T = [x for x in json.load(open(tpath))[t] if x.strip()]
        if t == '142ca369':
            A = [x for x in json.load(open(KS + 'lines-142ca369-a.json'))[t] if x.strip()]
            how = 'lines-142ca369-a.json'
        elif os.path.exists(KS + 'v2-%s.json' % t):
            A = json.load(open(KS + 'v2-%s.json' % t))['A']
            how = 'v2-%s.json key A' % t
        else:
            json.dump({t: T}, open('orderchk/lines-%s-T.json' % t, 'w'))
            S.setup(t, 'orderchk/lines-%s-T.json' % t, 600)
            A = made(list(S.base_lines))
            how = 'made as v2_make.py makes it'
        json.dump({t: T}, open('orderchk/lines-%s-T.json' % t, 'w'))
        json.dump({t: A}, open('orderchk/lines-%s-A.json' % t, 'w'))
        print(t, 'T', len(T), 'A', len(A), how, '| lines moved', sum(a != b for a, b in zip(T, A)))


if __name__ == '__main__':
    main()
