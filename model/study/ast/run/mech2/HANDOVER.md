# Normal-form owner handover

The repository copy now includes the table identity and atomic setup repair, unavailable-only retry, and mixed-producer read adapter. The refresh patch was applied after changing its paths to `model/study`. No retired source under S was edited during this migration turn. Data outputs remain under `study_paths.DATA_ROOT/ast/run/mech2`.

The initial coordinator run reported mutants normal 87,512, non-normal 997, unavailable 27,875; gold points normal 13,009, non-normal one, unavailable 1,526. Read-only inventory identified 2,658 missing-table errors and 25,217 missing-tabs errors. The repair supplies the writer interface's explicit table IDs and finishes setup before caching objects. The coordinator's retry result is still pending.

The migration compatibility receipt permits only the reviewed legacy manifest hashes, exact migrated dependencies, and the repaired classifier class ASTs. Existing classified rows retain their producer hashes. Syntax parsing and source comparisons were performed; no classification, evaluation, or tests were launched here.

After merge, the coordinator can run:

```sh
/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python /Users/davidlu/code/arc-workspace/model/study/ast/run/mech2/classify_normal.py --retry-unavailable
```

Review the returned counts and any remaining unavailable reasons before reporting completion. The read-only consumer remains `read_normal.load_normal`. Next owner message request ID is 7710007. The earlier codex-adm handover under S is historical; update this worktree file going forward.

Git staging and committing were blocked because the sandbox could not create `.git/worktrees/n-mech2/index.lock` in the main repository. The worktree changes remain uncommitted. Proposed commit message: `Fix normal-form stored table adapter and preserve results across study migration`.
