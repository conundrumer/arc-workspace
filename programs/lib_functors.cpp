// C++ functors backing the box algebra in lib/box.dl.
//
// Each functor is a function over Box records: it unpacks its arguments
// through the record table, computes, and packs the result. The lib.dl
// primitives are one-clause wrappers over these calls, so a chain of
// primitives in one rule inlines to one nested call per link.
//
// A record a functor returns cannot be destructured in the same rule:
// Souffle cannot ground a record pattern against a functor call. The
// wrappers read every record through a functor, never through a pattern.
//
// Constants mirror lib/orientation.dl's disjoint #define ranges (Dir 10-13,
// Axis 20-21, DiagDir 30-33, D4 50-57).
//
// Build: see build_functors() in run_dl.py (auto-built; artifact gitignored).

#include "souffle/RecordTable.h"
#include "souffle/SouffleFunctor.h"

using souffle::RamDomain;
using souffle::RecordTable;
using souffle::SymbolTable;

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

namespace {

// The margins of a box: (t, b, l, r).
struct Margins {
    RamDomain t, b, l, r;
};

Margins margins(RecordTable* rt, RamDomain box) {
    const RamDomain* m = rt->unpack(box, 4);
    return {m[0], m[1], m[2], m[3]};
}

RamDomain box(RecordTable* rt, Margins m) {
    return rt->pack({m.t, m.b, m.l, m.r});
}

// The near and far margins along an axis: (t, b) on V, (l, r) on H.
RamDomain near(Margins m, RamDomain a) { return a == AXIS_V ? m.t : m.l; }
RamDomain far(Margins m, RamDomain a) { return a == AXIS_V ? m.b : m.r; }

// A box with near and far along axis a, zero across.
Margins axis_only(RamDomain a, RamDomain near, RamDomain far) {
    return a == AXIS_V ? Margins{near, far, 0, 0} : Margins{0, 0, near, far};
}

// Whether Dir8 d has edge `edge`: a cardinal is its own edge, a corner has
// two.
bool has_edge(RamDomain d, RamDomain edge) {
    switch (d) {
        case DIAG_TL: return edge == DIR_T || edge == DIR_L;
        case DIAG_TR: return edge == DIR_T || edge == DIR_R;
        case DIAG_BL: return edge == DIR_B || edge == DIR_L;
        case DIAG_BR: return edge == DIR_B || edge == DIR_R;
    }
    return d == edge;
}

Margins edge_inset(RamDomain d, RamDomain k) {
    return {has_edge(d, DIR_T) ? k : 0, has_edge(d, DIR_B) ? k : 0,
            has_edge(d, DIR_L) ? k : 0, has_edge(d, DIR_R) ? k : 0};
}

// Whether p decomposes into size-k tiles with gap g along a, and its tile
// index and in-tile offset when it does.
struct Tiling {
    bool ok;
    RamDomain n, outer, inner, k;
};

Tiling tiling(Margins m, RamDomain a, RamDomain k, RamDomain g) {
    RamDomain period = k + g;
    if (period <= 0) return {false, 0, 0, 0, k};
    RamDomain ext = near(m, a) + far(m, a) + 1;
    if ((ext + g) % period != 0) return {false, 0, 0, 0, k};
    RamDomain inner = near(m, a) % period;
    if (inner >= k) return {false, 0, 0, 0, k};
    return {true, (ext + g) / period, near(m, a) / period, inner, k};
}

}  // namespace

extern "C" {

RamDomain box_compose(SymbolTable*, RecordTable* rt, RamDomain a, RamDomain b) {
    Margins x = margins(rt, a), y = margins(rt, b);
    return box(rt, {x.t + y.t, x.b + y.b, x.l + y.l, x.r + y.r});
}

RamDomain box_relative(SymbolTable*, RecordTable* rt, RamDomain base, RamDomain x) {
    Margins b = margins(rt, base), p = margins(rt, x);
    return box(rt, {p.t - b.t, p.b - b.b, p.l - b.l, p.r - b.r});
}

RamDomain box_inside(SymbolTable*, RecordTable* rt, RamDomain a, RamDomain b) {
    Margins x = margins(rt, a), y = margins(rt, b);
    return x.t >= y.t && x.b >= y.b && x.l >= y.l && x.r >= y.r;
}

RamDomain box_interior(SymbolTable*, RecordTable* rt, RamDomain a, RamDomain b) {
    Margins x = margins(rt, a), y = margins(rt, b);
    return x.t > y.t && x.b > y.b && x.l > y.l && x.r > y.r;
}

RamDomain box_dist(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain d) {
    Margins m = margins(rt, p);
    switch (d) {
        case DIR_T: return m.t;
        case DIR_B: return m.b;
        case DIR_L: return m.l;
        case DIR_R: return m.r;
    }
    return 0;
}

// Taxicab distance to corner diag: the sum of its two edge distances.
RamDomain box_corner_dist(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain diag) {
    Margins m = margins(rt, p);
    switch (diag) {
        case DIAG_TL: return m.t + m.l;
        case DIAG_TR: return m.t + m.r;
        case DIAG_BL: return m.b + m.l;
        case DIAG_BR: return m.b + m.r;
    }
    return 0;
}

RamDomain box_axis_dim(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain a) {
    Margins m = margins(rt, p);
    return near(m, a) + far(m, a) + 1;
}

RamDomain box_along(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain a) {
    Margins m = margins(rt, p);
    return box(rt, axis_only(a, near(m, a), far(m, a)));
}

RamDomain box_across(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain a) {
    Margins m = margins(rt, p);
    RamDomain other = a == AXIS_V ? AXIS_H : AXIS_V;
    return box(rt, axis_only(other, near(m, other), far(m, other)));
}

RamDomain box_centered(SymbolTable*, RecordTable* rt, RamDomain p) {
    Margins m = margins(rt, p);
    return m.t == m.b && m.l == m.r;
}

// The two positions agree on the distances to the two edges of corner diag.
RamDomain box_corner_anchor(SymbolTable*, RecordTable* rt, RamDomain diag, RamDomain p1,
                            RamDomain p2) {
    Margins a = margins(rt, p1), b = margins(rt, p2);
    switch (diag) {
        case DIAG_TL: return a.t == b.t && a.l == b.l;
        case DIAG_TR: return a.t == b.t && a.r == b.r;
        case DIAG_BL: return a.b == b.b && a.l == b.l;
        case DIAG_BR: return a.b == b.b && a.r == b.r;
    }
    return 0;
}

RamDomain box_edge_inset(SymbolTable*, RecordTable* rt, RamDomain d, RamDomain k) {
    return box(rt, edge_inset(d, k));
}

RamDomain box_axis_inset(SymbolTable*, RecordTable* rt, RamDomain d, RamDomain k1,
                         RamDomain k2) {
    RamDomain opp = d == DIR_T ? DIR_B : d == DIR_B ? DIR_T : d == DIR_L ? DIR_R : DIR_L;
    Margins a = edge_inset(d, k1), b = edge_inset(opp, k2);
    return box(rt, {a.t + b.t, a.b + b.b, a.l + b.l, a.r + b.r});
}

RamDomain box_jump_offset(SymbolTable*, RecordTable* rt, RamDomain d, RamDomain k) {
    Margins e = edge_inset(d, k);
    return box(rt, {e.b - e.t, e.t - e.b, e.r - e.l, e.l - e.r});
}

RamDomain box_apply(SymbolTable*, RecordTable* rt, RamDomain d, RamDomain p) {
    Margins m = margins(rt, p);
    switch (d) {
        case D4_ID: return p;
        case D4_CW: return box(rt, {m.l, m.r, m.b, m.t});
        case D4_HT: return box(rt, {m.b, m.t, m.r, m.l});
        case D4_CC: return box(rt, {m.r, m.l, m.t, m.b});
        case D4_LR: return box(rt, {m.t, m.b, m.r, m.l});
        case D4_TB: return box(rt, {m.b, m.t, m.l, m.r});
        case D4_DG: return box(rt, {m.l, m.r, m.t, m.b});
        case D4_AD: return box(rt, {m.r, m.l, m.b, m.t});
    }
    return p;
}

RamDomain box_tiles(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain a,
                    RamDomain k, RamDomain g) {
    return tiling(margins(rt, p), a, k, g).ok;
}

RamDomain box_tile_outer(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain a,
                         RamDomain k, RamDomain g) {
    Tiling t = tiling(margins(rt, p), a, k, g);
    return box(rt, axis_only(a, t.outer, t.n - 1 - t.outer));
}

RamDomain box_tile_inner(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain a,
                         RamDomain k, RamDomain g) {
    Tiling t = tiling(margins(rt, p), a, k, g);
    return box(rt, axis_only(a, t.inner, t.k - 1 - t.inner));
}

RamDomain box_concat(SymbolTable*, RecordTable* rt, RamDomain outer, RamDomain inner,
                     RamDomain a, RamDomain g) {
    Margins o = margins(rt, outer), i = margins(rt, inner);
    RamDomain span = near(i, a) + far(i, a) + 1;
    return box(rt, axis_only(a, near(o, a) * (span + g) + near(i, a),
                              far(o, a) * (span + g) + far(i, a)));
}

}  // extern "C"
