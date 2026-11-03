# Prediction

Written before any fit, with no read of a target against a fact.

- Primary, component pick and relation picks on one census walk, reader given with the read atom masked, forms at 25 bits or more: about +.8 bits per form (.3 to 1.6). That is between the two bars, so neither the steer bar nor the close bar.
- Head columns save most per form against their marginal, at about 1.5 to 2.5 bits, because the reader's join sites give the type of a column.
- Depth 1 is mostly a paint form, so its targets start cheap and save little. The best saving per form sits at depth 2 and 3.
- The output need at OUT adds under a quarter of what the reader's body gives once depth is above 1.
- Need per candidate beats need per state by about .5 bits per form, mostly at depth 1 and 2, and on RULE forms that read a table with Position and Color.

# Numbers for the bars, written after tuning on fit tasks and before the held read

- Fit fold 0 tilt, with models fit outside that fold: relation picks of RULE and DET forms save .43 bits per form, relation picks of INIT forms save 1.69 (`gamma-reads-RULE-DET.json`, `gamma-reads-INIT.json`). The component cuts from 3.76 to 1.88 bits on INIT and from 3.40 to 1.90 on DET on fit folds.
- Held is outside the fit distribution, so I expect about two thirds of that. Primary, forms at 25 bits or more: about +1.2 (.7 to 1.8), under the 2 bit bar and over the .5 bar.
- Without the reader's columns, `body` tier: about +.7.
- Output need adds nothing on top of the reader: on fit, the `full` tier's greedy pick took no output key on any of 6 targets.
- Need per candidate from the output alone, the arm a forward search has: about +.05 bits per form. Fit a hole, and the candidate pick saves about 1.3 bits per form, mostly from column types.
