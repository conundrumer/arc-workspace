//! The rows of a `join`, as the relations they come from.
//!
//! A [`Joined`] holds tables, the nodes, and equalities between a column of one node and a column of another. Its rows are every choice of one row from each node that agrees on each equality. The nodes and the node pairs that the equalities name form a tree, and each node after the first has a parent. A node pair holds all its equalities as one key. A `join` of two tables is two nodes and the pairs of its columns. A `join` or a `select` over a [`Joined`] adds nodes, equalities or a filter of one node's rows, and never the rows themselves.
//!
//! The count of the rows is the sum, over the rows of the first node, of the product over its children of the sum over their rows at its key, and so on down the tree. A count of rows grouped by some columns, and the distinct tuples of the rows at some columns, are read from the nodes that hold the columns and the nodes that join them: a node with no column asked for tells only whether a row has a partner. An operator whose value depends on the distinct tuples of the rows at some columns reads those tuples. Any other operator reads the rows written out, once.
//!
//! A relation's rows are a set, so the rows of the join are distinct: each row holds a row of every node, and each column of a node is a column of the join or equals one.

use std::cmp::Ordering;
use std::collections::BTreeMap;
use std::sync::{Arc, Mutex, OnceLock};

use crate::bounds::Bound;
use crate::boxes::{project_tuples, second_columns};
use crate::columns::Columns;
use crate::expression::Op;
use crate::gen_constants::number_bits;
use crate::gen_parts::PartStep;
use crate::native::{all, hash_words, holds, key_word, project, Cell, FastMap, KeyIndex, Part, Step, Table, Val, CELL_CAP};

/// Marks the hash of a [`Joined`], which no other value's hash has.
const JOINED_WORD: u64 = 0x4a6f_696e_6564_5273;

/// The most cells of the tables of `Joined::rows_at` that one value keeps for later readers.
const SKETCH_KEPT: usize = 1 << 18;

/// The id of a row of a parent that no row of its child pairs with.
const NO_PARTNER: u32 = u32::MAX;

/// The most pairs of rows that a `select` over two nodes tests.
const PAIR_WORK: usize = 1 << 26;

/// Where a column of the join stands: a place of a node's table.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct Place {
    node: usize,
    at: usize,
}

/// An equality between two places, which stand in two nodes or in one.
type Equality = (Place, Place);

/// How a node stands to its parent, and what the key of the two tells.
struct Link {
    parent: usize,
    /// The places of the key in the node's table, and in the parent's table, pair by pair.
    own: Vec<usize>,
    parent_places: Vec<usize>,
    /// The id of each of the node's rows' key.
    ids: Vec<u32>,
    /// The id of each of the parent's rows' key, or `NO_PARTNER` where no row of the node holds it.
    parent_ids: Vec<u32>,
    /// For each id, the count of rows below the node, summed over its rows at the id.
    weights: Vec<u64>,
}

pub struct Joined {
    nodes: Vec<Arc<Table>>,
    /// The link of node `at` is `links[at - 1]`, and the parent of a node stands before it.
    links: Vec<Link>,
    /// For each column of the join, where it stands.
    places: Vec<Place>,
    hash: u128,
    /// The count of rows of the join.
    rows: u64,
    /// The rows, once written: no value where they pass the output limit.
    written: OnceLock<Val>,
    /// For each node, whether each of its rows stands in a row of the join.
    live: OnceLock<Vec<Vec<bool>>>,
    /// The distinct tuples at some columns, by those columns, and the cells that the kept tables hold.
    sketches: Mutex<(usize, FastMap<Box<[u16]>, Arc<Sketch>>)>,
}

/// The distinct tuples of the rows of a join at the columns `key`.
struct Sketch {
    /// The tuples in order, as a table of the key's columns, or no table where a column is not one of the join.
    tuples: Option<Arc<Table>>,
    /// The tuples as rows of the join's width, with 0 at each column that is not in the key, once something has read them.
    wide: OnceLock<Arc<Table>>,
}

/// The distinct tuples of the rows of a join at the columns `key`, in order, each with the count of rows of the join that hold it.
struct Counted {
    tuples: Vec<Cell>,
    weights: Vec<u64>,
    /// The tuples as rows of the join's width, with 0 at each column that is not in the key, once something has read them.
    wide: OnceLock<Arc<Table>>,
}

impl Counted {
    /// The tuples as rows of `width` cells, with 0 at each column that is not in `key`.
    fn wide(&self, key: &[u16], width: usize) -> Arc<Table> {
        self.wide
            .get_or_init(|| {
                let mut cells: Vec<Cell> = vec![0; self.weights.len() * width];
                for (row, tuple) in cells.chunks_exact_mut(width).zip(self.tuples.chunks_exact(key.len())) {
                    for (column, cell) in key.iter().zip(tuple) {
                        row[usize::from(*column)] = *cell;
                    }
                }
                Table::new(width, cells)
            })
            .clone()
    }
}

/// The most cells that the answers a thread keeps for later reads hold in all. Once it holds that many, it keeps the answers it has until `clear_shared`, and adds no more.
const SHARED_CELLS: usize = 8_000_000;

/// What the reads of the joins on one thread keep for later reads, by the join's hash and the key. It holds the answers that a join does not keep itself, because they pass `SKETCH_KEPT`, so that a second read of the same join at the same columns does not group the join's rows again.
#[derive(Default)]
struct Shared {
    sketches: FastMap<u128, Arc<Sketch>>,
    counted: FastMap<u128, Arc<Counted>>,
    cells: usize,
}

thread_local! {
    static SHARED: std::cell::RefCell<Shared> = std::cell::RefCell::new(Shared::default());
}

/// Drops what this thread keeps of the joins' answers.
pub fn clear_shared() {
    SHARED.with(|shared| *shared.borrow_mut() = Shared::default());
}

/// Keeps `sketch`, which is at `at`, for later reads, and counts `cells` more cells held, where the thread then holds no more than the most it keeps. Otherwise it keeps nothing more, and gives false.
fn share_sketch(at: u128, sketch: &Arc<Sketch>, cells: usize) -> bool {
    SHARED.with(|shared| {
        let mut shared = shared.borrow_mut();
        if shared.cells + cells > SHARED_CELLS {
            return false;
        }
        shared.cells += cells;
        shared.sketches.insert(at, sketch.clone());
        true
    })
}

/// The place of the tuple that `row` holds at the columns `key` among `tuples`, which stand in order, `key.len()` cells each. The search starts at place `near` and runs on from it, so that rows asked in order of their tuples find theirs after a few steps, and a row asked out of order is found all the same.
fn tuple_place(tuples: &[Cell], key: &[u16], row: &[Cell], near: usize) -> Option<usize> {
    let stride = key.len();
    let count = tuples.len().checked_div(stride)?;
    if count == 0 {
        return None;
    }
    // A key of at most four columns is read from the row once.
    let mut small: [Cell; 4] = [0; 4];
    let short = stride <= small.len();
    if short {
        for (slot, column) in small.iter_mut().zip(key) {
            *slot = row[usize::from(*column)];
        }
    }
    let order = |at: usize| -> Ordering {
        let tuple = &tuples[at * stride..(at + 1) * stride];
        if short {
            tuple.cmp(&small[..stride])
        } else {
            tuple.iter().zip(key).map(|(cell, column)| cell.cmp(&row[usize::from(*column)])).find(|order| order.is_ne()).unwrap_or(Ordering::Equal)
        }
    };
    let near = near.min(count - 1);
    // The places from `low` on, up to `high`, hold the first tuple that is not below the row's, if there is one.
    let (mut low, mut high) = match order(near) {
        Ordering::Equal => return Some(near),
        Ordering::Greater => (0, near),
        Ordering::Less => {
            let mut low = near + 1;
            let mut step = 1;
            let high = loop {
                let probe = near + step;
                if probe >= count {
                    break count;
                }
                if order(probe) == Ordering::Less {
                    low = probe + 1;
                    step *= 2;
                } else {
                    break probe + 1;
                }
            };
            (low, high)
        }
    };
    while low < high {
        let middle = low + (high - low) / 2;
        if order(middle) == Ordering::Less {
            low = middle + 1;
        } else {
            high = middle;
        }
    }
    (low < count && order(low) == Ordering::Equal).then_some(low)
}

impl Drop for Joined {
    fn drop(&mut self) {
        crate::native::lazy_dropped(self.written.get());
    }
}

impl std::fmt::Debug for Joined {
    fn fmt(&self, out: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(out, "Joined {{ nodes: {}, rows: {} }}", self.nodes.len(), self.rows)
    }
}

/// The rows of a sorted table whose first cell is an id, as the runs of one id: the id, and the first row and the end of its run.
fn runs(cells: &[Cell], stride: usize) -> Vec<(u32, usize, usize)> {
    let mut out: Vec<(u32, usize, usize)> = Vec::new();
    for (at, row) in cells.chunks_exact(stride).enumerate() {
        match out.last_mut() {
            Some(last) if last.0 == row[0] => last.2 = at + 1,
            _ => out.push((row[0], at, at + 1)),
        }
    }
    out
}

/// The runs of the same id in two lists of runs, each in order of id.
fn common(a: &[(u32, usize, usize)], b: &[(u32, usize, usize)]) -> Vec<((usize, usize), (usize, usize))> {
    let (mut i, mut j) = (0, 0);
    let mut out = Vec::new();
    while i < a.len() && j < b.len() {
        match a[i].0.cmp(&b[j].0) {
            Ordering::Less => i += 1,
            Ordering::Greater => j += 1,
            Ordering::Equal => {
                out.push(((a[i].1, a[i].2), (b[j].1, b[j].2)));
                i += 1;
                j += 1;
            }
        }
    }
    out
}

/// A row of at most four cells as one number whose order is the order of the rows of that width.
trait Packed: Copy + Ord {
    fn pack(row: &[Cell]) -> Self;
    /// The cells of the row of `stride` cells that the number stands for, appended to `out`.
    fn unpack(self, stride: usize, out: &mut Vec<Cell>);
}

impl Packed for u32 {
    #[inline]
    fn pack(row: &[Cell]) -> u32 {
        row[0]
    }

    #[inline]
    fn unpack(self, _: usize, out: &mut Vec<Cell>) {
        out.push(self);
    }
}

impl Packed for u64 {
    #[inline]
    fn pack(row: &[Cell]) -> u64 {
        row.iter().fold(0u64, |held, cell| (held << 32) | u64::from(*cell))
    }

    #[inline]
    fn unpack(self, stride: usize, out: &mut Vec<Cell>) {
        for place in (0..stride).rev() {
            out.push((self >> (32 * place)) as u32);
        }
    }
}

impl Packed for u128 {
    #[inline]
    fn pack(row: &[Cell]) -> u128 {
        row.iter().fold(0u128, |held, cell| (held << 32) | u128::from(*cell))
    }

    #[inline]
    fn unpack(self, stride: usize, out: &mut Vec<Cell>) {
        for place in (0..stride).rev() {
            out.push((self >> (32 * place)) as u32);
        }
    }
}

/// The rows of `flat`, which stand `stride` cells wide, in order, each once, and the sum of the `weights` of each, with the rows packed into numbers where they are at most four cells wide.
fn sum_runs(flat: &[Cell], stride: usize, weights: &[u64]) -> (Vec<Cell>, Vec<u64>) {
    match stride {
        1 => sum_packed::<u32>(flat, stride, weights),
        2 => sum_packed::<u64>(flat, stride, weights),
        3 | 4 => sum_packed::<u128>(flat, stride, weights),
        _ => {
            let count = flat.len() / stride;
            let mut order: Vec<u32> = (0..count as u32).collect();
            order.sort_unstable_by(|a, b| flat[*a as usize * stride..(*a as usize + 1) * stride].cmp(&flat[*b as usize * stride..(*b as usize + 1) * stride]));
            let mut rows: Vec<Cell> = Vec::new();
            let mut sums: Vec<u64> = Vec::new();
            for at in order {
                let row = &flat[at as usize * stride..(at as usize + 1) * stride];
                let weight = weights[at as usize];
                if !sums.is_empty() && rows[rows.len() - stride..] == *row {
                    let last = sums.len() - 1;
                    sums[last] = sums[last].saturating_add(weight);
                } else {
                    rows.extend_from_slice(row);
                    sums.push(weight);
                }
            }
            (rows, sums)
        }
    }
}

fn sum_packed<K: Packed>(flat: &[Cell], stride: usize, weights: &[u64]) -> (Vec<Cell>, Vec<u64>) {
    let mut keyed: Vec<(K, u64)> = flat.chunks_exact(stride).zip(weights).map(|(row, weight)| (K::pack(row), *weight)).collect();
    keyed.sort_unstable_by(|a, b| a.0.cmp(&b.0));
    let distinct = usize::from(!keyed.is_empty()) + keyed.windows(2).filter(|pair| pair[0].0 != pair[1].0).count();
    let mut rows: Vec<Cell> = Vec::with_capacity(distinct * stride);
    let mut sums: Vec<u64> = Vec::with_capacity(distinct);
    let mut last: Option<K> = None;
    for (row, weight) in keyed {
        if last == Some(row) {
            let at = sums.len() - 1;
            sums[at] = sums[at].saturating_add(weight);
        } else {
            row.unpack(stride, &mut rows);
            sums.push(weight);
            last = Some(row);
        }
    }
    (rows, sums)
}

/// The rows of `flat`, which stand `stride` cells wide, in order, each once.
fn distinct_runs(flat: &[Cell], stride: usize) -> Vec<Cell> {
    match stride {
        1 => distinct_packed::<u32>(flat, stride),
        2 => distinct_packed::<u64>(flat, stride),
        3 | 4 => distinct_packed::<u128>(flat, stride),
        _ => {
            let mut rows: Vec<&[Cell]> = flat.chunks_exact(stride).collect();
            rows.sort_unstable();
            rows.dedup();
            let mut out = Vec::with_capacity(rows.len() * stride);
            for row in rows {
                out.extend_from_slice(row);
            }
            out
        }
    }
}

fn distinct_packed<K: Packed>(flat: &[Cell], stride: usize) -> Vec<Cell> {
    let mut keys: Vec<K> = flat.chunks_exact(stride).map(K::pack).collect();
    keys.sort_unstable();
    keys.dedup();
    let mut rows: Vec<Cell> = Vec::with_capacity(keys.len() * stride);
    for key in keys {
        key.unpack(stride, &mut rows);
    }
    rows
}

/// The table of the rows of `table` that `keep` holds of; the table itself where all of them pass.
fn filtered(table: &Arc<Table>, keep: impl Fn(&[Cell]) -> bool) -> Arc<Table> {
    if table.all_rows(&keep) {
        table.clone()
    } else {
        table.filter_rows(keep)
    }
}

/// The nodes, equalities and columns of a join in the making.
struct Lifted {
    nodes: Vec<Arc<Table>>,
    equalities: Vec<Equality>,
    places: Vec<Place>,
}

impl Lifted {
    /// A value as nodes: a join as its own, and rows of one part as that part's table. No value for any other.
    fn of(value: &Val) -> Option<Lifted> {
        match value {
            Val::Joined(joined) => Some(Lifted { nodes: joined.nodes.clone(), equalities: joined.equalities(), places: joined.places.clone() }),
            Val::Rows(parts) => {
                let [part] = parts.as_slice() else { return None };
                if part.table.arity == 0 || part.columns.len() != part.table.arity {
                    return None;
                }
                let places: Vec<Place> = (0..part.columns.len() as u16).map(|column| part.columns.iter().position(|own| *own == column).map(|at| Place { node: 0, at })).collect::<Option<_>>()?;
                Some(Lifted { nodes: vec![part.table.clone()], equalities: Vec::new(), places })
            }
            _ => None,
        }
    }
}

/// The value of `step` over `first` and `second`, where one of them is the rows of a `join` and the step is a `join` or a `select`: the join of more tables, or one with a node filtered. No value where the form does not allow it, which leaves the rows to be written out.
pub fn extend(step: &Step, first: &Val, second: Option<&Val>) -> Option<Val> {
    match step {
        Step::Join { left, right, kept, left_arity } => {
            let second = second?;
            if !matches!(first, Val::Joined(_)) && !matches!(second, Val::Joined(_)) {
                return None;
            }
            if matches!(first, Val::Empty) || matches!(second, Val::Empty) {
                return Some(Val::Empty);
            }
            let (l, r) = (Lifted::of(first)?, Lifted::of(second)?);
            join_lifted(l, r, left, right, kept, *left_arity)
        }
        Step::Select { at, op, other, drop } => match first {
            Val::Joined(joined) => joined.select(*at, *op, *other, *drop),
            _ => None,
        },
        _ => None,
    }
}

/// The join of two lifted values on the paired columns `left_at` and `right_at`, where `kept` is the right columns that no pair names and the left has `left_arity` columns.
fn join_lifted(left: Lifted, right: Lifted, left_at: &[u16], right_at: &[u16], kept: &[u16], left_arity: u16) -> Option<Val> {
    if left_at.is_empty() || left_at.len() != right_at.len() || left.places.len() != usize::from(left_arity) {
        return None;
    }
    let offset = left.nodes.len();
    let moved = |place: Place| Place { node: place.node + offset, at: place.at };
    let mut equalities = left.equalities;
    equalities.extend(right.equalities.iter().map(|(a, b)| (moved(*a), moved(*b))));
    for (l, r) in left_at.iter().zip(right_at) {
        equalities.push((*left.places.get(usize::from(*l))?, moved(*right.places.get(usize::from(*r))?)));
    }
    let mut places = left.places;
    for column in kept {
        places.push(moved(*right.places.get(usize::from(*column))?));
    }
    let mut nodes = left.nodes;
    nodes.extend(right.nodes);
    build(nodes, equalities, places)
}

/// The join of the tables in `nodes` whose equalities are `equalities`, with the columns `places`. The tables of nodes that an equality between two of their own columns names are filtered. No value where the equalities between nodes do not form a tree. The first node stays the first.
fn build(mut nodes: Vec<Arc<Table>>, equalities: Vec<Equality>, places: Vec<Place>) -> Option<Val> {
    let mut same: Vec<Vec<(usize, usize)>> = vec![Vec::new(); nodes.len()];
    let mut edges: BTreeMap<(usize, usize), Vec<(usize, usize)>> = BTreeMap::new();
    for (a, b) in equalities {
        if a.node == b.node {
            same[a.node].push((a.at, b.at));
        } else if a.node < b.node {
            edges.entry((a.node, b.node)).or_default().push((a.at, b.at));
        } else {
            edges.entry((b.node, a.node)).or_default().push((b.at, a.at));
        }
    }
    for (node, pairs) in same.iter().enumerate() {
        if !pairs.is_empty() {
            nodes[node] = filtered(&nodes[node], |row| pairs.iter().all(|(a, b)| row[*a] == row[*b]));
        }
    }
    if nodes.iter().any(|table| table.len == 0) {
        return Some(Val::Empty);
    }
    for pairs in edges.values_mut() {
        pairs.sort_unstable();
        pairs.dedup();
    }
    // The node pairs must make a tree of all the nodes.
    let count = nodes.len();
    let mut root: Vec<usize> = (0..count).collect();
    fn find(root: &mut [usize], mut at: usize) -> usize {
        while root[at] != at {
            root[at] = root[root[at]];
            at = root[at];
        }
        at
    }
    for (a, b) in edges.keys() {
        let (ra, rb) = (find(&mut root, *a), find(&mut root, *b));
        if ra == rb {
            return None;
        }
        root[ra] = rb;
    }
    if edges.len() + 1 != count {
        return None;
    }
    if count == 1 {
        // One table is the rows themselves.
        let table = nodes.pop()?;
        let mut columns = vec![u16::MAX; table.arity];
        for (position, place) in places.iter().enumerate() {
            if place.node != 0 || place.at >= table.arity || columns[place.at] != u16::MAX {
                return None;
            }
            columns[place.at] = position as u16;
        }
        if columns.contains(&u16::MAX) {
            return None;
        }
        return Some(Val::Rows(Arc::new(vec![Part { table, columns: columns.into_boxed_slice() }])));
    }
    // The nodes in order of their distance from the first, so that a parent stands before its children.
    let mut adjacent: Vec<Vec<usize>> = vec![Vec::new(); count];
    for (a, b) in edges.keys() {
        adjacent[*a].push(*b);
        adjacent[*b].push(*a);
    }
    let mut order: Vec<usize> = vec![0];
    let mut parent_of: Vec<usize> = vec![usize::MAX; count];
    let mut seen = vec![false; count];
    seen[0] = true;
    let mut head = 0;
    while head < order.len() {
        let node = order[head];
        head += 1;
        let mut next = adjacent[node].clone();
        next.sort_unstable();
        for other in next {
            if !seen[other] {
                seen[other] = true;
                parent_of[other] = node;
                order.push(other);
            }
        }
    }
    let mut rank = vec![0usize; count];
    for (at, node) in order.iter().enumerate() {
        rank[*node] = at;
    }
    let tables: Vec<Arc<Table>> = order.iter().map(|node| nodes[*node].clone()).collect();
    let places: Vec<Place> = places.into_iter().map(|place| Place { node: rank[place.node], at: place.at }).collect();
    let mut links: Vec<Link> = Vec::with_capacity(count - 1);
    for (at, node) in order.iter().enumerate().skip(1) {
        let parent = parent_of[*node];
        let pairs = &edges[&(parent.min(*node), parent.max(*node))];
        let (parent_places, own): (Vec<usize>, Vec<usize>) = if parent < *node { pairs.iter().copied().unzip() } else { pairs.iter().map(|(a, b)| (*b, *a)).unzip() };
        let keys: Vec<u64> = tables[at].rows().map(|row| key_word(row, &own)).collect();
        let (index, ids) = KeyIndex::of(&keys);
        let groups = ids.iter().max().map_or(0, |last| *last as usize + 1);
        let parent_ids: Vec<u32> = tables[rank[parent]].rows().map(|row| index.get(key_word(row, &parent_places)).unwrap_or(NO_PARTNER)).collect();
        links.push(Link { parent: rank[parent], own, parent_places, ids, parent_ids, weights: vec![0; groups] });
    }
    // The rows below each node, from the last node up.
    let mut below: Vec<Vec<u64>> = tables.iter().map(|table| vec![1u64; table.len]).collect();
    for at in (1..count).rev() {
        let mut weights = vec![0u64; links[at - 1].weights.len()];
        for (row, id) in links[at - 1].ids.iter().enumerate() {
            weights[*id as usize] = weights[*id as usize].saturating_add(below[at][row]);
        }
        let parent = links[at - 1].parent;
        for (row, id) in links[at - 1].parent_ids.iter().enumerate() {
            let weight = if *id == NO_PARTNER { 0 } else { weights[*id as usize] };
            below[parent][row] = below[parent][row].saturating_mul(weight);
        }
        links[at - 1].weights = weights;
    }
    let rows = below[0].iter().fold(0u64, |total, own| total.saturating_add(*own));
    if rows == 0 {
        return Some(Val::Empty);
    }
    let mut words: Vec<u64> = vec![JOINED_WORD, count as u64];
    for table in &tables {
        let hash = table.hash();
        words.extend([hash as u64, (hash >> 64) as u64]);
    }
    for link in &links {
        words.extend([link.parent as u64, link.own.len() as u64]);
        words.extend(link.own.iter().map(|at| *at as u64));
        words.extend(link.parent_places.iter().map(|at| *at as u64));
    }
    words.push(u64::MAX);
    for place in &places {
        words.extend([place.node as u64, place.at as u64]);
    }
    let hash = hash_words(words);
    Some(Val::Joined(Arc::new(Joined { nodes: tables, links, places, hash, rows, written: OnceLock::new(), live: OnceLock::new(), sketches: Mutex::new((0, FastMap::default())) })))
}

/// The rows of `grouped` of one node: for each key of the node's parent, the tuples of the key columns below the node, with their counts.
struct Rel {
    /// The index into the key of each column of a tuple.
    cols: Vec<usize>,
    stride: usize,
    flat: Vec<Cell>,
    /// The count of each entry, or none where the counts are not asked for.
    weights: Vec<u64>,
    /// For each id of the node's key, the first entry and the end of its run.
    ranges: Vec<(usize, usize)>,
}

/// Appends to `tuples` the tuples of a group: its `head` cells, then the cells of one entry of each of `rels` in the run that the group's ids in `ids` pick, for each choice of entries. Each cell of a tuple stands at the place that `positions` gives for its place in that order. Where `sums` is some, it gets the product of `weight` and the counts of the entries, for each of the tuples.
#[allow(clippy::too_many_arguments)]
fn expand(rels: &[&Rel], head: &[Cell], ids: &[Cell], positions: &[usize], weight: u64, tuples: &mut Vec<Cell>, mut sums: Option<&mut Vec<u64>>, spans: &mut Vec<(usize, usize)>) {
    let stride = positions.len();
    spans.clear();
    let mut count = 1usize;
    for (rel, id) in rels.iter().zip(ids) {
        let (from, to) = rel.ranges[*id as usize];
        spans.push((from, to - from));
        count *= to - from;
    }
    if count == 0 {
        return;
    }
    let base = tuples.len();
    tuples.resize(base + count * stride, 0);
    let out = &mut tuples[base..];
    for tuple in out.chunks_exact_mut(stride) {
        for (cell, place) in head.iter().zip(positions) {
            tuple[*place] = *cell;
        }
    }
    let sums_base = sums.as_ref().map_or(0, |sums| sums.len());
    if let Some(sums) = sums.as_deref_mut() {
        sums.resize(sums_base + count, weight);
    }
    let mut repeat = count;
    let mut offset = head.len();
    for (rel, (from, len)) in rels.iter().zip(spans.iter()) {
        repeat /= len;
        let width = rel.stride - 1;
        let places = &positions[offset..offset + width];
        let mut tuple = 0usize;
        while tuple < count {
            for entry in *from..from + len {
                let cells = &rel.flat[entry * rel.stride + 1..(entry + 1) * rel.stride];
                for at in tuple..tuple + repeat {
                    let target = &mut out[at * stride..(at + 1) * stride];
                    for (cell, place) in cells.iter().zip(places) {
                        target[*place] = *cell;
                    }
                }
                if let Some(sums) = sums.as_deref_mut() {
                    for sum in &mut sums[sums_base + tuple..sums_base + tuple + repeat] {
                        *sum = sum.saturating_mul(rel.weights[entry]);
                    }
                }
                tuple += repeat;
            }
        }
        offset += width;
    }
}

impl Joined {
    /// The join of `left` and `right` on the paired columns `left_at` and `right_at`, where `left_columns` and `right_columns` give the column of each table's columns, `kept` is the right columns that no pair names, and the left has `left_arity` columns: no rows where no row of one side has a partner. No value where a column is not at a table.
    #[allow(clippy::too_many_arguments)]
    pub fn of(left: Arc<Table>, left_columns: Vec<u16>, right: Arc<Table>, right_columns: Vec<u16>, left_at: &[u16], right_at: &[u16], kept: &[u16], left_arity: u16) -> Option<Val> {
        let place = |columns: &[u16], at: u16| columns.iter().position(|column| *column == at);
        if left_columns.len() != usize::from(left_arity) {
            return None;
        }
        let right_places: Vec<usize> = right_at.iter().map(|at| place(&right_columns, *at)).collect::<Option<_>>()?;
        let unpaired: Vec<usize> = (0..right_columns.len()).filter(|at| !right_places.contains(at)).collect();
        if unpaired.len() != kept.len() || unpaired.iter().any(|at| !kept.contains(&right_columns[*at])) {
            return None;
        }
        let mut equalities: Vec<Equality> = Vec::with_capacity(left_at.len());
        for (l, r) in left_at.iter().zip(&right_places) {
            equalities.push((Place { node: 0, at: place(&left_columns, *l)? }, Place { node: 1, at: *r }));
        }
        let mut places: Vec<Place> = Vec::with_capacity(left_columns.len() + kept.len());
        for column in 0..left_arity {
            places.push(Place { node: 0, at: place(&left_columns, column)? });
        }
        for column in kept {
            places.push(Place { node: 1, at: place(&right_columns, *column)? });
        }
        build(vec![left, right], equalities, places)
    }

    /// The join of `left` and `right` that a `select` makes of two parts, where it equates the column at `left_at` of the left table with the column at `right_at` of the right table, and drops the right one. `left_out` and `right_out` give the column of the select's rows for each column of each table; the right column at `right_at` has none. They name each column of the select's rows once. No value where they do not.
    pub fn across(left: Arc<Table>, left_out: &[u16], right: Arc<Table>, right_out: &[u16], left_at: usize, right_at: usize) -> Option<Val> {
        if left_out.len() != left.arity || right_out.len() != right.arity || left_at >= left.arity || right_at >= right.arity {
            return None;
        }
        let mut slots: Vec<Option<Place>> = vec![None; left.arity + right.arity - 1];
        let own = (0..left.arity).map(|at| (Place { node: 0, at }, left_out[at])).chain((0..right.arity).filter(|at| *at != right_at).map(|at| (Place { node: 1, at }, right_out[at])));
        for (place, column) in own {
            let slot = slots.get_mut(usize::from(column))?;
            if slot.is_some() {
                return None;
            }
            *slot = Some(place);
        }
        let places: Vec<Place> = slots.into_iter().collect::<Option<_>>()?;
        build(vec![left, right], vec![(Place { node: 0, at: left_at }, Place { node: 1, at: right_at })], places)
    }

    /// The equalities that join each node to its parent.
    fn equalities(&self) -> Vec<Equality> {
        let mut out = Vec::new();
        for (at, link) in self.links.iter().enumerate() {
            for (parent_place, own) in link.parent_places.iter().zip(&link.own) {
                out.push((Place { node: link.parent, at: *parent_place }, Place { node: at + 1, at: *own }));
            }
        }
        out
    }

    /// The children of each node, in order.
    fn children(&self) -> Vec<Vec<usize>> {
        let mut out: Vec<Vec<usize>> = vec![Vec::new(); self.nodes.len()];
        for (at, link) in self.links.iter().enumerate() {
            out[link.parent].push(at + 1);
        }
        out
    }

    /// For each row of each node, the count of rows of the join below it: the product, over the node's children, of the count at its key.
    fn below(&self) -> Vec<Vec<u64>> {
        let mut below: Vec<Vec<u64>> = self.nodes.iter().map(|table| vec![1u64; table.len]).collect();
        for link in &self.links {
            for (row, id) in link.parent_ids.iter().enumerate() {
                let weight = if *id == NO_PARTNER { 0 } else { link.weights[*id as usize] };
                below[link.parent][row] = below[link.parent][row].saturating_mul(weight);
            }
        }
        below
    }

    /// For each node, whether each of its rows stands in a row of the join.
    fn live(&self) -> &Vec<Vec<bool>> {
        self.live.get_or_init(|| {
            let mut live: Vec<Vec<bool>> = self.below().iter().map(|rows| rows.iter().map(|count| *count > 0).collect()).collect();
            for (at, link) in self.links.iter().enumerate() {
                // A row of the node stands in a row of the join where its key is the key of a parent row that does.
                let mut reached = vec![false; link.weights.len()];
                for (row, id) in link.parent_ids.iter().enumerate() {
                    if *id != NO_PARTNER && live[link.parent][row] {
                        reached[*id as usize] = true;
                    }
                }
                for (row, id) in link.ids.iter().enumerate() {
                    live[at + 1][row] = live[at + 1][row] && reached[*id as usize];
                }
            }
            live
        })
    }

    /// The count of rows of the join.
    pub fn rows(&self) -> u64 {
        self.rows
    }

    pub fn hash(&self) -> u128 {
        self.hash
    }

    /// The count of columns of the join.
    pub fn width(&self) -> usize {
        self.places.len()
    }

    /// The cells that the nodes and the ids of the join hold, which a walker counts as held.
    pub fn held_cells(&self) -> usize {
        self.nodes.iter().map(|table| table.cell_count()).sum::<usize>() + self.links.iter().map(|link| link.ids.len() + link.parent_ids.len() + 2 * link.weights.len()).sum::<usize>()
    }

    /// Whether the rows of the join can be written out, in at most the output limit of cells.
    pub fn fits(&self) -> bool {
        self.rows.saturating_mul(self.width() as u64) <= crate::native::output_limit() as u64
    }

    /// The rows of the join written out, or no value where they pass the output limit.
    pub fn written(&self) -> Val {
        let held = self.written.get_or_init(|| {
            let value = self.write();
            crate::native::lazy_wrote(&value);
            value
        });
        if matches!(held, Val::None) {
            crate::bounds::mark(Bound::Walk);
        }
        held.clone()
    }

    fn write(&self) -> Val {
        if !self.fits() {
            return Val::None;
        }
        let below = self.below();
        // The rows of each node after the first that stand below a row, by the id of their key, in the order they stand.
        let mut by_id: Vec<(Vec<usize>, Vec<u32>)> = Vec::with_capacity(self.links.len());
        for (at, link) in self.links.iter().enumerate() {
            let mut starts: Vec<usize> = vec![0; link.weights.len() + 1];
            for (row, id) in link.ids.iter().enumerate() {
                if below[at + 1][row] > 0 {
                    starts[*id as usize + 1] += 1;
                }
            }
            for id in 1..starts.len() {
                starts[id] += starts[id - 1];
            }
            let mut next = starts.clone();
            let mut rows: Vec<u32> = vec![0; starts[starts.len() - 1]];
            for (row, id) in link.ids.iter().enumerate() {
                if below[at + 1][row] > 0 {
                    rows[next[*id as usize]] = row as u32;
                    next[*id as usize] += 1;
                }
            }
            by_id.push((starts, rows));
        }
        // The rows hold the columns of each node that the join names, node by node.
        let mut emit: Vec<(usize, usize, u16)> = self.places.iter().enumerate().map(|(position, place)| (place.node, place.at, position as u16)).collect();
        emit.sort_unstable();
        let mut cells: Vec<Cell> = Vec::with_capacity(self.rows as usize * emit.len());
        let mut chosen = vec![0usize; self.nodes.len()];
        for row in 0..self.nodes[0].len {
            if below[0][row] > 0 {
                chosen[0] = row;
                self.write_below(1, &mut chosen, &by_id, &emit, &mut cells);
            }
        }
        let columns: Box<[u16]> = emit.iter().map(|(_, _, position)| *position).collect();
        Val::Rows(Arc::new(vec![Part { table: Table::new(emit.len(), cells), columns }]))
    }

    /// The rows of the join that agree with the rows `chosen` of the nodes before `depth`, written to `cells`.
    fn write_below(&self, depth: usize, chosen: &mut [usize], by_id: &[(Vec<usize>, Vec<u32>)], emit: &[(usize, usize, u16)], cells: &mut Vec<Cell>) {
        if depth == self.nodes.len() {
            for (node, at, _) in emit {
                cells.push(self.nodes[*node].cells()[chosen[*node] * self.nodes[*node].arity + *at]);
            }
            return;
        }
        let link = &self.links[depth - 1];
        let id = link.parent_ids[chosen[link.parent]] as usize;
        let (starts, rows) = &by_id[depth - 1];
        for row in &rows[starts[id]..starts[id + 1]] {
            chosen[depth] = *row as usize;
            self.write_below(depth + 1, chosen, by_id, emit, cells);
        }
    }

    /// The places of the columns `key` of the join: no value where a column is not one of the join.
    fn at(&self, key: &[u16]) -> Option<Vec<Place>> {
        key.iter().map(|column| self.places.get(usize::from(*column)).copied()).collect()
    }

    /// The distinct tuples of the rows of the join at the columns `key`, which stand sorted and distinct, each with the count of rows of the join that hold it. The tuples stand in order, the cells of each in the order of `key`. Without `weighted`, the counts are not the rows' counts.
    fn grouped(&self, key: &[u16], weighted: bool) -> Option<(Vec<Cell>, Vec<u64>)> {
        let count = self.nodes.len();
        let at = self.at(key)?;
        let children = self.children();
        // The nodes whose subtree holds a column of the key.
        let mut has = vec![false; count];
        for place in &at {
            has[place.node] = true;
        }
        for node in (1..count).rev() {
            if has[node] {
                has[self.links[node - 1].parent] = true;
            }
        }
        let live = self.live();
        let mut rels: Vec<Option<Rel>> = (0..count).map(|_| None).collect();
        let mut result: Option<(Vec<Cell>, Vec<u64>)> = None;
        for node in (0..count).rev() {
            if !has[node] {
                continue;
            }
            let wanted: Vec<usize> = children[node].iter().copied().filter(|child| has[*child]).collect();
            let unwanted: Vec<usize> = children[node].iter().copied().filter(|child| !has[*child]).collect();
            let own: Vec<(usize, usize)> = at.iter().enumerate().filter(|(_, place)| place.node == node).map(|(index, place)| (index, place.at)).collect();
            let up = usize::from(node > 0);
            // The rows of the node, grouped by their key to the parent, their own columns, and the keys to the children that hold columns.
            let width = up + own.len() + wanted.len();
            let own_places: Vec<usize> = own.iter().map(|(_, place)| *place).collect();
            let mut flat: Vec<Cell> = Vec::new();
            let mut weights: Vec<u64> = Vec::new();
            for (row, cells) in self.nodes[node].rows().enumerate() {
                if !live[node][row] {
                    continue;
                }
                let start = flat.len();
                if node > 0 {
                    flat.push(self.links[node - 1].ids[row]);
                }
                flat.extend(own_places.iter().map(|place| cells[*place]));
                flat.extend(wanted.iter().map(|child| self.links[*child - 1].parent_ids[row]));
                // A child with no column of the key tells how many rows it adds.
                let weight = if weighted { unwanted.iter().fold(1u64, |total, child| total.saturating_mul(self.links[*child - 1].weights[self.links[*child - 1].parent_ids[row] as usize])) } else { 1 };
                // A row equal to the one before it adds to that one.
                if start >= width && flat[start - width..start] == flat[start..] {
                    flat.truncate(start);
                    if weighted {
                        let last = weights.len() - 1;
                        weights[last] = weights[last].saturating_add(weight);
                    }
                } else if weighted {
                    weights.push(weight);
                }
            }
            let (groups, counts) = if weighted { sum_runs(&flat, width, &weights) } else { (distinct_runs(&flat, width), Vec::new()) };
            let below: Vec<&Rel> = wanted.iter().map(|child| rels[*child].as_ref().expect("a child below a node is done first")).collect();
            let cols: Vec<usize> = own.iter().map(|(index, _)| *index).chain(below.iter().flat_map(|rel| rel.cols.iter().copied())).collect();
            let stride = up + cols.len();
            let mut total = 0usize;
            for group in groups.chunks_exact(width) {
                let product = below.iter().enumerate().fold(1usize, |product, (slot, rel)| {
                    let (from, to) = rel.ranges[group[up + own.len() + slot] as usize];
                    product.saturating_mul(to - from)
                });
                total = total.saturating_add(product);
            }
            // With no child that holds a column of the key, the groups are the tuples. Otherwise each group gives the tuples of the choices of its children's entries, and a root gives them in the key's own order.
            let (tuples, tuple_counts) = if below.is_empty() {
                (groups, counts)
            } else {
                let positions: Vec<usize> = if node == 0 { cols.clone() } else { (0..stride).collect() };
                let mut tuples: Vec<Cell> = Vec::with_capacity(total * stride);
                let mut sums: Vec<u64> = Vec::new();
                let mut spans: Vec<(usize, usize)> = Vec::with_capacity(below.len());
                for (index, group) in groups.chunks_exact(width).enumerate() {
                    let (head, ids) = group.split_at(up + own.len());
                    if weighted {
                        expand(&below, head, ids, &positions, counts[index], &mut tuples, Some(&mut sums), &mut spans);
                    } else {
                        expand(&below, head, ids, &positions, 1, &mut tuples, None, &mut spans);
                    }
                }
                if weighted { sum_runs(&tuples, stride, &sums) } else { (distinct_runs(&tuples, stride), Vec::new()) }
            };
            if node == 0 {
                result = Some((tuples, tuple_counts));
            } else {
                let mut ranges = vec![(0usize, 0usize); self.links[node - 1].weights.len()];
                for (id, from, to) in runs(&tuples, stride) {
                    ranges[id as usize] = (from, to);
                }
                rels[node] = Some(Rel { cols, stride, flat: tuples, weights: tuple_counts, ranges });
            }
        }
        result
    }

    /// The places of the table of each node that hold the columns `key`, node by node.
    fn places_in(&self, key: &[u16], node: usize) -> Vec<usize> {
        key.iter().filter_map(|column| self.places.get(usize::from(*column))).filter(|place| place.node == node).map(|place| place.at).collect()
    }

    /// The distinct tuples of the rows of the join at the columns `key`, which stand in order.
    fn sketch(&self, key: &[u16]) -> Arc<Sketch> {
        let held = self.sketches.lock().expect("a sketch lock").1.get(key).cloned();
        match held {
            Some(sketch) => sketch,
            None => {
                let at = self.shared_key(key);
                if let Some(found) = SHARED.with(|shared| shared.borrow().sketches.get(&at).cloned()) {
                    return found;
                }
                let sketch = Arc::new(Sketch { tuples: self.build_tuples(key), wide: OnceLock::new() });
                let cells = sketch.tuples.as_ref().map_or(0, |table| table.cell_count());
                let mut kept = self.sketches.lock().expect("a sketch lock");
                if kept.0 + cells <= SKETCH_KEPT {
                    kept.0 += cells;
                    kept.1.insert(key.into(), sketch.clone());
                } else {
                    drop(kept);
                    share_sketch(at, &sketch, cells);
                }
                sketch
            }
        }
    }

    /// The key of what a thread keeps of this join's answer at the columns `key`.
    fn shared_key(&self, key: &[u16]) -> u128 {
        hash_words([self.hash as u64, (self.hash >> 64) as u64, key.len() as u64].into_iter().chain(key.iter().map(|column| u64::from(*column))))
    }

    /// The distinct tuples of the rows of the join at the columns `key`, which stand sorted and distinct, each with the count of rows of the join that hold it, from what a thread kept of an earlier read where it holds this one. No value where a column is not one of the join.
    fn counted(&self, key: &[u16]) -> Option<Arc<Counted>> {
        let at = self.shared_key(key);
        if let Some(found) = SHARED.with(|shared| shared.borrow().counted.get(&at).cloned()) {
            return Some(found);
        }
        let (tuples, weights) = self.grouped(key, true)?;
        let cells = tuples.len() + weights.len() * (2 + self.width());
        let found = Arc::new(Counted { tuples, weights, wide: OnceLock::new() });
        // What would pass the most a thread keeps is not kept, and a later read groups the rows again.
        SHARED.with(|shared| {
            let mut shared = shared.borrow_mut();
            if shared.cells + cells <= SHARED_CELLS {
                shared.cells += cells;
                shared.counted.insert(at, found.clone());
            }
        });
        Some(found)
    }

    /// The columns `columns` in order.
    fn key_of(columns: &Columns) -> Box<[u16]> {
        let mut key: Vec<u16> = columns.to_vec();
        key.sort_unstable();
        key.into_boxed_slice()
    }

    /// A table in which the distinct tuples of the rows of the join stand at `columns`, as rows of the join's width with 0 at each other column. An operator whose value depends on those tuples alone has the same value on this table as on the rows written out.
    pub fn rows_at(&self, columns: &Columns) -> Option<Arc<Table>> {
        let key = Joined::key_of(columns);
        let sketch = self.sketch(&key);
        let tuples = sketch.tuples.as_ref()?;
        if let Some(wide) = sketch.wide.get() {
            return Some(wide.clone());
        }
        let width = self.width();
        let wide = if key.is_empty() {
            Table::new(width, vec![0; width])
        } else {
            // The tuples ascend and the key stands in order, so the rows ascend.
            let mut out: Vec<Cell> = vec![0; tuples.len * width];
            for (row, tuple) in out.chunks_exact_mut(width).zip(tuples.rows()) {
                for (column, cell) in key.iter().zip(tuple) {
                    row[usize::from(*column)] = *cell;
                }
            }
            Table::ascending(width, out)
        };
        let cells = wide.cell_count();
        let mut kept = self.sketches.lock().expect("a sketch lock");
        if kept.0 + cells <= SKETCH_KEPT {
            if sketch.wide.set(wide.clone()).is_ok() {
                kept.0 += cells;
            }
        } else {
            drop(kept);
            if share_sketch(self.shared_key(&key), &sketch, cells) {
                let _ = sketch.wide.set(wide.clone());
            }
        }
        Some(wide)
    }

    /// What a `project` onto `columns` gives over the join's rows.
    fn project(&self, columns: &Columns) -> Val {
        if columns.is_empty() {
            return match self.rows_at(columns) {
                Some(table) => project(&Val::of_table(table), columns),
                None => Val::None,
            };
        }
        let key = Joined::key_of(columns);
        match &self.sketch(&key).tuples {
            Some(tuples) => project_tuples(tuples, &key, columns, self.width()),
            None => Val::None,
        }
    }

    /// The distinct tuples of the rows of the join at the columns `key`, which stand in order, as a table of those columns in order.
    fn build_tuples(&self, key: &[u16]) -> Option<Arc<Table>> {
        self.at(key)?;
        if key.is_empty() {
            return Some(Table::unit(true));
        }
        // A count of the tuples that an earlier read kept holds them.
        if let Some(found) = SHARED.with(|shared| shared.borrow().counted.get(&self.shared_key(key)).cloned()) {
            return Some(Table::new(key.len(), found.tuples.clone()));
        }
        let (tuples, _) = self.grouped(key, false)?;
        // The tuples stand in order, each once.
        Some(Table::new(key.len(), tuples))
    }

    /// The count of distinct tuples of the rows of the join at `columns`: no value where a column is not one of the join.
    pub fn distinct_count(&self, columns: &[u16]) -> Option<u64> {
        let mut key: Vec<u16> = columns.to_vec();
        key.sort_unstable();
        key.dedup();
        self.at(&key)?;
        if key.is_empty() {
            return Some(1);
        }
        if self.nodes.len() == 2 {
            return self.pair_count(&key);
        }
        if let Some(count) = self.tree_count(&key) {
            return Some(count);
        }
        self.grouped(&key, false).map(|(tuples, _)| (tuples.len() / key.len()) as u64)
    }

    /// The count of distinct tuples at `key` where the key of each node's link is told by the columns of `key`, so that rows at two keys never give one tuple: each node counts the distinct tuples below it at each of its parent's keys. No value where some link below a column of `key` is not told.
    fn tree_count(&self, key: &[u16]) -> Option<u64> {
        let count = self.nodes.len();
        let at = self.at(key)?;
        let children = self.children();
        let mut has = vec![false; count];
        for place in &at {
            has[place.node] = true;
        }
        for node in (1..count).rev() {
            if has[node] {
                has[self.links[node - 1].parent] = true;
            }
        }
        for node in 1..count {
            let link = &self.links[node - 1];
            let told = link.parent_places.iter().zip(&link.own).all(|(parent_place, own)| at.contains(&Place { node: link.parent, at: *parent_place }) || at.contains(&Place { node, at: *own }));
            if has[node] && !told {
                return None;
            }
        }
        let live = self.live();
        let mut below: Vec<Vec<u64>> = vec![Vec::new(); count];
        let mut total = 0u64;
        for node in (0..count).rev() {
            if !has[node] {
                continue;
            }
            let wanted: Vec<usize> = children[node].iter().copied().filter(|child| has[*child]).collect();
            let own: Vec<usize> = at.iter().filter(|place| place.node == node).map(|place| place.at).collect();
            let up = usize::from(node > 0);
            let width = up + own.len() + wanted.len();
            let mut flat: Vec<Cell> = Vec::new();
            for (row, cells) in self.nodes[node].rows().enumerate() {
                if live[node][row] {
                    if node > 0 {
                        flat.push(self.links[node - 1].ids[row]);
                    }
                    flat.extend(own.iter().map(|place| cells[*place]));
                    flat.extend(wanted.iter().map(|child| self.links[*child - 1].parent_ids[row]));
                }
            }
            if node > 0 {
                below[node] = vec![0; self.links[node - 1].weights.len()];
            }
            let groups = Table::distinct(width, flat);
            for group in groups.rows() {
                let product = wanted.iter().enumerate().fold(1u64, |product, (slot, child)| product.saturating_mul(below[*child][group[up + own.len() + slot] as usize]));
                if node == 0 {
                    total = total.saturating_add(product);
                } else {
                    let slot = &mut below[node][group[0] as usize];
                    *slot = slot.saturating_add(product);
                }
            }
        }
        Some(total)
    }

    /// The rows of a node of a join of two, which have a partner, as the id and the cells at `picks`, each once, in order.
    fn side_tuples(&self, node: usize, picks: &[usize]) -> Arc<Table> {
        let live = &self.live()[node];
        let ids = if node == 0 { &self.links[0].parent_ids } else { &self.links[0].ids };
        let mut flat: Vec<Cell> = Vec::new();
        for ((row, id), held) in self.nodes[node].rows().zip(ids).zip(live) {
            if *held {
                flat.push(*id);
                flat.extend(picks.iter().map(|place| row[*place]));
            }
        }
        Table::distinct(1 + picks.len(), flat)
    }

    /// The count of distinct tuples at `picks` of the rows of one node of a join of two that have a partner.
    fn one_side_count(&self, node: usize, picks: &[usize]) -> u64 {
        let mut flat: Vec<Cell> = Vec::new();
        for (row, held) in self.nodes[node].rows().zip(&self.live()[node]) {
            if *held {
                flat.extend(picks.iter().map(|place| row[*place]));
            }
        }
        Table::distinct(picks.len(), flat).len as u64
    }

    /// The count of distinct tuples at `key` of the rows of a join of two tables.
    fn pair_count(&self, key: &[u16]) -> Option<u64> {
        let (lefts, rights) = (self.places_in(key, 0), self.places_in(key, 1));
        if rights.is_empty() {
            return Some(self.one_side_count(0, &lefts));
        }
        if lefts.is_empty() {
            return Some(self.one_side_count(1, &rights));
        }
        let (a, b) = (self.side_tuples(0, &lefts), self.side_tuples(1, &rights));
        let (a_runs, b_runs) = (runs(a.cells(), a.arity), runs(b.cells(), b.arity));
        let pairs = common(&a_runs, &b_runs);
        // Two values of the paired columns that the tuples do not tell apart can give a tuple twice; where the tuples hold each paired column, they cannot.
        let link = &self.links[0];
        if link.parent_places.iter().zip(&link.own).all(|(parent_place, own)| lefts.contains(parent_place) || rights.contains(own)) {
            return Some(pairs.iter().map(|((a0, a1), (b0, b1))| ((a1 - a0) as u64).saturating_mul((b1 - b0) as u64)).fold(0u64, u64::saturating_add));
        }
        // A left tuple pairs with the right tuples of each id that it has. Left tuples with the same ids pair with the same right tuples, so each set of ids is counted once.
        let width = a.arity - 1;
        let mut by_tuple: Vec<Cell> = Vec::with_capacity(a.len * a.arity);
        for row in a.rows() {
            by_tuple.extend_from_slice(&row[1..]);
            by_tuple.push(row[0]);
        }
        let by_tuple = Table::distinct(a.arity, by_tuple);
        let mut sets: FastMap<Vec<u32>, u64> = FastMap::default();
        let mut start = 0;
        while start < by_tuple.len {
            let tuple = &by_tuple.cells()[start * a.arity..start * a.arity + width];
            let mut end = start;
            let mut ids: Vec<u32> = Vec::new();
            while end < by_tuple.len && by_tuple.cells()[end * a.arity..end * a.arity + width] == *tuple {
                ids.push(by_tuple.cells()[end * a.arity + width]);
                end += 1;
            }
            *sets.entry(ids).or_default() += 1;
            start = end;
        }
        let range_of = |id: u32| b_runs.binary_search_by(|run| run.0.cmp(&id)).ok().map(|at| (b_runs[at].1, b_runs[at].2));
        Some(sets.saturating_sum_of(|ids, tuples| {
            let mut flat: Vec<Cell> = Vec::new();
            for (from, to) in ids.iter().filter_map(|id| range_of(*id)) {
                for row in b.cells()[from * b.arity..to * b.arity].chunks_exact(b.arity) {
                    flat.extend_from_slice(&row[1..]);
                }
            }
            tuples.saturating_mul(Table::distinct(b.arity - 1, flat).len as u64)
        }))
    }

    /// The rows of `Count` over `keys`: each tuple of the keys' columns, with the count of the join's rows that hold it.
    pub fn counts(&self, keys: &[u16]) -> Val {
        if keys.is_empty() {
            return Val::of_table(Table::new(1, vec![number_bits(i64::try_from(self.rows).unwrap_or(i64::MAX))]));
        }
        let mut unique: Vec<u16> = keys.to_vec();
        unique.sort_unstable();
        unique.dedup();
        if self.at(&unique).is_none() {
            return Val::None;
        }
        let Some(counted) = self.counted(&unique) else { return Val::None };
        // Keys that are the distinct keys already give each tuple once.
        let regrouped;
        let (tuples, counts): (&[Cell], &[u64]) = if keys == unique.as_slice() {
            (counted.tuples.as_slice(), counted.weights.as_slice())
        } else {
            let picks: Vec<usize> = keys.iter().map(|key| unique.binary_search(key).expect("a key is one of the distinct keys")).collect();
            let mut ordered: Vec<Cell> = Vec::with_capacity(counted.weights.len() * keys.len());
            for tuple in counted.tuples.chunks_exact(unique.len()) {
                ordered.extend(picks.iter().map(|place| tuple[*place]));
            }
            regrouped = sum_runs(&ordered, keys.len(), &counted.weights);
            (regrouped.0.as_slice(), regrouped.1.as_slice())
        };
        let mut out: Vec<Cell> = Vec::with_capacity(counts.len() * (keys.len() + 1));
        for (tuple, count) in tuples.chunks_exact(keys.len()).zip(counts) {
            // A count past a number's range has no value.
            let Ok(count) = i32::try_from(*count) else { return Val::None };
            out.extend_from_slice(tuple);
            out.push(number_bits(i64::from(count)));
        }
        Val::of_table(Table::new(keys.len() + 1, out))
    }

    /// Whether `step` takes what it needs from the join's nodes as its first relation, without writing the rows.
    pub fn reads(&self, step: &Step) -> bool {
        match step {
            Step::Project { .. } | Step::All { .. } => true,
            Step::Part(part) => matches!(part.step(), PartStep::Count { .. }) || part.set_columns().is_some(),
            _ => false,
        }
    }

    /// Whether `step` takes what it needs from the join's nodes as its second relation, without writing the rows.
    pub fn reads_second(&self, step: &Step) -> bool {
        second_columns(step).is_some()
    }

    /// Whether `step` is a `join` or a `select`, which [`extend`] gives as more nodes, equalities or a filter where the form allows it, and which otherwise reads the rows written out.
    pub fn extends(step: &Step) -> bool {
        matches!(step, Step::Join { .. } | Step::Select { .. })
    }

    /// The relation that `step` reads in place of the join as its second relation, where `reads_second` holds of it.
    pub fn read_second(&self, step: &Step) -> Option<Val> {
        let columns = second_columns(step)?;
        Some(self.rows_at(columns).map_or(Val::None, Val::of_table))
    }

    /// What `step` gives over the join's rows, where `reads` holds of it.
    pub fn read(&self, step: &Step, children: &[&Val]) -> Option<Val> {
        match step {
            Step::Project { columns } => Some(self.project(columns)),
            Step::All { reads, left_len, right } => {
                let (left, outer) = reads.split(*left_len);
                Some(match self.rows_at(reads) {
                    Some(table) => all(&Val::of_table(table), children[1], left, right, outer).unwrap_or(Val::None),
                    None => Val::None,
                })
            }
            Step::Part(part) => match part.step() {
                PartStep::Count { keys } => Some(self.counts(keys)),
                other => {
                    let columns = part.set_columns()?;
                    Some(match self.rows_at(columns) {
                        Some(table) => other.run(&table, children).unwrap_or(Val::None),
                        None => Val::None,
                    })
                }
            },
            _ => None,
        }
    }

    /// The count of rows that `step` gives over the join's rows, where it is a count of distinct tuples of its columns, or a `select` that compares two columns of two nodes for inequality, and needs no rows written. `None` where `step` is not of that form.
    pub fn count_of(&self, step: &Step) -> Option<Option<u64>> {
        match step {
            Step::Select { at, op: Op::Ne, other: Some(other), drop: None } => self.unequal_count(*at, *other),
            Step::Project { columns } => Some(self.distinct_count(columns)),
            // A count past a number's range has no value, which only a join of more rows than a number holds can reach.
            Step::Part(part) => match part.step() {
                PartStep::Count { keys } if !keys.is_empty() && self.rows <= i32::MAX as u64 => Some(self.distinct_count(keys)),
                // A class of each key's rows is one row at the key.
                PartStep::ClassOf { keys } if !keys.is_empty() => Some(self.distinct_count(keys)),
                _ => None,
            },
            _ => None,
        }
    }

    /// The count of rows of the join whose columns `at` and `other` differ, where the two stand in two nodes: the rows of the join, less those where they are equal, which are the rows of the join with that pair added to the key between the nodes. `None` where that join is not a value.
    fn unequal_count(&self, at: u16, other: u16) -> Option<Option<u64>> {
        let first = self.places.get(usize::from(at))?;
        let second = self.places.get(usize::from(other))?;
        if first.node == second.node {
            return None;
        }
        let equal = match self.select(at, Op::Eq, Some(other), None)? {
            Val::Joined(joined) => joined.rows(),
            Val::Empty => 0,
            _ => return None,
        };
        Some(Some(self.rows.saturating_sub(equal)))
    }

    /// The count of rows that `step` gives over the join's rows, where every row it gives holds a row of the join in the cells it reads, or it keeps whole rows of the join: a part that gives each row it takes followed by cells that the cells at some of its columns fix, a `semijoin` or an `antijoin` or a part that keeps the rows that agree with a test on some of its columns, and a part that keeps the rows whose value is the most frequent of their key. No rows of the join are written: the step runs over the distinct tuples at the columns it reads, written as rows of the join's width with 0 at each other column, and each row it gives counts as many times as the join holds its tuple. `second` is the step's second relation, where it has one. `None` where `step` is not of that form.
    pub fn count_over(&self, step: &Step, second: Option<&Val>) -> Option<Option<u64>> {
        let mut key = match step {
            Step::Part(part) => part.row_columns().or_else(|| part.weighted_columns())?,
            Step::Semijoin { left, .. } | Step::Antijoin { left, .. } => left.to_vec(),
            _ => return None,
        };
        key.sort_unstable();
        key.dedup();
        if key.is_empty() {
            return None;
        }
        // A second relation that stands as the relations it comes from is read at the columns the step reads of it.
        let replaced;
        let second = match second {
            Some(Val::None) => return Some(None),
            Some(Val::Joined(joined)) => {
                replaced = joined.read_second(step)?;
                Some(&replaced)
            }
            Some(Val::Boxes(boxes)) => {
                replaced = boxes.read_second(step)?;
                Some(&replaced)
            }
            other => other,
        };
        if matches!(second, Some(Val::None)) {
            return Some(None);
        }
        let counted = self.counted(&key)?;
        let weights = &counted.weights;
        let width = self.width();
        let wide = counted.wide(&key, width);
        // The count of the rows of the join that hold the tuple of a row of the wide table, found among the sorted tuples from the place of the last row's tuple on.
        let near = std::cell::Cell::new(0usize);
        let weight_of = |row: &[Cell]| -> Option<u64> {
            let at = tuple_place(&counted.tuples, &key, row, near.get())?;
            near.set(at);
            Some(weights[at])
        };
        let mut total = 0u64;
        if let Step::Part(part) = step {
            if part.row_columns().is_none() {
                // The rows of the wide table ascend, as the tuples do, so row number `at` stands for `weights[at]` rows.
                let kept = part.step().kept_rows(&wide, weights)?;
                for row in kept.chunks_exact(width) {
                    total = total.saturating_add(weight_of(row)?);
                }
                return Some(Some(total));
            }
        }
        let first = Val::of_table(wide.clone());
        let given = match step {
            Step::Part(part) => {
                let children: Vec<&Val> = std::iter::once(&first).chain(second).collect();
                part.step().run(&wide, &children)
            }
            Step::Semijoin { left, right } => crate::native::semijoin(&first, second?, left, right),
            Step::Antijoin { left, right } => crate::native::antijoin(&first, second?, left, right),
            _ => return None,
        };
        let given = match given {
            None | Some(Val::None) => return Some(None),
            Some(Val::Empty) => return Some(Some(0)),
            Some(given) => crate::gen_parts::flat(&given)?,
        };
        for row in given.rows() {
            total = total.saturating_add(weight_of(row)?);
        }
        Some(Some(total))
    }

    /// A `select` over the rows of the join, as a join of the same nodes with the comparison applied. A comparison with 0, or of two columns of one node, filters that node's rows. An equality between columns of two nodes is one more pair of the key between them. Any other comparison between two nodes that are a node and its parent gives one node of the pairs of their rows that pass, in place of the two. No value where the form does not allow it.
    fn select(&self, at: u16, op: Op, other: Option<u16>, drop: Option<u16>) -> Option<Val> {
        let width = self.places.len();
        let inside = |column: u16| usize::from(column) < width;
        if !inside(at) || !other.is_none_or(inside) || !drop.is_none_or(inside) {
            return None;
        }
        // A column that is dropped equals another or a constant, so that no row of a node is lost.
        if let Some(dropped) = drop {
            if op != Op::Eq || (dropped != at && Some(dropped) != other) {
                return None;
            }
        }
        let first = self.places[usize::from(at)];
        let second = other.map(|other| self.places[usize::from(other)]);
        let places: Vec<Place> = self.places.iter().enumerate().filter(|(position, _)| Some(*position as u16) != drop).map(|(_, place)| *place).collect();
        // A relation of no columns is not rows of a join.
        if places.is_empty() {
            return None;
        }
        let mut nodes = self.nodes.clone();
        let mut equalities = self.equalities();
        match second {
            None => nodes[first.node] = filtered(&nodes[first.node], |row| holds(op, row[first.at], 0)),
            Some(second) if second.node == first.node => nodes[first.node] = filtered(&nodes[first.node], |row| holds(op, row[first.at], row[second.at])),
            Some(second) if op == Op::Eq => equalities.push((first, second)),
            Some(second) => return self.merged(op, first, second, drop),
        }
        build(nodes, equalities, places)
    }

    /// A `select` that compares the column at `first` with the column at `second` of the node's parent or child, as one node of the pairs of rows that stand in a row of the join and pass, in place of the two. No value where that is not so, or more than `PAIR_WORK` pairs are tested, or the pairs pass `CELL_CAP` cells.
    fn merged(&self, op: Op, first: Place, second: Place, drop: Option<u16>) -> Option<Val> {
        if drop.is_some() {
            return None;
        }
        let child = (1..self.nodes.len()).find(|at| {
            let parent = self.links[*at - 1].parent;
            (parent == first.node && *at == second.node) || (parent == second.node && *at == first.node)
        })?;
        let link = &self.links[child - 1];
        let parent = link.parent;
        let live = self.live();
        let mut starts: Vec<usize> = vec![0; link.weights.len() + 1];
        for (row, id) in link.ids.iter().enumerate() {
            if live[child][row] {
                starts[*id as usize + 1] += 1;
            }
        }
        for id in 1..starts.len() {
            starts[id] += starts[id - 1];
        }
        let mut next = starts.clone();
        let mut by_id: Vec<u32> = vec![0; starts[starts.len() - 1]];
        for (row, id) in link.ids.iter().enumerate() {
            if live[child][row] {
                by_id[next[*id as usize]] = row as u32;
                next[*id as usize] += 1;
            }
        }
        let (parent_table, child_table) = (&self.nodes[parent], &self.nodes[child]);
        let (parent_arity, child_arity) = (parent_table.arity, child_table.arity);
        // The comparison's two operands, as read from a parent row and a child row.
        let value = |place: Place, parent_row: &[Cell], child_row: &[Cell]| if place.node == parent { parent_row[place.at] } else { child_row[place.at] };
        let mut cells: Vec<Cell> = Vec::new();
        let mut work = 0usize;
        for (row, (parent_row, id)) in parent_table.rows().zip(&link.parent_ids).enumerate() {
            if !live[parent][row] || *id == NO_PARTNER {
                continue;
            }
            let run = &by_id[starts[*id as usize]..starts[*id as usize + 1]];
            work += run.len();
            if work > PAIR_WORK {
                return None;
            }
            for at in run {
                let child_row = &child_table.cells()[*at as usize * child_arity..(*at as usize + 1) * child_arity];
                if holds(op, value(first, parent_row, child_row), value(second, parent_row, child_row)) {
                    cells.extend_from_slice(parent_row);
                    cells.extend_from_slice(child_row);
                }
            }
            if cells.len() > CELL_CAP {
                return None;
            }
        }
        if cells.is_empty() {
            return Some(Val::Empty);
        }
        let merged = Table::new(parent_arity + child_arity, cells);
        // The pair stands where the parent stood, and the child's columns follow the parent's.
        let moved = |place: Place| {
            let node = if place.node == child { parent } else { place.node };
            let at = if place.node == child { place.at + parent_arity } else { place.at };
            Place { node: node - usize::from(node > child), at }
        };
        let mut nodes: Vec<Arc<Table>> = Vec::with_capacity(self.nodes.len() - 1);
        for (at, table) in self.nodes.iter().enumerate() {
            if at == parent {
                nodes.push(merged.clone());
            } else if at != child {
                nodes.push(table.clone());
            }
        }
        let equalities: Vec<Equality> = self.equalities().into_iter().filter(|(_, own)| own.node != child).map(|(a, b)| (moved(a), moved(b))).collect();
        let places: Vec<Place> = self.places.iter().map(|place| moved(*place)).collect();
        build(nodes, equalities, places)
    }
}
