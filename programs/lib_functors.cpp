// C++ functors backing the dispatch/projection primitives in lib.dl.
//
// Each performs the orientation dispatch (Dir / Axis / D4) in C++, letting its
// lib.dl wrapper be a single clause. One clause bounds the generated IR path
// count: a multi-clause inline contributes xN to every rule that calls it,
// because the dispatch value comes from a relation and Souffle can't prune the
// impossible combinations.
//
// All functors return plain `number` and are stateless (no SymbolTable* /
// RecordTable* args). A functor that *returned a Position record* would be
// unusable here: these wrappers are `inline`, and a record produced by a
// functor cannot be destructured downstream after inline substitution — the
// grounding analysis can't unify a record pattern against an opaque functor
// call. So the wrappers reassemble Positions as Datalog record literals
// `[@f(...), @f(...), ...]`, filling each slot from a number functor. Guards
// and arithmetic stay in Datalog inside the single clause.
//
// Constants mirror lib.dl's disjoint #define ranges (Dir 10-13, Axis 20-21,
// DiagDir 30-33, D4 50-57).
//
// Build: see build_functors() in run_dl.py (auto-built; artifact gitignored).

#include "souffle/SouffleFunctor.h"

using souffle::RamDomain;

#define DIR_T 10
#define DIR_B 11
#define DIR_L 12
#define DIR_R 13

#define AXIS_V 20
#define AXIS_H 21

#define DIAG_TL 30
#define DIAG_TR 31
#define DIAG_BL 32
#define DIAG_BR 33

#define D4_ID 50
#define D4_CW 51
#define D4_HT 52
#define D4_CC 53
#define D4_LR 54
#define D4_TB 55
#define D4_DG 56
#define D4_AD 57

extern "C" {

// dist: distance from p to edge d — the slot named by Dir d.
RamDomain dist_proj(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case DIR_T: return t;
        case DIR_B: return b;
        case DIR_L: return l;
        case DIR_R: return r;
    }
    return 0;
}

// "keep when": v if the selector equals the target, else 0. Places a value in
// the slot(s) matching an orientation and zeroes the rest. Two variants by
// selector type — a single `number`-typed functor would force Souffle to infer
// the typed selector variable (Dir / Axis) as plain `number`, breaking the
// wrapper head's declared type. keep_dir assembles edge_delta; keep_axis assembles
// split and the outer/inner records of divide / divide_by_size / concat.
//
// keep_dir's selector is a Dir8: a corner is its two cardinal edges, so a
// DiagDir sel matches either of those targets and edge_delta places v at both.
RamDomain keep_dir(RamDomain sel, RamDomain target, RamDomain v) {
    switch (sel) {
        case DIAG_TL: return (target == DIR_T || target == DIR_L) ? v : 0;
        case DIAG_TR: return (target == DIR_T || target == DIR_R) ? v : 0;
        case DIAG_BL: return (target == DIR_B || target == DIR_L) ? v : 0;
        case DIAG_BR: return (target == DIR_B || target == DIR_R) ? v : 0;
    }
    return sel == target ? v : 0;
}
RamDomain keep_axis(RamDomain sel, RamDomain target, RamDomain v) {
    return sel == target ? v : 0;
}

// Axis projection: the near (lower-index) and far (higher-index) slots along
// axis a. AXIS_V → (t, b); AXIS_H → (l, r).
RamDomain axis_near(RamDomain a, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    return a == AXIS_V ? t : l;
}
RamDomain axis_far(RamDomain a, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    return a == AXIS_V ? b : r;
}

// apply: D4 transform of a Position, one functor per output slot — the
// eight D4 gather permutations of (t, b, l, r).
RamDomain apply_t(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case D4_ID: return t;
        case D4_CW: return l;
        case D4_HT: return b;
        case D4_CC: return r;
        case D4_LR: return t;
        case D4_TB: return b;
        case D4_DG: return l;
        case D4_AD: return r;
    }
    return 0;
}
RamDomain apply_b(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case D4_ID: return b;
        case D4_CW: return r;
        case D4_HT: return t;
        case D4_CC: return l;
        case D4_LR: return b;
        case D4_TB: return t;
        case D4_DG: return r;
        case D4_AD: return l;
    }
    return 0;
}
RamDomain apply_l(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case D4_ID: return l;
        case D4_CW: return b;
        case D4_HT: return r;
        case D4_CC: return t;
        case D4_LR: return r;
        case D4_TB: return l;
        case D4_DG: return t;
        case D4_AD: return b;
    }
    return 0;
}
RamDomain apply_r(RamDomain d, RamDomain t, RamDomain b, RamDomain l, RamDomain r) {
    switch (d) {
        case D4_ID: return r;
        case D4_CW: return t;
        case D4_HT: return l;
        case D4_CC: return b;
        case D4_LR: return l;
        case D4_TB: return r;
        case D4_DG: return b;
        case D4_AD: return t;
    }
    return 0;
}

}  // extern "C"
