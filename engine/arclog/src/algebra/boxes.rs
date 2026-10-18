//! The box algebra's relations over Box, Position, Offset and number, and
//! the native forms of the relation macros over them: each computes in
//! 32-bit integers, and packs only the Boxes it binds, as
//! [`crate::terms::Margins`] gives.
//!
//! Each relation's arithmetic is that of the functors of
//! `programs/lib_functors.cpp` and the rules of `programs/lib/box.dl`, and
//! each macro's that of its definition in `engine/lib/registry.sexpr`.

use super::orientation::{Edge, Edges, Geometry};
use super::Algebra;
use crate::registry::Registry;
use crate::terms::{Margins, Number, ReachedMarginBound, Term, TermId};
use crate::types::ValueType;

/// Declares [`BoxRelation`] from its variants, each with its registry name,
/// with [`BoxRelation::ALL`] and [`BoxRelation::registry_name`].
macro_rules! box_relations {
    ($($relation:ident => $name:literal,)*) => {
        /// A relation of the box algebra, or a relation macro over Boxes, by
        /// its registry name.
        #[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
        pub enum BoxRelation {
            $($relation,)*
        }

        impl BoxRelation {
            /// Each relation of the box algebra.
            pub const ALL: &'static [BoxRelation] = &[$(BoxRelation::$relation,)*];

            /// The relation's name in the registry.
            const fn registry_name(self) -> &'static str {
                match self {
                    $(BoxRelation::$relation => $name,)*
                }
            }
        }
    };
}

box_relations! {
    Compose => "compose",
    Relative => "relative",
    EdgeInset => "edge_inset",
    Margin => "margin",
    Apply => "apply",
    CornerDist => "corner_dist",
    FrameExtent => "frame_extent",
    StepOffset => "step_offset",
    SubExtent => "sub_extent",
    Gap => "gap",
    Divide => "divide",
    Inside => "inside",
    Interior => "interior",
    SameDist => "same_dist",
    SameLine => "same_line",
    SameCorner => "same_corner",
    SameSlab => "same_slab",
    Nearer => "nearer",
    Centered => "centered",
    DistPair => "dist_pair",
    DiagDist => "diag_dist",
    AxisExtents => "axis_extents",
    BoxExtent => "box_extent",
    AxisInset => "axis_inset",
    UniformInset => "uniform_inset",
    CornerInset => "corner_inset",
    EdgeOutset => "edge_outset",
    CornerOutset => "corner_outset",
    AxisOutset => "axis_outset",
    UniformOutset => "uniform_outset",
    Jump => "jump",
    JumpOffset => "jump_offset",
    FrameOffset => "frame_offset",
    Neighbor => "neighbor",
    Split => "split",
}

fn margin(m: Margins, edge: Edge) -> i32 {
    match edge {
        Edge::Top => m.top,
        Edge::Bottom => m.bottom,
        Edge::Left => m.left,
        Edge::Right => m.right,
    }
}

/// The Box whose margin at each edge `at` gives.
fn margins(at: impl Fn(Edge) -> i32) -> Margins {
    Margins { top: at(Edge::Top), bottom: at(Edge::Bottom), left: at(Edge::Left), right: at(Edge::Right) }
}

fn add(a: Margins, b: Margins) -> Margins {
    margins(|e| margin(a, e).saturating_add(margin(b, e)))
}

fn subtract(a: Margins, b: Margins) -> Margins {
    margins(|e| margin(a, e).saturating_sub(margin(b, e)))
}

/// The sum of `m`'s margins at `edges`: for a Dir, the distance to its
/// edge, and for a DiagDir, the taxicab distance to its corner.
fn distance(m: Margins, edges: Edges) -> i32 {
    edges.each().map(|e| margin(m, e)).sum()
}

/// The Box inset by `k` at each of `edges`.
fn inset(edges: Edges, k: i32) -> Margins {
    margins(|e| if edges.contains(e) { k } else { 0 })
}

/// The translation of `k` cells toward `edges`: `-k` at each of them and
/// `k` at each opposite.
fn jump_offset(edges: Edges, k: i32) -> Margins {
    margins(|e| {
        if edges.contains(e) {
            k.saturating_neg()
        } else if edges.contains(e.opposite()) {
            k
        } else {
            0
        }
    })
}

/// The extent of `p`'s frame along the axis whose edges are `axis`.
fn extent(p: Margins, axis: Edges) -> i32 {
    distance(p, axis) + 1
}

/// The image of `p` under the D4 element `g`: the margin at each edge goes
/// to that edge's image.
pub(crate) fn apply(g: super::orientation::D4Element, p: Margins) -> Margins {
    margins(|e| margin(p, Edge::ALL.into_iter().find(|&f| g.image(f) == e).expect("an element moves each edge to an edge")))
}

/// The bound columns of one evaluation, as the trait's `bound` gives them.
struct Columns<'b>(&'b [Option<TermId>]);

impl Columns<'_> {
    fn input(&self, column: usize) -> TermId {
        self.0[column].expect("a column of the mode the bound columns satisfy")
    }

    fn boxed(&self, column: usize) -> Margins {
        match Term::decode(self.input(column), &ValueType::Box) {
            Term::Box(m) => m,
            _ => unreachable!("a Box column"),
        }
    }

    fn number(&self, column: usize) -> i32 {
        match Term::decode(self.input(column), &ValueType::Number) {
            Term::Number(Number(n)) => n,
            _ => unreachable!("a number column"),
        }
    }

    /// The term id of `m` at the Box column `column`: where the column is
    /// bound, its value where `m` is that Box and `None` where it is not,
    /// and otherwise `m` packed.
    fn out_box(&self, column: usize, m: Margins) -> Result<Option<TermId>, ReachedMarginBound> {
        match self.0[column] {
            Some(value) => Ok((Term::decode(value, &ValueType::Box) == Term::Box(m)).then_some(value)),
            None => Term::Box(m).encode().map(Some),
        }
    }
}

fn number(n: i32) -> TermId {
    Term::Number(Number(n)).encode().expect("a number's term id")
}

/// A value of a row: a term id, or a Box computed for its column.
enum Value {
    Id(TermId),
    Box(Margins),
}

impl Algebra for BoxRelation {
    fn name(&self) -> &'static str {
        self.registry_name()
    }

    fn evaluate(
        &self,
        bound: &[Option<TermId>],
        _registry: &Registry,
        emit: &mut dyn FnMut(&[TermId]),
    ) -> Result<(), ReachedMarginBound> {
        use Value::{Box as B, Id};
        let c = Columns(bound);
        let geometry = Geometry::get();
        let each = |column: usize, ty: ValueType| geometry.each(bound[column], &ty).collect::<Vec<_>>();
        let edges = |value: TermId| geometry.edges(value);
        // Emits `row` where each Box packs or agrees with its bound column.
        let mut row = |values: &[Value]| -> Result<(), ReachedMarginBound> {
            let mut ids = Vec::with_capacity(values.len());
            for (column, value) in values.iter().enumerate() {
                match *value {
                    Id(id) => ids.push(id),
                    B(m) => match c.out_box(column, m)? {
                        Some(id) => ids.push(id),
                        None => return Ok(()),
                    },
                }
            }
            emit(&ids);
            Ok(())
        };
        let id = |column: usize| Id(c.input(column));
        let n = |k: i32| Id(number(k));
        match self {
            BoxRelation::Compose => row(&[id(0), id(1), B(add(c.boxed(0), c.boxed(1)))])?,
            BoxRelation::Relative => row(&[id(0), id(1), B(subtract(c.boxed(1), c.boxed(0)))])?,
            BoxRelation::EdgeInset => {
                for d in each(0, ValueType::Dir) {
                    row(&[Id(d), id(1), B(inset(edges(d), c.number(1)))])?;
                }
            }
            BoxRelation::Margin => {
                for d in each(1, ValueType::Dir) {
                    row(&[id(0), Id(d), n(distance(c.boxed(0), edges(d)))])?;
                }
            }
            BoxRelation::Apply => {
                for t in each(0, ValueType::D4) {
                    row(&[Id(t), id(1), B(apply(geometry.element(t), c.boxed(1)))])?;
                }
            }
            BoxRelation::CornerDist => {
                for diag in each(1, ValueType::DiagDir) {
                    row(&[id(0), Id(diag), n(distance(c.boxed(0), edges(diag)))])?;
                }
            }
            BoxRelation::FrameExtent => {
                for a in each(1, ValueType::Axis) {
                    row(&[id(0), Id(a), n(extent(c.boxed(0), geometry.axis_edges(a)))])?;
                }
            }
            BoxRelation::StepOffset => {
                for d in each(0, ValueType::Dir8) {
                    row(&[Id(d), B(jump_offset(edges(d), 1))])?;
                }
            }
            BoxRelation::SubExtent => {
                for a in each(1, ValueType::Axis) {
                    for k in sub_extents(extent(c.boxed(0), geometry.axis_edges(a)), &c, 2) {
                        row(&[id(0), Id(a), n(k)])?;
                    }
                }
            }
            BoxRelation::Gap => {
                // q is `jump` from p toward d at k + 1.
                let v = subtract(c.boxed(2), c.boxed(1));
                for d in each(0, ValueType::Dir8) {
                    let toward = edges(d).each().next().expect("a direction's edge");
                    let steps = margin(v, toward).saturating_neg();
                    if steps >= 1 && jump_offset(edges(d), steps) == v {
                        row(&[Id(d), id(1), id(2), n(steps - 1)])?;
                    }
                }
            }
            BoxRelation::Divide => {
                let (t, side, gap) = (i64::from(c.number(0)), i64::from(c.number(1)), i64::from(c.number(2)));
                let period = side + gap;
                if t >= 0 && period > 0 && t % period < side {
                    let part = i32::try_from(t / period).expect("a part no greater than the count");
                    let remainder = i32::try_from(t % period).expect("a remainder less than the side");
                    row(&[id(0), id(1), id(2), n(part), n(remainder)])?;
                }
            }
            BoxRelation::Inside | BoxRelation::Interior => {
                let (a, b) = (c.boxed(0), c.boxed(1));
                let holds = |e: Edge| match self {
                    BoxRelation::Inside => margin(a, e) >= margin(b, e),
                    _ => margin(a, e) > margin(b, e),
                };
                if Edge::ALL.into_iter().all(holds) {
                    row(&[id(0), id(1)])?;
                }
            }
            BoxRelation::SameDist => {
                for d in each(0, ValueType::Dir) {
                    if margin(c.boxed(1), geometry.edge(d)) == margin(c.boxed(2), geometry.edge(d)) {
                        row(&[Id(d), id(1), id(2)])?;
                    }
                }
            }
            BoxRelation::SameLine => {
                // p and q agree on the distance toward a direction of the
                // axis perpendicular to a.
                for a in each(0, ValueType::Axis4) {
                    let perpendicular = geometry.perpendicular_directions(a);
                    if perpendicular.into_iter().any(|e| distance(c.boxed(1), e) == distance(c.boxed(2), e)) {
                        row(&[Id(a), id(1), id(2)])?;
                    }
                }
            }
            BoxRelation::SameCorner => {
                for diag in each(0, ValueType::DiagDir) {
                    if edges(diag).each().all(|e| margin(c.boxed(1), e) == margin(c.boxed(2), e)) {
                        row(&[Id(diag), id(1), id(2)])?;
                    }
                }
            }
            BoxRelation::SameSlab => {
                // The distance to d's edge, and to each edge across d's axis.
                for d in each(0, ValueType::Dir) {
                    let e = geometry.edge(d);
                    let compared = Edge::ALL.into_iter().filter(|&f| f != e.opposite());
                    if compared.into_iter().all(|f| margin(c.boxed(1), f) == margin(c.boxed(2), f)) {
                        row(&[Id(d), id(1), id(2)])?;
                    }
                }
            }
            BoxRelation::Nearer => {
                for d in each(0, ValueType::Dir8) {
                    if distance(c.boxed(1), edges(d)) < distance(c.boxed(2), edges(d)) {
                        row(&[Id(d), id(1), id(2)])?;
                    }
                }
            }
            BoxRelation::Centered => {
                let p = c.boxed(0);
                if p.top == p.bottom && p.left == p.right {
                    row(&[id(0)])?;
                }
            }
            BoxRelation::DistPair => {
                let p = c.boxed(0);
                for d in each(1, ValueType::Dir) {
                    row(&[id(0), Id(d), n(margin(p, geometry.edge(d))), n(margin(p, geometry.edge(d).opposite()))])?;
                }
            }
            BoxRelation::DiagDist => {
                let p = c.boxed(0);
                for diag in each(1, ValueType::DiagDir) {
                    for a in each(2, ValueType::Axis) {
                        let on = |on_a: bool| margin(p, geometry.corner_edge(diag, a, on_a));
                        row(&[id(0), Id(diag), Id(a), n(on(true)), n(on(false))])?;
                    }
                }
            }
            BoxRelation::AxisExtents => {
                let p = c.boxed(0);
                for a in each(1, ValueType::Axis) {
                    let along = geometry.axis_edges(a);
                    row(&[id(0), Id(a), n(extent(p, along)), n(extent(p, along.complement()))])?;
                }
            }
            BoxRelation::BoxExtent => {
                let relative = subtract(c.boxed(1), c.boxed(0));
                for a in each(2, ValueType::Axis) {
                    row(&[id(0), id(1), Id(a), n(extent(relative, geometry.axis_edges(a)))])?;
                }
            }
            BoxRelation::AxisInset | BoxRelation::AxisOutset => {
                let sign = |k: i32| if *self == BoxRelation::AxisInset { k } else { k.saturating_neg() };
                let (k1, k2) = (sign(c.number(1)), sign(c.number(2)));
                for d in each(0, ValueType::Dir) {
                    let b = margins(|e| if e == geometry.edge(d) { k1 } else if e == geometry.edge(d).opposite() { k2 } else { 0 });
                    row(&[Id(d), id(1), id(2), B(b)])?;
                }
            }
            BoxRelation::UniformInset => row(&[id(0), B(margins(|_| c.number(0)))])?,
            BoxRelation::UniformOutset => row(&[id(0), B(margins(|_| c.number(0).saturating_neg()))])?,
            BoxRelation::CornerInset | BoxRelation::CornerOutset | BoxRelation::EdgeOutset => {
                let (ty, k) = match self {
                    BoxRelation::CornerInset => (ValueType::DiagDir, c.number(1)),
                    BoxRelation::CornerOutset => (ValueType::DiagDir, c.number(1).saturating_neg()),
                    _ => (ValueType::Dir, c.number(1).saturating_neg()),
                };
                for d in each(0, ty) {
                    row(&[Id(d), id(1), B(inset(edges(d), k))])?;
                }
            }
            BoxRelation::Jump => {
                for d in each(1, ValueType::Dir8) {
                    row(&[id(0), Id(d), id(2), B(add(c.boxed(0), jump_offset(edges(d), c.number(2))))])?;
                }
            }
            BoxRelation::JumpOffset => {
                for d in each(0, ValueType::Dir8) {
                    row(&[Id(d), id(1), B(jump_offset(edges(d), c.number(1)))])?;
                }
            }
            BoxRelation::FrameOffset => {
                // An offset of k toward either edge of a, at each k of
                // `sub_extent`.
                for a in each(1, ValueType::Axis) {
                    let axis = geometry.axis_edges(a);
                    for k in sub_extents(extent(c.boxed(0), axis), &c, 2) {
                        for toward in axis.each() {
                            row(&[id(0), Id(a), n(k), B(jump_offset(Edges::of(&[toward]), k))])?;
                        }
                    }
                }
            }
            BoxRelation::Neighbor => {
                for d in each(1, ValueType::Dir8) {
                    row(&[id(0), Id(d), B(add(c.boxed(0), jump_offset(edges(d), 1)))])?;
                }
            }
            BoxRelation::Split => {
                let p = c.boxed(0);
                for a in each(1, ValueType::Axis) {
                    let axis = geometry.axis_edges(a);
                    let along = margins(|e| if axis.contains(e) { margin(p, e) } else { 0 });
                    row(&[id(0), Id(a), B(along), B(subtract(p, along))])?;
                }
            }
        }
        Ok(())
    }
}

/// The proper sub-extents of an extent of `extent`, each k with
/// 1 <= k < extent: the value of the number column `column` where it is
/// bound and one of them, and otherwise each.
fn sub_extents(extent: i32, c: &Columns<'_>, column: usize) -> Vec<i32> {
    match c.0[column] {
        Some(_) => Some(c.number(column)).filter(|k| (1..extent).contains(k)).into_iter().collect(),
        None => (1..extent).collect(),
    }
}
