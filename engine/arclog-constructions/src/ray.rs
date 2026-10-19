//! Ray, Walk, Boundary and Outlines: stepping, and tests of each cell's
//! neighbors.
//!
//! A step is the native `compose` of a Position and the `step_offset` of a
//! direction. A step whose margins leave a signed byte reaches no cell.

use arclog::algebra::Algebra;
use arclog::algebra::boxes::BoxRelation;
use arclog::algebra::orientation::{Edge, Edges, Geometry};
use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::hash::{StableHashMap, StableHashSet};
use arclog::registry::Registry;
use arclog::relations::RowSet;
use arclog::terms::{Margins, Term, TermId};

/// The straight path from each source toward each direction, each step
/// onto a node, with its last cell.
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
            let offset = step_offset(context.registry, d);
            for origin in source.rows() {
                let origin = origin[0];
                let mut p = origin;
                let mut k = 0;
                loop {
                    ray.insert(Box::new([p, d, Term::encode_count(k), origin]));
                    match step(context.registry, node, p, offset) {
                        Some(q) => (p, k) = (q, k + 1),
                        None => break,
                    }
                }
                end.insert(Box::new([p, d, Term::encode_count(k), origin]));
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
        let offsets: Vec<(TermId, TermId)> = dir.rows().map(|d| (d[0], step_offset(context.registry, d[0]))).collect();
        let mut boundary = RowSet::empty(1);
        let mut exposed = RowSet::empty(2);
        for p in cell.rows() {
            for &(d, offset) in &offsets {
                if step(context.registry, cell, p[0], offset).is_none() {
                    boundary.insert(Box::new([p[0]]));
                    exposed.insert(Box::new([p[0], d]));
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
            step_offset(registry, d)
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
    let mut q = None;
    // A margin outside a signed byte is a cell no node holds.
    let _ = BoxRelation::Compose.evaluate(&[Some(p), Some(offset), None], registry, &mut |row| q = Some(row[2]));
    q.filter(|&q| nodes.contains(&[q]))
}

/// The Offset of one step toward the Dir8 `d`.
fn step_offset(registry: &Registry, d: TermId) -> TermId {
    let mut offset = None;
    BoxRelation::StepOffset
        .evaluate(&[Some(d), None], registry, &mut |row| offset = Some(row[1]))
        .expect("a step offset within a signed byte");
    offset.expect("a step offset of each Dir8")
}

/// The Box whose corner toward the top and the left is the Position `a`,
/// and whose corner toward the bottom and the right is the Position `b`.
fn span(a: TermId, b: TermId) -> TermId {
    let (a, b) = (Term::decode_box(a), Term::decode_box(b));
    let span = Margins { top: a.top, left: a.left, bottom: b.bottom, right: b.right };
    Term::Box(span).encode().expect("the box of two Positions")
}

