# progress-create

- delay: `uv run python scripts/run_dl.py e6721834`, the first pairs run. Every pair reached the runner's 20 s limit, and the run took 38 s. The cause was `TiebreakResolutions` over the object half taken as the dot half: under `$MatchShapeOnly` & `$MarksByDotColor`, each of about 40 rectangle cells had 5 candidate marks, so the product of candidates grew without bound. The `crowded` gate, marked `@workaround`, fixed it. It cost one run and one edit.
