import gzip, hashlib, json, os, sys
v = sys.argv[1]
h = hashlib.sha256()
for t in sorted(os.listdir(v)):
    p = os.path.join(v, t, 'pairs.jsonl.gz')
    if os.path.exists(p):
        h.update((t + '\n' + '\n'.join(json.loads(gzip.open(p, 'rt').readline())['gold_sexp'].splitlines()) + '\n\0').encode())
print(h.hexdigest())
