// C++ functors backing the dispatch/projection primitives in lib.dl.
//
// Each performs the orientation dispatch (Dir / Axis / D4) in C++, letting its
// lib.dl wrapper be a single clause; lib.dl covers why that matters (it bounds
// the generated IR path count).
//
// All functors return plain `number` and are stateless (no SymbolTable* /
// RecordTable* args). A functor that *returned a Position record* would be
// unusable here: these wrappers are `inline`, and a record produced by a
// functor cannot be destructured downstream after inline substitution — the
// grounding analysis can't unify a record pattern against an opaque functor
// call. So the wrappers reassemble Positions as Datalog record literals
// `[@f(...), @f(...), ...]`, filling each slot from a number functor.
//
// Constants mirror lib.dl's disjoint #define ranges (Dir 10-13, Axis 20-21,
// D4 50-57).
//
// Build: see build_functors() in run_dl.py (auto-built; artifact gitignored).

#include "souffle/SouffleFunctor.h"

using souffle::RamDomain;

#define TOP    10
#define BOTTOM 11
#define LEFT   12
#define RIGHT  13

#define VERTICAL   20
#define HORIZONTAL 21

#define IDENTITY      50
#define ROT_CW        51
#define ROT_180       52
#define ROT_CCW       53
#define FLIP_LR       54
#define FLIP_TB       55
#define FLIP_DIAG     56
#define FLIP_ANTIDIAG 57

extern "C" {

// dist: distance from p to edge d — the slot named by Dir d.
RamDomain dist_proj(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case TOP:    return t;
        case BOTTOM: return b;
        case LEFT:   return l;
        case RIGHT:  return r;
    }
    return 0;
}

// "keep when": v if the selector equals the target, else 0. Places a value in
// the slot(s) matching an orientation and zeroes the rest. Two variants by
// selector type — a single `number`-typed functor would force Souffle to infer
// the typed selector variable (Dir / Axis) as plain `number`, breaking the
// wrapper head's declared type. keep_dir assembles edge_delta; keep_axis assembles
// split and the outer/inner records of divide / divide_by_size / concat.
RamDomain keep_dir(RamDomain sel, RamDomain target, RamDomain v) {
    return sel == target ? v : 0;
}
RamDomain keep_axis(RamDomain sel, RamDomain target, RamDomain v) {
    return sel == target ? v : 0;
}

// Axis projection: the near (lower-index) and far (higher-index) slots along
// axis a. VERTICAL → (t, b); HORIZONTAL → (l, r).
RamDomain axis_near(RamDomain a, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    return a == VERTICAL ? t : l;
}
RamDomain axis_far(RamDomain a, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    return a == VERTICAL ? b : r;
}

// apply: D4 transform of a Position, one functor per output slot — the
// eight D4 gather permutations of (t, b, l, r).
RamDomain apply_t(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case IDENTITY:      return t;
        case ROT_CW:        return l;
        case ROT_180:       return b;
        case ROT_CCW:       return r;
        case FLIP_LR:       return t;
        case FLIP_TB:       return b;
        case FLIP_DIAG:     return l;
        case FLIP_ANTIDIAG: return r;
    }
    return 0;
}
RamDomain apply_b(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case IDENTITY:      return b;
        case ROT_CW:        return r;
        case ROT_180:       return t;
        case ROT_CCW:       return l;
        case FLIP_LR:       return b;
        case FLIP_TB:       return t;
        case FLIP_DIAG:     return r;
        case FLIP_ANTIDIAG: return l;
    }
    return 0;
}
RamDomain apply_l(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case IDENTITY:      return l;
        case ROT_CW:        return b;
        case ROT_180:       return r;
        case ROT_CCW:       return t;
        case FLIP_LR:       return r;
        case FLIP_TB:       return l;
        case FLIP_DIAG:     return t;
        case FLIP_ANTIDIAG: return b;
    }
    return 0;
}
RamDomain apply_r(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case IDENTITY:      return r;
        case ROT_CW:        return t;
        case ROT_180:       return l;
        case ROT_CCW:       return b;
        case FLIP_LR:       return l;
        case FLIP_TB:       return r;
        case FLIP_DIAG:     return b;
        case FLIP_ANTIDIAG: return t;
    }
    return 0;
}

}  // extern "C"
