#!/usr/bin/env python3
"""Filter the corpus to eligible comments, tag them, era-split, and sample."""
import json, os, re, collections, random

OUT = os.path.dirname(os.path.abspath(__file__))
ERA_CUT = "2026-08-26T01:00"

corpus = json.load(open(os.path.join(OUT, "corpus.json")))

JUNK = ["Stop hook feedback:", "<task-notification>", "<bash-input>", "<bash-stdout>",
        "Continue from where you left off.", "<local-command", "<command-name>",
        "Revision check on this turn's writes"]

TRIG = set("""next commit go fit do it done yes ok okay y proceed continue run write stage promote
cleanup all and ship push retry again more resume good sure fine now please k backlog drop add
this that then one first second lgtm thanks ty np agreed makes sense sounds callouts callout
simplify prune audit revise handoff nice great cool right no nope stop wait""".split())


def is_trigger(text):
    t = text.strip().lower()
    stripped = re.sub(r"\b[0-9a-f]{8}\b", " ", t)
    if stripped.strip(" ,.\n") == "" and re.search(r"\b[0-9a-f]{8}\b", t):
        return True
    t2 = re.sub(r"^\d+[.)]\s*", "", stripped)
    t2 = re.sub(r"[^a-z\s]", " ", t2)
    w = t2.split()
    if not w:
        return True
    if len(w) <= 4 and all(x in TRIG for x in w):
        return True
    return False


# taxonomy from 80db06f8's classify.py, used only to stratify the old-era sample
CATS = [
 ("ALT_MODEL", r"alt model|alternat(e|ive) model|another way of looking|another model|"
               r"potential alt|any alts|alts\?|other models|as a human (i|im|i'm)|"
               r"my (human )?percept|i see (it|the|this)|human perceptual|"
               r"i was thinking:|i(')?d model|different model|diff model"),
 ("OVERFIT_VETO", r"\bveto\b|too specific|overfit|over-fit|a stretch|too much of a stretch|"
                  r"drop\b.*comp|not general"),
 ("TASK_LOCAL_COMP", r"task[- ]local|solver[- ]local|task local comp|solver comp|"
                     r"local comp|\bstage\b|staging|staged"),
 ("PROMOTE_GENERALIZE", r"\bpromot|widen|generaliz|more general|extend \w+ to|subsume|"
                        r"key\b.*lib|into the lib|to lib|lib[- ]ready|precedence|precendence"),
 ("INDIRECTION_AWKWARD", r"indirection|coordinate surgery|smell|roundabout|awkward|"
                         r"doesn'?t feel right|feels? (weird|off|odd|bloated)|"
                         r"something (doesn'?t|does not) (seem|feel)|"
                         r"something feels|not sure how i feel|suspicious|"
                         r"encoding data as ops|impl(ementation)?[- ]vibes"),
 ("NAMING", r"\bname[sd]?\b|\bnaming\b|call(ed)? it|why call|rename|better name|"
            r"more precise term|alt names"),
 ("EXPLAIN", r"\bexplain\b|say more|\bwym\b|what do you mean|i don'?t understand|"
             r"i'?m confused|confused about|elaborate|illustrate|\btldr\b|"
             r"not (quite )?following|you lost me|having trouble understanding|"
             r"whats? (going on|happening)|restate"),
 ("PROCESS_DOCGAP", r"in the docs|the docs (say|made|told|gave)|propose (a )?doc|doc update|"
                    r"what (needs to|should) change|why did you|what made you|"
                    r"what prompted|why didn'?t you|why are you|gap in the doc|"
                    r"where did you get|how did you (get|come)|what in the docs|"
                    r"so you would have|prevent (this|that) from happening|"
                    r"what caused you|what led you|what lead you"),
 ("STYLE_PRUNE", r"\bprune|wordy|docstring|fluff|leakage|bloat|plainly|keep it plain|"
                 r"global style|too big|convoluted|write plainly"),
 ("DATA_READING", r"task data|task json|data version|in the data|data[- ]heavy|"
                  r"look at the (task|json)|isn'?t in the task|data form|"
                  r"put in(to)? consts|encode it as data|store the"),
 ("TOOLING_PERF", r"\blint|\bfit\b|budget|timeout|timing out|runner|perf(ormance)?\b|"
                  r"too (slow|long)|5s|atoms|harness"),
 ("SIMPLIFY", r"simpl(er|est|ify|ification|e way)|complicated|complicat|"
              r"can anything be|any other simplif|how much simpler|"
              r"more direct|most direct|minimal"),
 ("CORRECTNESS", r"that'?s not right|no thats not right|wrong\b|incorrect|invalid|"
                 r"\bbug\b|mistake|doesn'?t work|really\?"),
]
COMPILED = [(n, re.compile(p, re.I)) for n, p in CATS]


def clip(s, n):
    s = s.strip()
    if len(s) <= n:
        return s
    return s[:int(n * 0.7)] + "\n...[trimmed]...\n" + s[-int(n * 0.3):]


rows = []
seen = set()
counter = collections.Counter()
n_junk = n_trig = n_dup = n_noprev = 0
for s in corpus:
    cs = s["comments"]
    for i, c in enumerate(cs):
        t = c["text"].strip()
        if any(j in t for j in JUNK):
            n_junk += 1
            continue
        key = (s["task"], re.sub(r"\W+", "", t.lower())[:200])
        if key in seen:
            n_dup += 1
            continue
        seen.add(key)
        if is_trigger(t):
            n_trig += 1
            continue
        if not c["prev"].strip():
            n_noprev += 1
            continue
        counter[s["kind"]] += 1
        tags = [n for n, rx in COMPILED if rx.search(t)] or ["OTHER"]
        nxt = []
        for c2 in cs[i + 1:]:
            t2 = c2["text"].strip()
            if not t2 or any(j in t2 for j in JUNK):
                continue
            nxt.append(clip(t2, 300))
            if len(nxt) >= 5:
                break
        rows.append({
            "id": f"{s['kind'][0]}{counter[s['kind']]}",
            "kind": s["kind"], "task": s["task"], "file": s["file"],
            "ts": c["ts"], "era": "new" if (c["ts"] or "") >= ERA_CUT else "old",
            "tags": tags,
            "user_comment": t,
            "preceding_assistant_message": clip(c["prev"], 5000),
            "following_user_messages": nxt,
        })

print("junk", n_junk, "dup", n_dup, "trigger", n_trig, "no-prev", n_noprev)
print("eligible", len(rows))
print(collections.Counter(r["era"] for r in rows))
json.dump(rows, open(os.path.join(OUT, "_pool.json"), "w"))

# ---- sampling ----
new = [r for r in rows if r["era"] == "new"]
old = [r for r in rows if r["era"] == "old"]
random.seed(7)
random.shuffle(old)
byid = {r["id"]: r for r in old}
tagpool = collections.defaultdict(list)
for r in old:
    for t in r["tags"]:
        tagpool[t].append(r["id"])

sel, selset, have = [], set(), collections.Counter()
for tag in sorted(tagpool, key=lambda t: len(tagpool[t])):
    for rid in tagpool[tag]:
        if have[tag] >= 10:
            break
        if rid in selset:
            continue
        selset.add(rid); sel.append(rid)
        for t in byid[rid]["tags"]:
            have[t] += 1
for r in old:
    if len(sel) >= 200:
        break
    if r["id"] in selset:
        continue
    selset.add(r["id"]); sel.append(r["id"])
    for t in r["tags"]:
        have[t] += 1

print("old sampled", len(sel), "of", len(old))
for t, n in sorted(have.items(), key=lambda x: -x[1]):
    print(f"  {t}: {n} of {len(tagpool[t])}")
print("new included", len(new))

sample = [byid[i] for i in sel] + new
json.dump(sample, open(os.path.join(OUT, "_sample.json"), "w"), indent=1)
print("total pairs", len(sample))
