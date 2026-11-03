# Prediction, written before any held read

Primary model: `final-hyb-noorder`. Lib relations, facts and operators are keys by name. Derived options are keys by the family of their form, and may split on their own component or relation key. Depth 4 trees, without reader counts or form order. The other final models give per-key tables and the comparison.

- Primary, all picks: +.40 (range +.30 to +.50). Gold alive: +.37. It stays under 1 bit and over .3.
- Same arm with reader counts and form order: +.48.
- Class: lib about +.8, derived about +.45, rest about +.25, own about 0.
- Relation-level keys, primary fact set: about +.38.
- Keys that pass 1 bit at gold picks with a lower limit above 0: about 12 lib relations, covering about 12% of picks. Net of what a key's model costs at other picks: 3 or fewer.
- Control on a label drawn from the prior: about -.03, with no key net over 1 bit.
