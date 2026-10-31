//! Ray, Walk, Boundary and Outlines: stepping, and tests of each cell's
//! neighbors.
//!
//! A step is the native `compose` of a Position and the `step_offset` of a
//! direction. A step whose margins leave a signed byte reaches no cell.

use arclog::algebra::Algebra;
use arclog::algebra::boxes::BoxRelation;
use arclog::algebra::geometry::{Edge, Edges, Geometry};
use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::hash::{StableHashMap, StableHashSet};
use arclog::registry::Registry;
use arclog::relations::RowSet;
use arclog::terms::{Margins, Term, TermId};

/// The straight path from each source toward each direction, each step
/// onto a node, with its last cell.
///
/// A source that is no node first crosses the Positions off the grid, those
/// with a margin below 0, as the lib's `Ray.cast` does: a step reaches such a
/// Position where each margin it lowers stays at or above 0. From its first
/// node on, a cast reaches only nodes. A source that a grid holds and that is
/// no node crosses nothing, since a step that leaves its grid lowers a margin
/// below 0.
///
/// - in `source(key, P)`: where each path starts. A source on the grid and outside `node` gives only its own row at K = 0.
/// - in `node(key, P)`: the cells a path may step onto. A path stops before its first step off them.
/// - in `dir(key, D)`, from the key: the directions.
/// - out `ray(key, P, D, K, Origin)`: P is K steps from Origin toward D. Each source is on its own path at K = 0.
/// - out `end(key, P, D, K, Origin)`: the path's last cell.
#[derive(Clone, Copy, Debug, Default)]
pub struct Ray;

impl Construction for Ray {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [source, node, dir] = group.inputs else { panic!("the three inputs of Ray") };
        let mut ray = RowSet::empty(4);
        let mut end = RowSet::empty(4);
        for d in dir.rows() {
            let d = d[0];
            let Some(offset) = step_offset(context.registry, d) else { continue };
            for origin in source.rows() {
                let origin = origin[0];
                let mut p = origin;
                let mut k = 0;
                loop {
                    if group.wanted[0] {
                        ray.insert(Box::new([p, d, Term::encode_count(k), origin]));
                    }
                    match cast_step(context.registry, node, p, offset) {
                        Some(q) => (p, k) = (q, k + 1),
                        None => break,
                    }
                }
                if group.wanted[1] {
                    end.insert(Box::new([p, d, Term::encode_count(k), origin]));
                }
                context.budget.charge_work(k as u64 + 1)?;
            }
        }
        context.budget.charge_rows((ray.len() + end.len()) as u64)?;
        Ok(GroupOutputs { outputs: Box::new([ray, end]) })
    }
}

/// The member a given count of successors from a start.
///
/// A start is a member with a successor. Each start is its own walk at
/// count 0, and the walks run to the greatest count of `steps`.
///
/// - in `successor(key, p, p_next)`.
/// - in `steps(key, N)`: the step counts to walk.
/// - out `walk(key, p0, N, p)`: N steps from p0 reach p, for every N from 0 to the greatest N of `steps`. A walk starts only at a member that has a successor, and a walk that runs out of successors has no row past its end.
#[derive(Clone, Copy, Debug, Default)]
pub struct Walk;

impl Construction for Walk {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [successor, steps] = group.inputs else { panic!("the two inputs of Walk") };
        let width = usize::from(successor.arity()) / 2;
        let mut next: StableHashMap<&[TermId], Vec<&[TermId]>> = StableHashMap::default();
        for row in successor.rows() {
            next.entry(&row[..width]).or_default().push(&row[width..]);
        }
        let bound = steps.rows().map(|row| Term::decode_number(row[0])).max().unwrap_or(0).max(0);
        let mut walk = RowSet::empty(2 * width as u16 + 1);
        for &start in next.keys() {
            let mut at: StableHashSet<&[TermId]> = [start].into_iter().collect();
            for n in 0..=bound {
                for &p in &at {
                    walk.insert(start.iter().chain([&Term::encode_number(n)]).chain(p).copied().collect());
                }
                if n == bound {
                    break;
                }
                let reached: StableHashSet<&[TermId]> =
                    at.iter().flat_map(|p| next.get(p).into_iter().flatten().copied()).collect();
                context.budget.charge_work(at.len() as u64 + 1)?;
                at = reached;
                if at.is_empty() {
                    break;
                }
            }
        }
        context.budget.charge_rows(walk.len() as u64)?;
        Ok(GroupOutputs { outputs: Box::new([walk]) })
    }
}

/// The cells of the group's set with nothing of the set one step toward a
/// direction.
///
/// - in `cell(key, P)`.
/// - in `dir(D)`, shared, default the four edges: the directions tested.
/// - out `exposed(key, P, D)`: no cell of the set lies one step from P toward D. Off the grid counts as no cell.
/// - out `boundary(key, P)`: P is exposed toward some direction.
#[derive(Clone, Copy, Debug, Default)]
pub struct Boundary;

impl Construction for Boundary {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [cell, dir] = group.inputs else { panic!("the two inputs of Boundary") };
        let offsets: Vec<(TermId, TermId)> = dir.rows().filter_map(|d| Some((d[0], step_offset(context.registry, d[0])?))).collect();
        let mut boundary = RowSet::empty(1);
        let mut exposed = RowSet::empty(2);
        for p in cell.rows() {
            for &(d, offset) in &offsets {
                if step(context.registry, cell, p[0], offset).is_none() {
                    if group.wanted[0] {
                        boundary.insert(Box::new([p[0]]));
                    }
                    if group.wanted[1] {
                        exposed.insert(Box::new([p[0], d]));
                    }
                }
            }
        }
        context.budget.charge_work((cell.len() * offsets.len()) as u64)?;
        context.budget.charge_rows((boundary.len() + exposed.len()) as u64)?;
        Ok(GroupOutputs { outputs: Box::new([boundary, exposed]) })
    }
}

/// The rectangles drawn in the group's set: candidate boxes from corner
/// cells, each tested along its perimeter.
///
/// A rectangle spans at least two cells on each axis, and its interior may
/// hold any cells.
///
/// - in `node(key, P)`.
/// - out `box(key, B)`: every cell of B's outline is in the set. B is at least two cells long on each axis, and its interior may hold any cells.
#[derive(Clone, Copy, Debug, Default)]
pub struct Outlines;

impl Construction for Outlines {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [node] = group.inputs else { panic!("the one input of Outlines") };
        let registry = context.registry;
        let toward = |edge: Edge| {
            let d = Geometry::get().direction(Edges::of(&[edge])).expect("a Dir8 toward each edge");
            step_offset(registry, d).expect("a step offset of each Dir8")
        };
        let (right, down) = (toward(Edge::Right), toward(Edge::Bottom));
        // The cells of the run of nodes from each node toward a direction,
        // the node first.
        let run = |p: TermId, offset: TermId| -> Vec<TermId> {
            std::iter::successors(Some(p), |&q| step(registry, node, q, offset)).collect()
        };
        let mut boxes = RowSet::empty(1);
        let mut work = 0;
        // Each candidate's corner toward the top and the left, `p`, with
        // its top side `top` and its left side `left`.
        for p in node.rows() {
            let (top, left) = (run(p[0], right), run(p[0], down));
            for (w, &top_right) in top.iter().enumerate().skip(1) {
                let right_side = run(top_right, down);
                for (h, &bottom_left) in left.iter().enumerate().skip(1).take(right_side.len() - 1) {
                    work += 1;
                    if run(bottom_left, right).len() > w {
                        boxes.insert(Box::new([span(p[0], right_side[h])]));
                    }
                }
            }
        }
        context.budget.charge_work(work)?;
        context.budget.charge_rows(boxes.len() as u64)?;
        Ok(GroupOutputs { outputs: Box::new([boxes]) })
    }
}

/// The node one step from `p` by `offset`, or `None` where that cell is not
/// in `nodes`: the cell `p` is exposed toward the step in Boundary's sense.
fn step(registry: &Registry, nodes: &RowSet, p: TermId, offset: TermId) -> Option<TermId> {
    compose(registry, p, offset).filter(|&q| nodes.contains(&[q]))
}

/// The cell one step from `p` by `offset` in a cast of Ray: a node, or,
/// where `p` is no node, a Position off the grid that the step enters
/// without lowering a margin below 0. `None` where the cast ends at `p`.
fn cast_step(registry: &Registry, nodes: &RowSet, p: TermId, offset: TermId) -> Option<TermId> {
    let q = compose(registry, p, offset)?;
    let crosses = !nodes.contains(&[p]) && enters_off_grid(Term::decode_box(p), Term::decode_box(q));
    (nodes.contains(&[q]) || crosses).then_some(q)
}

/// Whether the Position `q` has a margin below 0 and each margin of `q`
/// lower than that of `p` is at or above 0.
fn enters_off_grid(p: Margins, q: Margins) -> bool {
    let margins = |m: Margins| [m.top, m.bottom, m.left, m.right];
    let (p, q) = (margins(p), margins(q));
    q.iter().any(|&margin| margin < 0) && p.iter().zip(&q).all(|(&before, &after)| after >= before || after >= 0)
}

/// The Position one step from `p` by `offset`, or `None` where a margin of it
/// is outside a signed byte.
fn compose(registry: &Registry, p: TermId, offset: TermId) -> Option<TermId> {
    let mut q = None;
    // A margin outside a signed byte is a cell no node holds.
    let _ = BoxRelation::Compose.evaluate(&[Some(p), Some(offset), None], registry, &mut |row| q = Some(row[2]));
    q
}

/// The Offset of one step toward `d`, or `None` where `d` is no Dir8, where
/// the lib's `step_offset` holds no row. Ray and Boundary give no row of such
/// a `d`.
fn step_offset(registry: &Registry, d: TermId) -> Option<TermId> {
    let mut offset = None;
    BoxRelation::StepOffset
        .evaluate(&[Some(d), None], registry, &mut |row| offset = Some(row[1]))
        .expect("a step offset within a signed byte");
    offset
}

/// The Box whose corner toward the top and the left is the Position `a`,
/// and whose corner toward the bottom and the right is the Position `b`.
fn span(a: TermId, b: TermId) -> TermId {
    let (a, b) = (Term::decode_box(a), Term::decode_box(b));
    let span = Margins { top: a.top, left: a.left, bottom: b.bottom, right: b.right };
    Term::Box(span).encode().expect("the box of two Positions")
}

