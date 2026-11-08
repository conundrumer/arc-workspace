//! The value hash of each column of a table at one assignment, for a reader
//! that orders a table's columns by content ([`column_keys`]).
//!
//! A column's key is its type name and its value hash. The type name is the
//! one that the TableHash writes ([`super::hashed_names`]), so a Pose type
//! names its assembly by the QueryHash of its `RIGID_DET` and holds no slot.
//! The value hash is defined from the table's cells alone:
//!
//! 1. The base hash of a column is the hash of its type name and, for each
//!    example in the order that the table holds them, the example's kind and
//!    index and the Set of the example's Sets of TableRows, each reduced to
//!    the Set of the column's runs of cells. A Set is sorted and has no
//!    repeat. So the base hash holds no row order, no row count of a repeated
//!    run, no name of a label or of the author, and no order of a map or a
//!    set. It is the same for every `ARCLOG_MAP_SEED`, as the cells are the
//!    export cells: an Ident is the first 32 bits of its member digest.
//! 2. Two columns tie where their type names and base hashes are equal.
//!    Two tied columns can still differ in how they relate to the other
//!    columns, so each tied column's hash is refined: it becomes the hash of
//!    its previous hash and the sorted list, over each other column, of that
//!    column's previous hash and the pair hash. The pair hash of the ordered
//!    pair `(a, b)` is the base hash of the two columns `a` and `b` read as
//!    one run. The refinement repeats while it splits a class of tied
//!    columns, at most once for each column. A column that no other column
//!    ties with keeps its hash. The refinement is skipped, and every tie then
//!    stays, where the pair hashes would read more than [`PAIR_ROWS`] table
//!    rows.
//! 3. The columns that still tie form a class. A class is checked for
//!    exchange: for each other column `c` of the class, whether the table
//!    with the first column of the class and `c` swapped has the Set of
//!    TableRows that the table has, in every example. The swaps of the first
//!    column with each other generate every permutation of the class, so
//!    where all of them leave the table as it is, any order of the class
//!    gives the same table. The check is skipped where it would read more
//!    than [`PAIR_ROWS`] table rows.
//!
//! The tie of a column ([`ColumnKey::tie`]) is [`TIE_NONE`] for a column
//! whose type name and hash no other column has, [`TIE_EXCHANGEABLE`] for a
//! column of a class that passed the check, and [`TIE_OPEN`] for a column of a
//! class that failed or skipped it.
//!
//! One order for equal contents. Let a table `T'` hold the content of a table
//! `T` with its columns permuted by `p`, and the same examples. Each step
//! above reads the cells through sorted Sets, the type names, and
//! multisets over the other columns, so each column of `T'` has the key of
//! its column in `T`, the classes are those of `T` moved by `p`, and the
//! skips are decided by the counts of columns and table rows, which are
//! equal. Sorting the columns of each table by (type name, hash) therefore
//! gives the columns of one class at one range of places in both. A column
//! whose key is unique is at one place in both, with equal content. Within a
//! class of [`TIE_EXCHANGEABLE`] columns, the permutations of the class are
//! automorphisms of the table, so any assignment of the class's columns to
//! its places gives one table. So the two sorted tables are equal. A class of
//! [`TIE_OPEN`] columns has no such guarantee, and a reader treats the order
//! within it as open.

use std::hash::Hasher;

use arclog::hash::{StableHash, StableHashMap, StableHasher};
use arclog::types::ValueType;

use super::{digest, hashed_names, run_of, Assemblies, Encoded};

/// The most table rows that the pair hashes of the refinement, and the swaps
/// of the exchange check, read in all at one assignment.
const PAIR_ROWS: usize = 4_000_000;

/// No other column has the column's type name and hash.
pub const TIE_NONE: u32 = 0;
/// Another column has them, and every swap in the class leaves the table as it is.
pub const TIE_EXCHANGEABLE: u32 = 1;
/// Another column has them, and the class was not shown exchangeable.
pub const TIE_OPEN: u32 = 2;

/// A column's key at one assignment.
#[derive(Clone, Debug)]
pub struct ColumnKey {
    /// The type name that the TableHash writes for the column.
    pub ty: String,
    /// The value hash of the column.
    pub hash: StableHash,
    /// [`TIE_NONE`], [`TIE_EXCHANGEABLE`] or [`TIE_OPEN`].
    pub tie: u32,
}

/// The cells of a table at one assignment, by example.
struct Cells<'a> {
    examples: &'a [(u8, u32, &'a [Encoded])],
    widths: Vec<usize>,
    starts: Vec<usize>,
    width: usize,
}

impl Cells<'_> {
    /// The hash of the Set, over the examples, of the Sets of TableRows, each
    /// reduced to the Set of its runs of the cells of `columns` in that order.
    fn runs(&self, columns: &[usize]) -> u128 {
        let mut hasher = StableHasher::new();
        for (kind, index, distinct) in self.examples {
            let mut sets: Vec<u128> = distinct
                .iter()
                .map(|rows| {
                    let mut runs: Vec<u128> = (0..rows.count as usize)
                        .map(|row| {
                            let mut run = StableHasher::new();
                            for &column in columns {
                                run.write_i32s(run_of(rows, self.width, self.starts[column], self.widths[column], row));
                            }
                            run.finish128().0
                        })
                        .collect();
                    runs.sort_unstable();
                    runs.dedup();
                    digest(&runs)
                })
                .collect();
            sets.sort_unstable();
            sets.dedup();
            hasher.write_u8(*kind);
            hasher.write_u32(*index);
            hasher.write_u128(digest(&sets));
        }
        hasher.finish128().0
    }

    /// The hash of the Set, over the examples, of the Sets of rows with the
    /// columns in `order`.
    fn body(&self, order: &[usize]) -> u128 {
        let mut hasher = StableHasher::new();
        for (kind, index, distinct) in self.examples {
            let mut sets: Vec<u128> = distinct
                .iter()
                .map(|rows| {
                    let mut hashes: Vec<u128> = (0..rows.count as usize)
                        .map(|row| {
                            let mut hasher = StableHasher::new();
                            for &column in order {
                                hasher.write_i32s(run_of(rows, self.width, self.starts[column], self.widths[column], row));
                            }
                            hasher.finish128().0
                        })
                        .collect();
                    hashes.sort_unstable();
                    digest(&hashes)
                })
                .collect();
            sets.sort_unstable();
            sets.dedup();
            hasher.write_u8(*kind);
            hasher.write_u32(*index);
            hasher.write_u128(digest(&sets));
        }
        hasher.finish128().0
    }
}

/// The count of distinct (type name, hash) among the columns `of`.
fn classes(names: &[String], hashes: &[u128], of: &[usize]) -> usize {
    let mut keys: Vec<(&str, u128)> = of.iter().map(|&column| (names[column].as_str(), hashes[column])).collect();
    keys.sort_unstable();
    keys.dedup();
    keys.len()
}

/// The columns whose type name and hash another column has.
fn tied(names: &[String], hashes: &[u128]) -> Vec<usize> {
    (0..names.len()).filter(|&column| (0..names.len()).any(|other| other != column && names[other] == names[column] && hashes[other] == hashes[column])).collect()
}

/// The key of each column of `types` at one assignment, where `examples` give
/// each example's kind, index and distinct TableRows as cells, and `failed`
/// the failed examples (kind, index, bound name) that the TableHash also
/// hashes.
pub(super) fn column_keys(types: &[ValueType], examples: &[(u8, u32, &[Encoded])], failed: &[(u8, u32, &'static str)], assemblies: &Assemblies) -> Vec<ColumnKey> {
    let names = hashed_names(types, assemblies);
    let widths: Vec<usize> = types.iter().map(|ty| if ty.is_box() { 4 } else { 1 }).collect();
    let starts: Vec<usize> = widths.iter().scan(0, |at, width| { let start = *at; *at += width; Some(start) }).collect();
    let width: usize = widths.iter().sum();
    let cells = Cells { examples, widths, starts, width };
    let count = types.len();
    let mut hashes: Vec<u128> = (0..count)
        .map(|column| {
            let mut hasher = StableHasher::new();
            hasher.write(b"arclog.column_value");
            hasher.write(names[column].as_bytes());
            hasher.write_u8(0);
            hasher.write_u128(cells.runs(&[column]));
            for (kind, index, bound) in failed {
                hasher.write_u8(*kind);
                hasher.write_u32(*index);
                hasher.write(bound.as_bytes());
                hasher.write_u8(0);
            }
            hasher.finish128().0
        })
        .collect();
    let rows: usize = examples.iter().flat_map(|(_, _, distinct)| distinct.iter()).map(|rows| rows.count as usize).sum::<usize>().max(1);
    let mut open = tied(&names, &hashes);
    if !open.is_empty() && open.len().saturating_mul(count).saturating_mul(rows) <= PAIR_ROWS {
        let mut pairs: StableHashMap<(usize, usize), u128> = StableHashMap::default();
        for _ in 0..count {
            let mut next = hashes.clone();
            for &column in &open {
                let mut around: Vec<(u128, u128)> = (0..count)
                    .filter(|&other| other != column)
                    .map(|other| (hashes[other], *pairs.entry((column, other)).or_insert_with(|| cells.runs(&[column, other]))))
                    .collect();
                around.sort_unstable();
                let mut hasher = StableHasher::new();
                hasher.write(b"arclog.column_value.refined");
                hasher.write_u128(hashes[column]);
                for (class, pair) in around {
                    hasher.write_u128(class);
                    hasher.write_u128(pair);
                }
                next[column] = hasher.finish128().0;
            }
            if classes(&names, &next, &open) == classes(&names, &hashes, &open) {
                break;
            }
            hashes = next;
            open = tied(&names, &hashes);
            if open.is_empty() {
                break;
            }
        }
    }
    let mut ties = vec![TIE_NONE; count];
    let mut done: Vec<bool> = vec![false; count];
    let identity: Vec<usize> = (0..count).collect();
    let mut table: Option<u128> = None;
    for &column in &open {
        if std::mem::replace(&mut done[column], true) {
            continue;
        }
        let class: Vec<usize> = open.iter().copied().filter(|&other| names[other] == names[column] && hashes[other] == hashes[column]).collect();
        class.iter().for_each(|&member| done[member] = true);
        let exchangeable = class.len().saturating_mul(rows) <= PAIR_ROWS && {
            let whole = *table.get_or_insert_with(|| cells.body(&identity));
            class[1..].iter().all(|&member| {
                let mut order = identity.clone();
                order.swap(class[0], member);
                cells.body(&order) == whole
            })
        };
        let tie = if exchangeable { TIE_EXCHANGEABLE } else { TIE_OPEN };
        class.iter().for_each(|&member| ties[member] = tie);
    }
    (0..count).map(|column| ColumnKey { ty: names[column].clone(), hash: StableHash(hashes[column]), tie: ties[column] }).collect()
}
