"""The pool's found forms: read status from the nodes' parents, target found from the run's cover records. Stdlib and the zstd command. No engine.

  python3 features_unread_pool.py

Writes pool-tasks.jsonl, one row per arm and task, flushed: a rerun skips the arm and task pairs that have a row. It prints a rate and an ETA.

A node is a line of <task>.nodes.jsonl.zst. A pool form is the nodes that share the head &f<id> of `clause`: an INIT gives one node per relation. A node's `parents` list every node of each form that its clause reads, so read status is a property of a form. A pool form is read when a node of another form has one of its nodes in `parents`.

Time: tags.draw is the count of draws when a node was added, and a cover event gives its draw and seconds. The state at a draw D is the nodes with tags.draw <= D, and the reads of those nodes.

Target found, per base line: gold-map.jsonl gives the line of the run's first gold, which the `cover` events index, and the line of its second gold (golds-factored.json), which the `cover2` events index. Each event marks a table of one relation of that gold form equal to a node's table. `cover` gives the node; `cover2` gives only the draw. A cover2 hit for a base line with no line in the first gold has no node, so it gives no read status of the target.
"""
import collections
import json
import os
import re
import subprocess
import time

import features_unread_lib as L

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
OUT = HERE + 'pool-tasks.jsonl'
FID = re.compile(r'\(\w+ &f(\d+)')


def nodes_of(path):
    """[(token, form id, draw, set of parent tokens, kind of clause, depth, tag kind)], without the rows."""
    p = subprocess.Popen(['zstd', '-dc', path], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, bufsize=1 << 20)
    out = []
    for line in p.stdout:
        i, j = line.find('"x_rows":'), line.find('"table_types":')
        r = json.loads(line[:i] + line[j:] if 0 < i < j else line)  # the rows are the bulk of a line, and nothing here reads them
        c = r.get('clause') or ''
        m = FID.match(c)
        t = r.get('tags') or {}
        out.append((r['token'], m[1] if m else 'token' + r['token'], t.get('draw', 0), tuple(r.get('parents') or ()), c.split(' ')[0].lstrip('('), r.get('depth'), t.get('kind')))
    p.wait()
    return out


class State:
    def __init__(self, nodes):
        self.nodes = nodes
        self.form_of = {n[0]: n[1] for n in nodes}
        self.kind = {n[1]: n[4] for n in nodes}
        self.first = {}  # form -> first draw
        for n in nodes:
            self.first.setdefault(n[1], n[2])
        self.reads = []  # (draw, read form, reader form)
        for n in nodes:
            for q in n[3]:
                f = self.form_of.get(q)
                if f is None:
                    raise SystemExit('a parent that no node has: %s' % q)
                if f != n[1]:
                    self.reads.append((n[2], f, n[1]))

    def at(self, draw):
        """(forms, unread forms, nodes, unread nodes) at a draw; draw None is the end."""
        forms = {f for f, d in self.first.items() if draw is None or d <= draw}
        read = {f for d, f, _ in self.reads if draw is None or d <= draw}
        nodes = [n for n in self.nodes if draw is None or n[2] <= draw]
        return len(forms), len(forms - read), len(nodes), sum(n[1] not in read for n in nodes)

    def status(self, form, draw=None):
        """(read or not, count of forms that read it) at a draw; draw None is the end."""
        who = {g for d, f, g in self.reads if f == form and (draw is None or d <= draw)}
        return bool(who), len(who)


def one(arm, task, gmap):
    base = '%s%s/%s' % (L.RUN, arm, task)
    done = json.load(open(base + '.done.json'))
    ev = [json.loads(x) for x in open(base + '.events.jsonl')]
    nodes = nodes_of(base + '.nodes.jsonl.zst')
    st = State(nodes)
    first, first2 = {}, {}
    for e in ev:
        if e.get('event') == 'cover':
            first.setdefault(e['gold'], e)
        elif e.get('event') == 'cover2':
            first2.setdefault(e['gold'], e)
    targets = []
    for g in gmap:
        r = dict(line=g['line'], source=None, found=None)
        e = first.get(g['kit']) if g['kit'] is not None else None
        e2 = first2.get(g['gold2']) if g['gold2'] is not None else None
        if g['kit'] is not None:
            r['source'] = 'cover'
            r['found'] = e is not None
            if e is None and e2 is not None:
                r['found'], r['source'] = True, 'cover2'
        elif g['gold2'] is not None:
            r['source'] = 'cover2'
            r['found'] = e2 is not None
        hit = e or e2
        if hit:
            d = hit['draw']
            forms, unread, n, un = st.at(d)
            r.update(seconds=hit['seconds'], draw=d, forms_at_found=forms, unread_at_found=unread, nodes_at_found=n, unread_nodes_at_found=un)
        if e:
            f = st.form_of[str(e['node'])]
            r.update(node=e['node'], pool_form=f, node_kind=st.kind[f], depth=e.get('depth'), read_at_found=st.status(f, e['draw'])[0], read_end=st.status(f)[0], readers_end=st.status(f)[1])
        targets.append(r)
    forms, unread, n, un = st.at(None)
    return dict(arm=arm, task=task, seconds=done.get('seconds'), draws=done.get('draws'), done_forms=done.get('forms'), done_nodes=done.get('nodes'), done_covered=done.get('covered'), done_gold=done.get('gold'), forms=forms, unread=unread, nodes=n, unread_nodes=un,
                kinds=dict(collections.Counter(x[4] for x in nodes)), targets=targets)


def main():
    gm = collections.defaultdict(list)
    for x in open(HERE + 'gold-map.jsonl'):
        r = json.loads(x)
        gm[r['task']].append(r)
    done = set()
    if os.path.exists(OUT):
        done = {(r['arm'], r['task']) for r in map(json.loads, open(OUT))}
    todo = [(a, t) for a in L.ARMS for t in L.held_tasks() if t not in L.NOT_IN_RUN and (a, t) not in done]
    print('%d arm and task pairs to do, %d done' % (len(todo), len(done)), flush=True)
    t0 = time.time()
    with open(OUT, 'a') as out:
        for c, (a, t) in enumerate(todo, 1):
            r = one(a, t, gm[t])
            out.write(json.dumps(r) + '\n')
            out.flush()
            rate = c / (time.time() - t0)
            print('%s %s: %d forms, %d unread, %d nodes; %.2f pairs/s, %d left, ETA %.0f s' % (a, t, r['forms'], r['unread'], r['nodes'], rate, len(todo) - c, (len(todo) - c) / rate), flush=True)


if __name__ == '__main__':
    main()
