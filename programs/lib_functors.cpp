// C++ functors backing the box algebra in lib/box.dl. Each functor unpacks
// its Box arguments through the record table and packs its result.
//
// Souffle cannot ground a record pattern against a functor call, so a
// wrapper clause in box.dl reads a functor's result through another functor,
// never through a pattern.
//
// The orientation constants (DIR_T, AXIS_V, ...) are the #define values of
// lib/orientation.dl, which the build passes to the compiler.
//
// Build: see build_functors() in src/souffle/run.py (auto-built; artifact gitignored).

#include <cstdio>
#include <cstdlib>

#include "souffle/RecordTable.h"
#include "souffle/SouffleFunctor.h"

using souffle::RamDomain;
using souffle::RecordTable;
using souffle::SymbolTable;

namespace {

// Fail the run on an orientation value that no case of `functor` gives.
[[noreturn]] void no_case(const char* functor, RamDomain value) {
    std::fprintf(stderr, "%s: no case for the value %d\n", functor, static_cast<int>(value));
    std::abort();
}

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
RamDomain near(Margins m, RamDomain a) {
    switch (a) {
        case AXIS_V: return m.t;
        case AXIS_H: return m.l;
    }
    no_case("near", a);
}

RamDomain far(Margins m, RamDomain a) {
    switch (a) {
        case AXIS_V: return m.b;
        case AXIS_H: return m.r;
    }
    no_case("far", a);
}

// A box with near and far along axis a, zero across.
Margins axis_only(RamDomain a, RamDomain near, RamDomain far) {
    switch (a) {
        case AXIS_V: return Margins{near, far, 0, 0};
        case AXIS_H: return Margins{0, 0, near, far};
    }
    no_case("axis_only", a);
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

// The distance from a box to its edge at a Dir, and to its corner at a
// DiagDir. Each returns false, with `out` untouched, at any other value.
bool edge_dist(Margins m, RamDomain d, RamDomain& out) {
    switch (d) {
        case DIR_T: out = m.t; return true;
        case DIR_B: out = m.b; return true;
        case DIR_L: out = m.l; return true;
        case DIR_R: out = m.r; return true;
    }
    return false;
}

bool corner_dist(Margins m, RamDomain diag, RamDomain& out) {
    switch (diag) {
        case DIAG_TL: out = m.t + m.l; return true;
        case DIAG_TR: out = m.t + m.r; return true;
        case DIAG_BL: out = m.b + m.l; return true;
        case DIAG_BR: out = m.b + m.r; return true;
    }
    return false;
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
    RamDomain k;
    if (edge_dist(m, d, k)) return k;
    no_case("box_dist", d);
}

// Taxicab distance to corner diag: the sum of its two edge distances.
RamDomain box_corner_dist(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain diag) {
    Margins m = margins(rt, p);
    RamDomain k;
    if (corner_dist(m, diag, k)) return k;
    no_case("box_corner_dist", diag);
}

// The edge distance at a Dir and the corner distance at a DiagDir.
RamDomain box_dir8_dist(SymbolTable*, RecordTable* rt, RamDomain p, RamDomain d) {
    Margins m = margins(rt, p);
    RamDomain k;
    if (edge_dist(m, d, k) || corner_dist(m, d, k)) return k;
    no_case("box_dir8_dist", d);
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
    no_case("box_apply", d);
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
