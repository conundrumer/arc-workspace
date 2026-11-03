# Prediction, written before any held read

Tune on fit tasks gives, for RULE atoms against the marginal: scope only .31, the other atoms as a set .99, the same with join structure 1.31 and 1.37 on two folds, with open labels and unread forms 1.57.

Primary: RULE atoms, tier `dag`, penalty 30.

- Held primary: 1.1, between .9 and 1.3. Held tasks are in the eval set and on another gold revision, so a drop from tune is likely.
- Control: within .02 of 0.
- Order: restored on the same rows it adds about .3, about a fifth of the gain.
- The three named pairs hold in both directions as a set: `compose` with `perp`, `neighbor` with `dir8_elem`, `inside` with `BoundingBox.box`.
- INIT about 1.8, DET about .7.
- By class: macro and lib gain most, fact least.

These tiers read a full body with one atom missing. So a search with half a body has less, and the 1 bit bar on this read is a bound from above on what a steer can read. The baseline is a marginal, and the record's +.39 is against the steered prior, so the two numbers don't compare.
