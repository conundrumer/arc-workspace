# Prediction

Written before any fit, with no read of a target against a fact.

- Saving on forms at 25 bits or more, on the best single target: about .7 bits per form (.2 to 1.5), under the 2 bit bar.
- The component of an INIT saves most per form at about .5 to 1 bit, as `component` is 3.7 bits per INIT.
- Head column types and row shapes save more against what the pool proposes than against gold's marginal, because the pool's mix of heads differs from gold's by kind alone.
- Output-need facts carry under half of the saving. Earlier results find that general facts of a scope or a grid give little, so the need facts have to carry a new signal to beat that.
- Late forms gain more than early forms: a need that nears 0 says "write the paint form".

# Numbers for the bars, written after the dev read and before the held read

- Primary: the component pick and the relation picks of one form on one census walk, saved at forms of 25 bits or more, tier need+foundset. This is an exact change of the census's bits, and no fact in this tier reads gold's order.
- Upper bound: the same read, tier all, with facts of the last form written. A pool has no such order.
- Joint read of component, columns and both row shapes: `content`, against its marginal on fit tasks. It is state information only, and the steered prior may already hold part of it.
- From the dev read, the prediction for held: primary about +.25 (under the .5 bar), upper bound about +1.3 (under the 2 bit bar), need facts adding about a sixth of the primary.
