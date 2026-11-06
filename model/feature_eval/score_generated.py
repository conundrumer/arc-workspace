import sys
src=open('/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/12a37de8-ac57-40d8-8718-66c6d6d45701/scratchpad/eval2/all_read.py').read()
head=src[:src.index("def speak(name, tasks, keep):")]
exec(head)
import glob
sys.path.insert(0, os.path.dirname(os.path.abspath(sys.argv[0])))
from common import data_exists, glob_data, open_text, read_json


def pair_groups(split, task):
    """Each item's pair groups, cached as zstd."""
    cache = f'{ALL}{split}/pair-groups/{task}.json'
    if data_exists(cache):
        return read_json(cache)
    t = read_json(f'{ALL}{split}/candidate-tables/{task}.json')
    out = [dict(groups=[group(it['gold'], m['table']) for m in it['mutants']]) for it in t['items']]
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    with open_text(cache + '.zst', 'w') as sink:
        sink.write(json.dumps(out))
    return out


def load_split(split, rule):
    tasks = {}
    rank = Counter()
    for f in glob_data(f'{ALL}{split}/{rule}/*.json'):
        d = read_json(f)
        g = pair_groups(split, d['task'])
        items = []
        for it, gs in zip(d['items'], g):
            if it['last']:
                continue
            items.append((prep(it['true'], rank, 1), prep(it['null'], rank, -1), gs['groups'], None))
        tasks[d['task']] = items
    return tasks


names={}
for split in ('train','dev'):
    path=f'{ALL}{split}/candidate-dump-generated-names.tsv'
    if data_exists(path):
        for line in open_text(path):
            k,_,t=line.rstrip('\n').partition('\t')
            names[k]=t
print(len(names),'named shapes',flush=True)
results={}
for label,rule in (('size 1 or less','candidate-dump-generated-d1'),('size 2 or less','candidate-dump-generated-d2')):
    ID.clear()
    NAME.clear()
    train=load_split('train',rule)
    dev=load_split('dev',rule)
    print(f'\n## {label}: {len(NAME)} shapes that told two tables apart, {len(train)} + {len(dev)} tasks',flush=True)
    every=set(range(len(NAME)))
    for split,tasks,other in (('train',train,dev),('dev',dev,train)):
        if not tasks or not other:
            continue
        net,seen_by=votes(other)
        order=[k for k,_ in net.most_common()]
        print(f'-- {split}',flush=True)
        show('all, mutant has rows',tasks,None)
        show('all, every pair',tasks,None,EVERYTHING)
        show('top 30, rows',tasks,set(order[:30]))
        show('top 100, rows',tasks,set(order[:100]))
        show('top 1000, rows',tasks,set(order[:1000]))
        if split=='dev':
            print('   top on train:',[names.get(NAME[k],NAME[k])[:80] for k in order[:12]],flush=True)
