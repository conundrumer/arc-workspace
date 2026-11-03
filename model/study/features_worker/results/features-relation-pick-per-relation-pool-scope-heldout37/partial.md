# Relation pick, per-relation models on pool scopes: state of the record

The held reads are done, 23 in all, listed in `reads.log`. `summary.md` holds every number, `manifest.json` the design, `prediction-agent.md` the prediction.

Design: a gold RULE form qualifies in a base arm when the run's cover events hold each form it reads. Its scope is gold's text of the read forms with their ancestors, plus the forms of a real RULE visit after the last read form's first cover. A visit form that covers one of those gold forms leaves the scope, unless another scope form reads it.

Assumptions:

- Gold's text stands in for the pool's covering text. A cover is a table match, and 359 of 591 first covers have gold's frame in `cover-rows.tsv`.
- Ancestors of read forms come in gold's text whether or not the pool found them: 442 of 641 scope gold forms were covered.
- A built scope is one form larger than a real scope of its size, as the read forms join the visit's forms. Holds, built and no-reads rows are read apart in `summary.md`.
- The visit is drawn by tries, 2 per form and run.

Gold-alive picks against the steered prior:

| Model | Pool rows, 920 picks |
|---|---|
| Primary as fit, reads written order | -.07 (-.25 to +.09) |
| Refit on parents rows, no lexical order | -.09 (-.21 to +.02) |
| Refit on pool rows and parents rows, no lexical order | +.32 (+.13 to +.47) |

Forms with no read form have no gold text in scope. There the refit on pool rows reads +.25 (+.08 to +.43).

Written order: on 110 census forms whose atoms move in a random valid order, the refit with no lexical facts saves +.42 (+.26 to +.58) in written order and +.04 (-.10 to +.16) in random order. A refit on random order rows reads +.52 (+.30 to +.77) on 566 random order pool picks, and +.17 (-.14 to +.48) on the 25 forms that moved there.

Not done: walks of 229 wide pool points and 105 wide parents points, all at the end of budget, and a union refit on random order rows.
