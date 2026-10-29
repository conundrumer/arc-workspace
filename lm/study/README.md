# LM data study

The live study sources and documents are here. [Moved files](MOVED_FILES.md)
lists the source inventory. [Plan](plan.md) describes the pipeline.

`study_paths.CODE_ROOT` names this directory in the current checkout.
`study_paths.DATA_ROOT` names `work/lm/data-study` in the repository's main
worktree, found with `engine.checkout.main_worktree`. Databases, corpora,
runtimes, immutable reader snapshots, native blocks, replay artifacts, thread
state and logs stay there. A source dependency stays relative to its module.

Start a new owner with:

```sh
bash lm/study/codex-adm/newthread.sh <owner> <request-id> <brief-file> [writable-root ...]
```

The launcher calls `scripts/change_worktree.py --name <owner>` and starts the
thread in that worktree, with the shared data root also writable. It stores the
thread ID and writable roots in the data directory. Send messages with
`lm/study/codex-adm/send.sh`; owners and handovers remain in the data directory.
Changes land through `scripts/merge_change.py`.

Run entry points with the existing study runtime, for example:

```sh
S=$(python3 lm/study/study_paths.py)
"$S/ast/run/runtime-5ee2f066/venv/bin/python" -B lm/study/ast/run/corpus.py --help
```

The corpus runner's new `SOURCES.repository.json` authenticates these repository
sources. Original source receipts and stored runtime/config/result manifests
are preserved in the data directory. Changed source paths and hashes produce
new receipts; they do not authorize resuming an output with incompatible
configuration or accepting an old proof as a proof of the migrated code.

Judge document templates substitute `@STUDY_CODE_ROOT@` when rendered, so new
documents name this checkout's tool and specification. Generated documents and
review recordings stay under the shared data root. Existing threads and
processes require coordinator handoff to the repository entry points.
