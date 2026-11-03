# Order-free relation pick: state of the record

The held reads are done: 15 final models, each once, and one pairs table. `summary.md` has the tables, `pairs.md` the pairs, `audit-order-reads.md` the audit, `features_ofree_facts.py` the fact layer, `fact-layer-check.txt` its checks. Nothing more is running.

Held, RULE atoms, bits saved per left-out atom against the marginal among the options, baseline 5.216 bits, 1,809 atoms on 37 tasks.

| Model | Saved |
|---|---|
| Scope only | +.226 (+.148 to +.316) |
| Other atoms as a set, with their count | +.722 (+.526 to +.930) |
| Primary: the same with join structure | +.944 (+.726 to +1.184) |
| Primary on shuffled labels | -.090 (-.140 to -.043) |
| Primary with open labels and unread forms | +1.252 (+1.031 to +1.491) |
| Primary with written order | +1.309 (+1.108 to +1.531) |
| A random subset of the other atoms | +.512 (+.374 to +.663) |
| Atoms written before | +1.004 (+.858 to +1.164) |
| Atoms written before, with index and last head | +1.056 (+.911 to +1.215) |

Against the bars: the primary is under 1 bit and over .3, so neither bar holds.

Against the prediction: the primary at 1.1 between .9 and 1.3 held at .944. The control within .02 of 0 missed at -.090, with no false gain: it's the cost of noise weights. Order adding about .3 held at .365. The three pairs held both ways. INIT 1.8 read 1.98, DET .7 read .54. Fact gaining least missed: NOT gains least.
