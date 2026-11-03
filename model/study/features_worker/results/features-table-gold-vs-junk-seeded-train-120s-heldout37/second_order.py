"""Second-order facts of each table class with one Position column: how it stands against the classes it reads and the classes that read it, not what it holds alone. Gold is a label only.

gain: accuracy added over input color when predicting output cells, leaving one pair out. parent_gain, reader_gain: the best gain among parents and readers. lift: reader_gain - gain, the signal a reader gets that the table lacks alone. step: gain - parent_gain, the signal the table adds. share_spread: spread of its share of the grid across examples, over the mean. label_overlap: share of a table's labels seen in another example.

  second_order.py NODES_DIR TASKS_DIR OUT STEP OFFSET
"""
import collections, json, os, statistics, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe2 as P
import census as C


def main():
    base, tasks, out, step, offset = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
    files = sorted(e.name for e in os.scandir(base) if e.name.endswith('.nodes.jsonl.zst'))[offset::step]
    done = {json.loads(x)['task'] for x in open(out)} if os.path.exists(out) else set()
    t0, ran = time.time(), 0
    with open(out, 'a') as w:
        for i, f in enumerate(files, 1):
            task = f.split('.')[0]
            if task in done:
                continue
            path = os.path.join(base, f)
            tables, token_of, _ = P.load(path)
            reps, _ = P.classes_of(tables, token_of)
            if len(reps) < 2:
                continue
            nodes = C.raw_nodes(path)
            data = json.load(open(os.path.join(tasks, task + '.json')))
            names = {n: k for k, n in enumerate(sorted({tuple(e[0]) for r in nodes.values() for e in r['x_rows'] or ()}))}
            train = [k for n, k in names.items() if n[0] == 1]
            cell = [r for r in reps if len(P.position_columns(r.types)) == 1 and any(r.ex[1:])]
            gain = {}
            for r in cell:
                g = C.explains_output(r, names, data)
                if g:
                    gain[r.i] = g['output_gain']
            readers = collections.defaultdict(set)
            for r in reps:
                for p in r.parents:
                    readers[p].add(r.i)
            for r in cell:
                n = nodes[min(r.ids)]
                cf = C.clause_facts(n['clause'])
                shares = []
                labels = []
                for k in train:
                    lab = C.cell_labels(r, k)
                    labels.append(set(lab.values()))
                    pair = data['train'][[x for x, y in names.items() if y == k][0][1]]
                    shares.append(len(lab) / (len(pair['input']) * len(pair['input'][0])))
                m = statistics.mean(shares) if shares else 0
                overlap = None
                if len(labels) > 1:
                    seen = [len(x & set().union(*(labels[:j] + labels[j + 1:]))) / len(x) for j, x in enumerate(labels) if x]
                    overlap = round(statistics.mean(seen), 4) if seen else None
                g = gain.get(r.i)
                pg = max((gain[p] for p in r.parents if p in gain), default=None)
                rg = max((gain[x] for x in readers[r.i] if x in gain), default=None)
                w.write(json.dumps(dict(task=task, c=r.i, gold=int(r.gold), seeded=int(any((nodes[x]['tags'] or {}).get('seeded') for x in r.ids if x in nodes)), kind=cf['kind'], op=cf['op'], distinct=cf.get('distinct_reads', 0), negated=cf['negated'], union=cf['union'], columns=len(r.types), parents=len(r.parents), readers=len(readers[r.i]),
                                        gain=g, parent_gain=pg, reader_gain=rg, lift=None if g is None or rg is None else round(rg - g, 4), step=None if g is None or pg is None else round(g - pg, 4), share=round(m, 4), share_spread=round(statistics.pstdev(shares) / m, 4) if m else None, label_overlap=overlap)) + '\n')
            w.flush()
            ran += 1
            print('%d/%d %s cell tables %d | %.0f s | ETA %.0f s' % (i, len(files), task, len(cell), time.time() - t0, (time.time() - t0) / ran * (len(files) - i)), flush=True)
    print('done', round(time.time() - t0), 's', flush=True)


if __name__ == '__main__':
    main()
