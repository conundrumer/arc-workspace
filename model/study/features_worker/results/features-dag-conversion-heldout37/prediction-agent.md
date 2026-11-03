# Prediction, written before any fit of items 9 and 10

Written 2026-11-01, before any fit on fit rows, any tune read on `test-parents` and any held read of this conversion. Amended once: see "Amendment". Before the amendment the scripts ran in mechanical smoke tests on `dev-cut` rows (4 to 25 rounds, fit and read on the same dev tasks, so in-sample). Those runs checked that the code works, and their numbers are not reads and did not set a number below.

Rows when written: the walks of `held-parents`, `held-cut` and `dev-cut` were partly walked. No row of `fit-cut`, `test-parents` or `test-cut` existed in the new format.

Terms: `off` is the walk under `live.Sampler(models, ())`. `live` is the walk under the steers in use. "Saved over off" is the mean of `q_bits(off)` less the model's bits at the same pick keys. "Saved over live" is the mean of `q_bits(live)` at the same pick keys, less the model's bits. A pick weighs its count of walks over the form's finished walks. Intervals are 95% from 10,000 resamples of tasks.

## Bars (from the design)

- Over `live`, 1 bit per pick makes a read the next steer. Under .3 closes it. Between the two, it stands as a finding. Content adds its own row.
- Per-relation read: the same bars on gold-alive picks. Keys past 1 bit net are listed.
- A control on a label drawn from the offset reads 0 within its interval, and no key passes under it.
- Per form: mean over a form's orders of the sum over a walk's picks, on forms at 25 bits or more by `bits_mean` under `live`, with forms under 25 beside.

## Amendment

After the first version of this file, the offsets of the partial `held-parents` rows were compared. This reads the two priors and no model. On the 5,777 RULE pick keys (79% of the weight) that both the `off` and the `live` walks have reached, the `off` prior costs 5.15 bits per pick and the `live` prior costs 3.53. The steers in use are worth 1.6 bits per pick over `off`, and a model that starts at `off` must make up that gap before it gains over `live`. The first version put "saved over off" at +.5 and "saved over live" at +.1, which cannot both hold with a gap of 1.6. The numbers below replace those.

## Rank refit (item 9), on `held-parents` RULE picks

Offset: `lq` of `off`. Fit on `fit-cut` RULE, tuned by task folds of the 161 test tasks on `test-parents`.

- Structure arm, saved over `off`, all picks: +1.1 (+.8 to +1.4). The facts of the pick (option kind, dead by join, whether the option's relation stands in D, the option's form depth, `d_depth`, the sparse tokens of D) recover most of what the steers add, and not all of it: the steers were fit with written order facts and with the columns of the scope's types, and this fit has no scope types (see Limits).
- Structure arm, saved over `live`: -.5 (-.8 to -.2). The model stays under the steers in use. It reads under the .3 bar, so the rank read closes as a next steer.
- Content arm over structure: +.03 (-.03 to +.10). The old rank read gave +.006.
- Control, over `off`: 0 (-.03 to +.03).
- By class, saved over off: derived in scope and the form's own atom recover the most (+1.2 to +1.6); lib relation the least (+.3 to +.8). By `d_depth` band 0, 1, 2, 3+: the lowest at band 0, where D is empty and the pick has the fewest facts.
- Per form, at 25 bits or more: a sum of about +6 bits over `off`, as such forms carry 7 to 12 picks. Over `live` the sum is negative, about -3 bits. The count of forms that the model takes under 25 bits against `live` is zero or near it.

## Per-relation refit (item 10), on `held-parents` RULE picks, gold-alive

- Primary (`hyb`), saved over `off`: +1.2 (+.9 to +1.5). Over `live`: -.4 (-.7 to -.1). Under the .3 bar.
- Per component and per lib section: each under the primary by .05 to .2.
- Per relation, keys: the keys with net over 1 bit stand among the derived `init:` and `rule:` keys of the most common components, and a few lib relations. 4 to 10 keys, since the gap to `off` is 1.6 bits.
- Control: 0 (-.05 to +.05), and no key passes under it.
- What the models learn, as pairs from D: `prefix:` tokens that name a relation the option's relation joins on, `ddepth` thresholds, and `scope:` tokens. No token reads order, as `check_tokens` guarantees.

## Limits that bound what these reads can show

- The pick rows hold `nscope`, the count of columns in scope, and not their types. The columns `hit`, `hit_frac`, `none_in_scope`, `new_types`, `col*_in_scope` and `scope_n_*` are therefore constant (-1 or 0) in these arrays, and a fit cannot split on them. The old fits had them. A model without them can read lower than a model with them. If the prediction above fails low, this is the first suspect.
- `dead by join` is not a function of the pick key on 3.5% of picks (it reads the scope's types as a set, and those differ with the walk order inside an OR). The array keeps the first walk's flag.
- Walks are in valid orders, `K` per form. A form with one valid order weighs as much as a form with 8.

## First pass on partial dev rows (written after the amendment, before any fit on fit rows)

`dev-cut` off rows of 21 tasks (one shard of three, 3,434 picks), structure arm, 60 rounds, 4 task folds, fit on the other folds and read on the fold: +.77 bits per pick over `off`, and still rising at 60 rounds (+.60 at 20, +.72 at 40). The `live` prior costs 3.87 bits against 5.39 for `off` on the same picks, so this model sits about .7 bits under `live`. The amended numbers above stand.
