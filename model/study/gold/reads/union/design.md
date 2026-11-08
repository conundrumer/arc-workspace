# Union gold

Every case of each task's solver, each as a one-case program, and the union of their tables, each union table with its reads and depth in each case, one union table for each QueryHash.

## Cases

A task's cases are the `cases` of its record in the latest empty-gold publication that holds it (`gold_case_counts.py` in this folder gives which; in a round, the line that the round's selection names). The solver's `exclude` forms in its `.arcdata` file already leave out the excluded cases, since the engine's case catalog takes them out. A case's program is its `filtered_program`, or its `original_program` where that is empty. The pinned program (`gold-v3-combined-cut/view-final`) is one more program of the task, named `pinned`. It is the cut text of one case.

Two programs are the same when their texts are equal after labels are renamed in order of definition. Each distinct program is read once, and the record lists every case it stands for.

A program that doesn't parse, or that doesn't solve the task, is left out, with the reason. A program solves the task when it fits and its test outputs are given:
- It fits when some assignment of its DETs gives every train output through its OUT query.
- Its test outputs are given when, on each test example that has an expected output, the fitting assignments give at most two distinct grids over all constraint models, and one of them is the expected output.

`gold_union_fits.py` judges each distinct program text on the current engine and writes `fits-SET.jsonl`: one line per task, with, for each program text, its cases, the number of assignments of the OUT table, the number that fit (`fitting`), `fit`, `test_ok` and `why` (the reason where the program gives no tables). The text is matched by the first 16 hex digits of its sha256. The union keeps a program when `fit` and `test_ok` are true. Its reason when it is left out is `no assignment fits` or `test output not given`, or `why`. A program whose text has no line in the file is left out with `no fits row`, and a task with no line has the error `no fits row`. If the pinned program is left out, the task has the error `pinned: no assignment fits`.

## Forms and tables

A form's identity is its text with each read replaced by the identity of the form it reads, recursively, and its own label dropped. Forms of equal identity make equal tables, so they are one table without a replay.

The QueryHash of a form is `query_hash(scope, text)` (`model/study/samples/query_hash.py`, on the engine of `gold_union_env.sh`), where `scope` is the lines before the form in its program's normal form. In a union row, forms of equal QueryHash make one union table, and forms of different QueryHash are separate union tables. A form that the engine refuses keeps its own union table, with `query` null, and its key is in the row's `unhashed`. `gold_union.py` hashes a form in the first program that holds it and in one other, and the task gets the error `QueryHash conflict` if the two QueryHashes differ. Every row has `merged: query_hash` and `query_hash_version`, the engine that hashed. The union graph (`gold_union_graph.py`) then joins union tables whose maps from assignment to TableHash are equal, with DETs of different QueryHash paired by equal sets of value hashes.

A union table has:
- `key`: the least index, among the identities of its QueryHash, in order of first appearance with the pinned program first.
- `query`: its QueryHash.
- `forms`: the text of each identity of its QueryHash.
- `cases`: the cases whose program makes it, and whether the pinned program makes it.
- `kind`, and `component` for INIT.
- `reads`: for each identity, the keys of the union tables it reads.
- `depth`: the least depth over its identities, counted from 0 for a form that reads no form, and `depths`, the set of depths over its identities.

## Output

Each shard writes `union-K.jsonl`, one line per task: `task`, `set`, `cases` (with the distinct program each maps to), `left_out` (programs with reasons), `tables`, `merged` (`query_hash`), `query_hash_version`, `unhashed`. Then `merge` writes `union.jsonl` in task order, and its sha256 in `union.jsonl.sha256`.

Rows stream, one task at a time, and a restart skips tasks it has. A task past 5 min or 4 GiB gets a `set_aside` line.

## Code stamp

Each output in this folder records the code that made it, as `{"sha": HEAD, "dirty": bool}` (`gold_union_code.py`). `dirty` is true when a file under `model/study/gold/reads/union` or `src/arclog_convert` differs from HEAD.
- `fits-SET.jsonl`: the first line is `{"t": "header", "code": ...}`. A reader skips the lines that have `t` (`gold_union_fits.rows_of`).
- `union-SET.manifest.json`: the key `code`.
- Any other output (`union-keys-SET.jsonl`, `graph-*-SET.jsonl`): the file `<output>.code.json`, `{"code": ...}`.

## File form

A large output of the stages is a zstd stream, `NAME.jsonl.zst`: a sequence of independent frames, each of whole rows, written as the rows go out, so a reader can read a file that a stage still writes. Every stage reads a file through `model/study/study_zst.py`, which reads `NAME.jsonl.zst` and a plain `NAME.jsonl` alike, and where both exist reads the one modified last. A name in this document is the logical name, without `.zst`. A `NAME.jsonl.sha256` holds the sha256 of the text, and `NAME.jsonl.code.json` keeps the logical name too.

## Check against a grammar

`gold_union_grammar_check.py` decodes each distinct program text of `cases-SET.jsonl` on an engine (as `gold_union_fits.sampler_decode` does: the reader and `Session.check_stream`, no table evaluated) and lists the tasks and cases the engine's grammar refuses, with each reason. Its output, `grammar-SET[-K].jsonl` in a folder of its own, is one line per task, written as the task is checked; a restart skips the tasks it has. The tasks it names are the tasks whose gold must be made again, by the conversion of the solver and a publication, on that engine.

`runs/strip_tasks.py` removes the lines of tasks from the shard files of a folder, `.zst` or plain, before the stages take those tasks again. A task that a shard of an earlier batch still holds is skipped by the union stage, and a merge can take the older line, as the shard names sort as text.

## Search programs

Search-found right programs are not gold. They go to `search-programs.jsonl`, one line per program: task, source file, line, the program pruned to the forms OUT reads, and which test attempts are right.
