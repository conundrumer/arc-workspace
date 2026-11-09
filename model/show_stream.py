"""Print a gold stream by token name: model tokens plain, engine tokens in [brackets]."""
import json, subprocess, sys
import arclog

tid = sys.argv[1]
task = arclog.Task.from_json(open(f"data/tasks/{tid}.json").read(), arclog.World.Closed)
voc = arclog.Session(task).vocabulary
out = subprocess.run(["engine/target/tool/arclog-cli", "stream", f"programs/arclog/{tid}.arclog"],
                     capture_output=True, text=True, check=True).stdout
toks = json.loads(out)
words = [voc.name(t["id"]) if t["emitter"] == "model" else f"[{voc.name(t['id'])}]" for t in toks]
print(f"{len(toks)} tokens, {sum(t['emitter']=='model' for t in toks)} model, vocab {len(voc)}")
print(" ".join(words))
