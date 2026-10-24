# cc9053aa create progress

- delay: `uv run python scripts/run_dl.py derive cc9053aa` took 119 s and printed the same Souffle warning block twelve times, once per killed run (exit -9) of `marker_color=DominantColor`, `marker_color=SharedColor` and `marker_color=VanishedColor`, and judged none of them. Under each of these derivations every background cell, or every input color, is a marker, so the per-marker trips and their walk enumerations blow up. Cost: about two minutes and a long output to read. The three derivations are dismissed by hand with `@ignore: derive` lines.
