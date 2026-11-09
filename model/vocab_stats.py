"""Token frequencies over the concept streams of the gold corpus, by token class."""
import collections, json, subprocess, sys
import arclog

ids = [l.split()[0] for l in open("work/lm-size/stream-lengths.txt") if l.strip()]
voc = arclog.Session(arclog.Task.from_json(open(f"data/tasks/{ids[0]}.json").read(), arclog.World.Closed)).vocabulary
names = [voc.name(i) for i in range(len(voc))]

CLASS_OF_KIND = {"relation": "relation ref", "label": "label", "column": "column", "control": "keyword/mark",
                 "component": "component/proposer", "proposer": "component/proposer",
                 "fact relation": "keyword/mark", "lib relation": "lib relation", "relation macro": "lib relation"}
kinds = [voc.kind(i) for i in range(len(voc))]
kind_of = dict(zip(names, kinds))

def cls(n):
    return CLASS_OF_KIND[kind_of[n]]

model, engine, used = collections.Counter(), collections.Counter(), collections.Counter()
for tid in ids:
    r = subprocess.run(["engine/target/tool/arclog-cli", "stream", f"programs/arclog/{tid}.arclog"], capture_output=True, text=True)
    if r.returncode: continue
    for t in json.loads(r.stdout):
        n = names[t["id"]]
        (model if t["emitter"] == "model" else engine)[cls(n)] += 1
        if t["emitter"] == "model": used[n] += 1

vc = collections.Counter(cls(n) for n in names)
print("vocabulary by class:", dict(vc))
print("model tokens by class:", dict(model))
print("engine tokens by class:", dict(engine))
for c in ["component/proposer", "lib relation", "keyword/mark"]:
    tot = [n for n in names if cls(n) == c]
    u = [n for n in tot if used[n]]
    print(f"{c}: {len(u)} of {len(tot)} used; top:", [(n, used[n]) for n in sorted(u, key=lambda n: -used[n])[:12]])
    print("   used once or twice:", sum(1 for n in u if used[n] <= 2))
print("max label index:", kinds.count("label") - 1, "max relation ref:", kinds.count("relation") - 1)
