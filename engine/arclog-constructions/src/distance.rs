//! Distance and CellDistance: breadth-first and Dijkstra search, keeping
//! every predecessor at the least cost.
//!
//! Each `edge`, `weight`, `source` and `source_distance` row is a candidate
//! cost, and each cost is the least of its candidates. A search is
//! breadth-first where every edge costs one and every source starts at zero.

use std::cmp::Reverse;
use std::collections::{BinaryHeap, VecDeque};

use arclog::eval::ReachedBound;
use arclog::eval::instance::{Construction, ConstructionContext, GroupInputs, GroupOutputs};
use arclog::eval::join::Budget;
use arclog::hash::StableHashMap;
use arclog::relations::{Row, RowSet};
use arclog::terms::{Margins, Number, Term, TermId};
use arclog::types::ValueType;

/// The steps a search takes between two charges of its budget.
const BATCH: u64 = 1024;

/// The least cost from a source to each node, and every predecessor on a
/// least-cost path.
#[derive(Clone, Copy, Debug, Default)]
pub struct Distance;

impl Construction for Distance {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [edge, weight, source, source_distance] = group.inputs else {
            panic!("the four inputs of Distance")
        };
        let width = usize::from(source.arity());
        let mut graph = Graph::new(width);
        for row in edge.rows() {
            graph.edge(&row[..width], &row[width..], 1);
        }
        for row in weight.rows() {
            graph.edge(&row[..width], &row[width..2 * width], number(row[2 * width]));
        }
        for row in source.rows() {
            graph.start(row, 0);
        }
        for row in source_distance.rows() {
            graph.start(&row[..width], number(row[width]));
        }
        graph.distances(context.budget)
    }
}

/// Distance over the steps inside the group's set, the cardinals by
/// default.
#[derive(Clone, Copy, Debug, Default)]
pub struct CellDistance;

impl Construction for CellDistance {
    fn name(&self) -> &'static str {
        Self::NAME
    }

    fn evaluate(
        &self,
        group: &GroupInputs<'_>,
        context: &mut ConstructionContext<'_, '_>,
    ) -> Result<GroupOutputs, ReachedBound> {
        let [node, source, step] = group.inputs else { panic!("the three inputs of CellDistance") };
        let mut graph = Graph::new(1);
        for p in node.rows() {
            let from = margins(p[0]);
            for delta in step.rows() {
                // The `compose` of the box algebra: the margins summed.
                let to = margins(delta[0]);
                let q = Margins {
                    top: from.top + to.top,
                    bottom: from.bottom + to.bottom,
                    left: from.left + to.left,
                    right: from.right + to.right,
                };
                // A sum outside a signed byte is a Box no node holds.
                if let Ok(q) = Term::Box(q).encode()
                    && node.contains(&[q])
                {
                    graph.edge(p, &[q], 1);
                }
            }
        }
        for row in source.rows() {
            graph.start(row, 0);
        }
        graph.distances(context.budget)
    }
}

/// The value of a `number` column.
fn number(id: TermId) -> i64 {
    let Term::Number(Number(n)) = Term::decode(id, &ValueType::Number) else { unreachable!("a number column") };
    i64::from(n)
}

/// The margins of a Box column.
fn margins(id: TermId) -> Margins {
    let Term::Box(margins) = Term::decode(id, &ValueType::Box) else { unreachable!("a Box column") };
    margins
}

/// The nodes of one key group by index, each edge at its least cost, and
/// each source at its least start cost.
struct Graph {
    width: usize,
    index: StableHashMap<Row, usize>,
    nodes: Vec<Row>,
    edges: StableHashMap<(usize, usize), i64>,
    starts: StableHashMap<usize, i64>,
}

impl Graph {
    fn new(width: usize) -> Self {
        Graph {
            width,
            index: StableHashMap::default(),
            nodes: Vec::new(),
            edges: StableHashMap::default(),
            starts: StableHashMap::default(),
        }
    }

    fn node(&mut self, node: &[TermId]) -> usize {
        if let Some(&index) = self.index.get(node) {
            return index;
        }
        let index = self.nodes.len();
        self.nodes.push(node.into());
        self.index.insert(node.into(), index);
        index
    }

    /// Adds a candidate cost of the edge from `a` to `b`.
    fn edge(&mut self, a: &[TermId], b: &[TermId], cost: i64) {
        let edge = (self.node(a), self.node(b));
        least(self.edges.entry(edge).or_insert(cost), cost);
    }

    /// Adds a candidate start cost of `node`.
    fn start(&mut self, node: &[TermId], cost: i64) {
        let node = self.node(node);
        least(self.starts.entry(node).or_insert(cost), cost);
    }

    /// The `distance` and `predecessor` rows of the graph.
    fn distances(self, budget: &mut Budget<'_>) -> Result<GroupOutputs, ReachedBound> {
        let mut out = vec![Vec::new(); self.nodes.len()];
        for (&(a, b), &cost) in &self.edges {
            out[a].push((b, cost));
        }
        let mut search = Search { budget, steps: 0 };
        let unit = self.edges.values().all(|&cost| cost == 1) && self.starts.values().all(|&cost| cost == 0);
        let costs = if unit { search.breadth_first(&self.starts, &out)? } else { search.dijkstra(&self.starts, &out)? };
        search.charge(0)?;
        let mut distance = RowSet::empty(self.width as u16 + 1);
        for (node, cost) in self.nodes.iter().zip(&costs) {
            if let Some(cost) = cost {
                distance.insert(row(node, &[encode_number(*cost)]));
            }
        }
        let mut predecessor = RowSet::empty(2 * self.width as u16);
        for (&(a, b), &cost) in &self.edges {
            if let (Some(at_a), Some(at_b)) = (costs[a], costs[b])
                && at_a + cost == at_b
            {
                predecessor.insert(row(&self.nodes[b], &self.nodes[a]));
            }
        }
        budget.charge_rows((distance.len() + predecessor.len()) as u64)?;
        Ok(GroupOutputs { outputs: Box::new([distance, predecessor]) })
    }
}

/// Lowers `held` to `cost` where `cost` is less.
fn least(held: &mut i64, cost: i64) {
    *held = (*held).min(cost);
}

/// The row of `head`'s columns followed by `tail`'s.
fn row(head: &[TermId], tail: &[TermId]) -> Row {
    head.iter().chain(tail).copied().collect()
}

fn encode_number(cost: i64) -> TermId {
    let n = i32::try_from(cost).expect("a least cost within a number");
    Term::Number(Number(n)).encode().expect("a number encodes")
}

/// A search over a graph's edges, counting its steps against the budget.
struct Search<'s, 'a> {
    budget: &'s mut Budget<'a>,
    steps: u64,
}

impl Search<'_, '_> {
    /// Counts `steps` more steps, and charges the budget a batch once the
    /// count reaches one, or the rest of the count where `steps` is zero.
    fn charge(&mut self, steps: u64) -> Result<(), ReachedBound> {
        self.steps += steps;
        if self.steps >= BATCH || (steps == 0 && self.steps > 0) {
            self.budget.charge_work(std::mem::take(&mut self.steps))?;
        }
        Ok(())
    }

    /// The least cost of each node where every edge costs one and every
    /// source starts at zero.
    fn breadth_first(
        &mut self,
        starts: &StableHashMap<usize, i64>,
        out: &[Vec<(usize, i64)>],
    ) -> Result<Vec<Option<i64>>, ReachedBound> {
        let mut costs = vec![None; out.len()];
        let mut queue = VecDeque::new();
        for &node in starts.keys() {
            costs[node] = Some(0);
            queue.push_back(node);
        }
        while let Some(a) = queue.pop_front() {
            let next = costs[a].expect("a queued node has a cost") + 1;
            for &(b, _) in &out[a] {
                self.charge(1)?;
                if costs[b].is_none() {
                    costs[b] = Some(next);
                    queue.push_back(b);
                }
            }
        }
        Ok(costs)
    }

    /// The least cost of each node by Dijkstra's search. A node whose cost
    /// falls after it is taken is taken again, so a negative cost gives the
    /// least cost where no cycle has a negative sum, and a cycle that has one
    /// runs to the work cap.
    fn dijkstra(
        &mut self,
        starts: &StableHashMap<usize, i64>,
        out: &[Vec<(usize, i64)>],
    ) -> Result<Vec<Option<i64>>, ReachedBound> {
        let mut costs = vec![None; out.len()];
        let mut heap = BinaryHeap::new();
        for (&node, &cost) in starts {
            costs[node] = Some(cost);
            heap.push(Reverse((cost, node)));
        }
        while let Some(Reverse((cost, a))) = heap.pop() {
            if costs[a] != Some(cost) {
                continue;
            }
            for &(b, step) in &out[a] {
                self.charge(1)?;
                let reached = cost + step;
                if costs[b].is_none_or(|held| reached < held) {
                    costs[b] = Some(reached);
                    heap.push(Reverse((reached, b)));
                }
            }
        }
        Ok(costs)
    }
}
