# Normal-form owner handover

The coordinator's retry finished with mutants normal 100,331, non-normal 11,448, unavailable 4,605; gold points normal 14,393, non-normal 100, unavailable 43. Read-only grouping: mutants projection-only 3,919, layout/entries-only 630, both 56; gold points projection-only 18, layout/entries-only 25. These groups were added to the data summary.json with a pending-repair note. No retired source under S was edited.

Source/metadata review found adapter defects: trailing INIT SKIP tokens can become a prefix to the next RULE in CaseRows' declaration scanner; the parquet width helper treats native Position/Offset aliases as scalars; full gold replay can be empty while the point-prefix snapshot holds the needed tables. The worktree fixes form spans, uses canonical native widths, and consults both stored gold snapshots through CaseRows. A complete mapped multi-row observation rules out one-row; missing evidence remains explicit. No native/program evaluation or tests were run. Bounded metadata inspection demonstrated correct rule headers/spatial spans and available prefix tables behind empty full replays.

The width defect can affect earlier classified row-dependent attributes. Unavailable-only retry cannot repair those. Current classifier class hashes deliberately fail legacy compatibility. After merge run:

```sh
/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python /Users/davidlu/code/arc-workspace/model/study/ast/run/mech2/classify_normal.py
```

This computes the normal attribute from stored streams and rows, without relabeling the base or replaying programs. Structural cases avoid row acquisition and carry row_independent. New output has source/entry receipts, exclusive cause counts, explanations, and pre-repair counts. Missing/faulted relations or stopped/count-only entries can be intrinsically insufficient; unresolved mapping remains an adapter limitation. Current generic diagnostics do not establish any of the 4,648 rows as intrinsically undecidable.

Open work: merge, coordinator run, inspect concrete remaining causes, publish corrected counts. Owner notice sent to n-mech as 7710007. Next request ID: 7710008.

Git staging/commit were blocked at the main repository .git/worktrees/n-mech2/index.lock. Changes remain uncommitted. Proposed commit message: Fix normal-form native spans and prefix mapping; report unavailable causes.
