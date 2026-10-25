# d8e07eb2 progress notes

- delay: `uv run python scripts/run_dl.py audit d8e07eb2` stopped at `timeout 120` (exit 124) with 16 witnessed cases of 4096. It cost about 2 minutes and gave no audit findings. The audit stays unrun.
- interference: `uv run python scripts/run_dl.py store d8e07eb2` printed about 30 store points (card_panel, cut_axis, divider, outer, panels.*, runs.node, band_order.*, card_band and others). [Develop](docs/handbook/create.md#develop) step 4, "Hold as a branch each of these", would hold every one of them. That is not doable within the run budget. It cost one extra read of a 120 KB output. Only the four store points that `analyze.md` gives witnesses for are held, and that is still the case.
- delay: the pairs run grew from 2 s to about 60 s once the four `@store` lines and the `@derive` line were added (4096 cases before witness filtering). Every later `run_dl.py` command took 30 to 110 s.
