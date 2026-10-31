# e9614598 create: progress notes

- interference: command `run_dl.py <task_id>` in [Pace](#pace). A pairs run that passes every pair but prints a lint finding exits non-zero, so the `&&`-joined copy to `last-pass.dl` did not run during Develop. A bad edit of mine then garbled the solver, and no backup stood to restore it from; I rebuilt it from the garbled text. Cost: about 1 min. The output was right; the gap in the backup no longer holds, as later runs passed lint and wrote `last-pass.dl`.
