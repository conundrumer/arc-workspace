//! The order of the columns that the TableHash is computed under
//! ([`AssignmentSummary::column_order`]): two tables of equal TableHash have,
//! under the map that it gives, columns of equal key and equal Sets of rows,
//! where the columns tie with a tie of 2 that the search ordered, and with a
//! tie of 1.

use std::collections::BTreeSet;

use super::*;

/// The search cap of the default settings.
const SEARCH_CAP: u64 = 1 << 28;

/// Each order of three columns.
const ORDERS: [[usize; 3]; 6] = [[0, 1, 2], [0, 2, 1], [1, 0, 2], [1, 2, 0], [2, 0, 1], [2, 1, 0]];

/// A table of one example of one TableRows, as its summary gives it.
struct Observed {
    hash: StableHash,
    order: Vec<usize>,
    keys: Vec<ColumnKey>,
    rows: Vec<Vec<i32>>,
}

impl Observed {
    /// The Set of rows with the columns in the table's canonical order.
    fn placed(&self) -> BTreeSet<Vec<i32>> {
        self.rows.iter().map(|row| self.order.iter().map(|&column| row[column]).collect()).collect()
    }
}

/// The TableHash, the order of the columns and the key of each column of the table of `Color` columns that holds `rows`.
fn observe(rows: Vec<Vec<i32>>) -> Observed {
    let types = vec![ValueType::Color; rows[0].len()];
    let cells: Vec<i32> = rows.iter().flatten().copied().collect();
    let mut hasher = StableHasher::new();
    hasher.write_u64(rows.len() as u64);
    hasher.write_i32s(&cells);
    let encoded = Encoded { count: rows.len() as u64, cells, key: hasher.finish128() };
    let views: Vec<(u8, u32, &[Encoded])> = vec![(1, 0, std::slice::from_ref(&encoded))];
    let assemblies = Assemblies::default();
    let (found, _) = table_hash(&types, &views, &assemblies, SEARCH_CAP);
    let (hash, _, order) = found.expect("the search stays within its cap");
    let keys = column_hash::column_keys(&types, &views, &[], &assemblies);
    Observed { hash, order, keys, rows }
}

/// The rows of `base` with column `c` of the result the column `order[c]` of `base`.
fn permuted(base: &[[i32; 3]], order: &[usize; 3]) -> Vec<Vec<i32>> {
    base.iter().map(|row| order.iter().map(|&column| row[column]).collect()).collect()
}

/// Checks that `a` and `b` have equal TableHashes, and, under the map from the column at each place of the order of `a` to the column at that place of
/// the order of `b`, columns of equal type key and value hash and equal Sets of rows.
fn assert_one_table(a: &Observed, b: &Observed) {
    assert_eq!(a.hash, b.hash, "the TableHashes");
    for observed in [a, b] {
        let mut sorted = observed.order.clone();
        sorted.sort_unstable();
        assert_eq!(sorted, (0..observed.rows[0].len()).collect::<Vec<_>>(), "the order holds each column once");
    }
    for place in 0..a.order.len() {
        let (x, y) = (&a.keys[a.order[place]], &b.keys[b.order[place]]);
        assert_eq!(x.ty, y.ty, "the type key at place {place}");
        assert_eq!(x.hash, y.hash, "the value hash at place {place}");
    }
    assert_eq!(a.placed(), b.placed(), "the Set of rows under the map");
}

#[test]
fn columns_of_a_tie_of_two_that_the_search_ordered_map_to_equal_columns() {
    // Each column holds 0, 1 and 2, and each two columns hold every pair of values: the refinement splits none. The columns `(i, j, i + j)` are
    // not exchangeable, as swapping the first and the third gives rows `(i + j, j, i)`, which the table lacks.
    let base: Vec<[i32; 3]> = (0..3).flat_map(|i| (0..3).map(move |j| [i, j, (i + j) % 3])).collect();
    let observed: Vec<Observed> = ORDERS.iter().map(|order| observe(permuted(&base, order))).collect();
    for each in &observed {
        assert!(each.keys.iter().all(|key| key.tie == TIE_OPEN), "every column has a tie of 2");
    }
    for each in &observed[1..] {
        assert_one_table(&observed[0], each);
    }
}

#[test]
fn columns_of_a_tie_of_one_map_to_equal_columns() {
    // The first two columns are equal, so exchangeable; the third holds other values.
    let base: Vec<[i32; 3]> = (0..3).flat_map(|i| (0..2).map(move |k| [i, i, k])).collect();
    let observed: Vec<Observed> = ORDERS.iter().map(|order| observe(permuted(&base, order))).collect();
    for (each, order) in observed.iter().zip(&ORDERS) {
        let expected: Vec<u32> = order.iter().map(|&column| if column < 2 { TIE_EXCHANGEABLE } else { TIE_NONE }).collect();
        assert_eq!(each.keys.iter().map(|key| key.tie).collect::<Vec<_>>(), expected, "the ties in the order {order:?}");
    }
    for each in &observed[1..] {
        assert_one_table(&observed[0], each);
    }
}
