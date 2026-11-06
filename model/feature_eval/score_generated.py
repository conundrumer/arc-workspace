src=open('/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/12a37de8-ac57-40d8-8718-66c6d6d45701/scratchpad/eval2/all_read.py').read()
head=src[:src.index("def speak(name, tasks, keep):")]
exec(head)
import glob
names={}
for split in ('train','dev'):
    path=f'{ALL}{split}/candidate-dump-generated-names.tsv'
    if os.path.exists(path):
        for line in open(path):
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
