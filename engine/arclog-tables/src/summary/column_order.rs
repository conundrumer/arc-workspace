//! The order of the columns that a TableHash hashes the table's rows in, where
//! columns tie ([`least_body`]).
//!
//! Two columns tie where their type names are equal and the Sets of their
//! cells are equal, over all examples. The TableHash must not depend on the
//! order in which a table writes columns that tie, so it is the least body hash
//! over the orders that the search below reaches, and that set of orders is the
//! same for every table with the same content up to its column order. The search
//! is individualization-refinement:
//!
//! 1. A coloring gives each column a color. The first coloring is the hash of
//!    the column's cells (the TableHash definition's step 2). A class is the
//!    columns with one type name and one color.
//! 2. Refinement gives a column the hash of its color and the sorted list, over
//!    each other column, of that column's type name rank, its color and the
//!    pair hash of the two columns: the hash of the Set of the rows reduced to
//!    those two columns, in that order. It repeats while it splits a class. A
//!    class stays as it is where the refinement does not split it. Refinement
//!    reads only the pair hashes, so it reads no table row after the pair hashes
//!    are made.
//! 3. At a node where each class holds one column, the order of the columns is
//!    their order by type name and color, and the node is a leaf: it has the
//!    body hash of the table with the columns in that order.
//! 4. At any other node, the target class is the largest class with more than
//!    one column, the first in the order of type name and color where several
//!    are as large. For each column of the target class, a child node gives
//!    that column a color of its own and refines. A column is left out when a
//!    column before it in the target class is exchangeable with it: the table
//!    with the contents of the two columns swapped has the body hash that the
//!    table has. The swap is then a symmetry of the table that keeps the
//!    coloring, so the two children have leaves of equal body hashes.
//!
//! The result is the least body hash over the leaves. Let a table `T'` hold the
//! content of a table `T` with its columns permuted, column to column of one
//! type. Each step reads columns through their cells and type names alone, so the
//! nodes, the classes at each node, the target class and the leaves of the search
//! of `T'` are those of `T` with the columns moved by the permutation, and a
//! leaf has the same body hash in both. Exchangeability is a property of the
//! contents of two columns, and the columns that are exchangeable with a column
//! form a class of an equivalence (a swap of two columns that are exchangeable
//! with a third is a composition of swaps), so the children left out are the
//! same in both searches up to the permutation, and the children kept are one for each
//! such class. So the two searches reach the same count of nodes and leaves
//! and have the same least body hash.
//!
//! The order of the leaf with the least body hash is the order of the table's
//! canonical places: [`Searched::found`] gives it, for each place, as the column
//! at that place. Let two tables have one body hash. Each example's Set of
//! TableRows is the same in both under the map that sends each column of one to
//! the column at the same place of the other, as the body hash hashes the rows
//! with the columns in that order. The leaves that tie in body hash may differ in
//! order, and any of them has that property.
//!
//! The search counts its work, and the count depends on the table's content alone,
//! by the same argument. Work is counted in units: a cell hashed is a unit, and a
//! search node is [`NODE_WORK`] units. A search that passes the cap
//! of the setting `column_search_work_cap` has no result, and the table has no TableHash: a search cut short would give a
//! hash that depends on the order in which the table wrote its columns.

use std::hash::Hasher;

use arclog::hash::StableHasher;

use super::column_hash::Cells;

/// The units that one search node counts, which cover its refinement: with the
/// default cap (`arclog::eval::COLUMN_SEARCH_WORK_CAP`, 2^28), the cap stands
/// for 1024 nodes of a table whose leaves hash no cell.
const NODE_WORK: u64 = 1 << 18;

/// The result of a search for the order of the columns of a table.
pub(super) struct Searched {
    /// The least body hash, the low 64 bits of the hash of each example's Set of
    /// TableRows under the order that gives it, and that order: for each place of the
    /// order, the column at it. None where the search passed its cap.
    pub found: Option<(u128, Vec<u64>, Vec<usize>)>,
    /// The work of the search, in units.
    pub work: u64,
}

/// The least body hash of the table `cells` over the leaves of the search, where
/// column `c` has the type name `names[c]` and, for its first color, `start[c]`.
/// At least two columns must tie. The search does at most `cap` units of work,
/// the setting `column_search_work_cap`.
pub(super) fn least_body(cells: &Cells<'_>, names: &[String], start: &[u128], cap: u64) -> Searched {
    let count = names.len();
    let mut ranked: Vec<&String> = names.iter().collect();
    ranked.sort();
    ranked.dedup();
    let kinds: Vec<u32> = names.iter().map(|name| ranked.binary_search(&name).expect("the name is among the names") as u32).collect();
    let mut search = Search { cells, cap, count, kinds, pairs: vec![0; count * count], work: 0, cut: false, whole: None, swaps: vec![None; count * count], leaf_work: cells.cell_count() };
    let found = search.run(start);
    Searched { found: if search.cut { None } else { found }, work: search.work }
}

struct Search<'c, 'a> {
    cells: &'c Cells<'a>,
    /// The most work the search does, in units.
    cap: u64,
    count: usize,
    /// The rank of each column's type name among the distinct type names.
    kinds: Vec<u32>,
    /// The pair hash of the columns `c` and `d`, at `c * count + d`, for each column `c` that ties at the first coloring.
    pairs: Vec<u128>,
    work: u64,
    cut: bool,
    /// The body hash of the table with its columns in their places.
    whole: Option<u128>,
    /// Whether the columns `a` and `b` are exchangeable, at `a * count + b` for `a < b`.
    swaps: Vec<Option<bool>>,
    /// The units of a leaf: the cells that its body hash hashes.
    leaf_work: u64,
}

impl Search<'_, '_> {
    /// Counts `units` of work, and whether the search is still within its cap.
    fn charge(&mut self, units: u64) -> bool {
        self.work = self.work.saturating_add(units);
        if self.work > self.cap {
            self.cut = true;
        }
        !self.cut
    }

    fn run(&mut self, start: &[u128]) -> Option<(u128, Vec<u64>, Vec<usize>)> {
        let count = self.count;
        let tied = self.tied(start);
        // The pair hashes of the columns that tie, with every other column.
        let rows = self.cells.table_rows();
        let mut pair_work: u64 = 0;
        for &column in &tied {
            for other in (0..count).filter(|&other| other != column) {
                pair_work = pair_work.saturating_add(rows.saturating_mul((self.cells.width_of(column) + self.cells.width_of(other)) as u64));
            }
        }
        if !self.charge(pair_work) {
            return None;
        }
        for &column in &tied {
            for other in (0..count).filter(|&other| other != column) {
                self.pairs[column * count + other] = self.cells.runs(&[column, other]);
            }
        }
        let mut colors = start.to_vec();
        self.refine(&mut colors);
        // The swaps of the columns of each class that the first refinement leaves: counted before any is made, so the count is that of the table's content.
        let classes = self.classes(&colors);
        let swaps: u64 = classes.iter().map(|class| (class.len() * (class.len() - 1) / 2) as u64).sum();
        if swaps > 0 && !self.charge(swaps.saturating_add(1).saturating_mul(self.leaf_work)) {
            return None;
        }
        let mut best = None;
        self.visit(colors, &mut best);
        best
    }

    /// The columns whose type name and color another column has.
    fn tied(&self, colors: &[u128]) -> Vec<usize> {
        (0..self.count).filter(|&column| (0..self.count).any(|other| other != column && self.kinds[other] == self.kinds[column] && colors[other] == colors[column])).collect()
    }

    /// The count of distinct (type name, color) among the columns `of`.
    fn class_count(&self, colors: &[u128], of: &[usize]) -> usize {
        let mut keys: Vec<(u32, u128)> = of.iter().map(|&column| (self.kinds[column], colors[column])).collect();
        keys.sort_unstable();
        keys.dedup();
        keys.len()
    }

    /// The classes of more than one column, each as its columns in ascending order, in the order of type name and color.
    fn classes(&self, colors: &[u128]) -> Vec<Vec<usize>> {
        let mut order: Vec<usize> = (0..self.count).collect();
        order.sort_by_key(|&column| (self.kinds[column], colors[column], column));
        let key = |at: usize| (self.kinds[order[at]], colors[order[at]]);
        let mut classes = Vec::new();
        let mut start = 0;
        while start < order.len() {
            let end = (start..order.len()).find(|&at| key(at) != key(start)).unwrap_or(order.len());
            if end - start > 1 {
                classes.push(order[start..end].to_vec());
            }
            start = end;
        }
        classes
    }

    /// Refines `colors` while the refinement splits a class.
    fn refine(&self, colors: &mut Vec<u128>) {
        let count = self.count;
        let mut open = self.tied(colors);
        while !open.is_empty() {
            let mut next = colors.clone();
            for &column in &open {
                let mut around: Vec<(u32, u128, u128)> = (0..count).filter(|&other| other != column).map(|other| (self.kinds[other], colors[other], self.pairs[column * count + other])).collect();
                around.sort_unstable();
                let mut hasher = StableHasher::new();
                hasher.write(b"arclog.table.refined");
                hasher.write_u128(colors[column]);
                for (kind, color, pair) in around {
                    hasher.write_u32(kind);
                    hasher.write_u128(color);
                    hasher.write_u128(pair);
                }
                next[column] = hasher.finish128().0;
            }
            if self.class_count(&next, &open) == self.class_count(colors, &open) {
                return;
            }
            *colors = next;
            open = self.tied(colors);
        }
    }

    /// Whether the table has the body hash that it has when the contents of the columns `a` and `b` are swapped.
    fn exchangeable(&mut self, a: usize, b: usize) -> bool {
        let (a, b) = (a.min(b), a.max(b));
        if self.cells.width_of(a) != self.cells.width_of(b) {
            return false;
        }
        if let Some(known) = self.swaps[a * self.count + b] {
            return known;
        }
        let mut order: Vec<usize> = (0..self.count).collect();
        let whole = match self.whole {
            Some(whole) => whole,
            None => {
                let whole = self.cells.body(&order);
                self.whole = Some(whole);
                whole
            }
        };
        order.swap(a, b);
        let same = self.cells.body(&order) == whole;
        self.swaps[a * self.count + b] = Some(same);
        same
    }

    /// One node of the search: refines `colors`, then, at a leaf, keeps the
    /// least body hash, and at any other node visits a child for each column of the
    /// target class that no column before it in the class is exchangeable with.
    /// Returns false where the search passed the cap.
    fn visit(&mut self, mut colors: Vec<u128>, best: &mut Option<(u128, Vec<u64>, Vec<usize>)>) -> bool {
        if !self.charge(NODE_WORK) {
            return false;
        }
        self.refine(&mut colors);
        let classes = self.classes(&colors);
        let Some(target) = classes.iter().fold(None::<&Vec<usize>>, |held, class| match held {
            Some(held) if held.len() >= class.len() => Some(held),
            _ => Some(class),
        }) else {
            if !self.charge(self.leaf_work) {
                return false;
            }
            let mut order: Vec<usize> = (0..self.count).collect();
            order.sort_by_key(|&column| (self.kinds[column], colors[column]));
            let (body, hashes) = self.cells.body_examples(&order);
            if best.as_ref().is_none_or(|(held, _, _)| body < *held) {
                *best = Some((body, hashes, order));
            }
            return true;
        };
        let mut kept: Vec<usize> = Vec::new();
        for &column in target {
            if kept.iter().any(|&earlier| self.exchangeable(earlier, column)) {
                continue;
            }
            kept.push(column);
            let mut child = colors.clone();
            let mut hasher = StableHasher::new();
            hasher.write(b"arclog.table.individualized");
            hasher.write_u128(colors[column]);
            child[column] = hasher.finish128().0;
            if !self.visit(child, best) {
                return false;
            }
        }
        true
    }
}
