//! The `tile_size` relation evaluates at the mode of Ext, N and G, which
//! gives K, and at the mode of K, N and G, which gives Ext.

use arclog::algebra::{algebra, satisfied_mode};
use arclog::registry::{LibName, Registry};
use arclog::terms::Term;

/// The rows of `tile_size` at the bound columns `ext`, `n`, `g`, `k`, as numbers.
fn rows(ext: Option<i32>, n: i32, g: i32, k: Option<i32>) -> Vec<[i32; 4]> {
    let bound = [ext.map(Term::encode_number), Some(Term::encode_number(n)), Some(Term::encode_number(g)), k.map(Term::encode_number)];
    let relation = algebra(&LibName("tile_size".into())).expect("tile_size is a native algebra relation");
    let mut found = Vec::new();
    relation
        .evaluate(&bound, Registry::get(), &mut |row| found.push([0, 1, 2, 3].map(|i| Term::decode_number(row[i]))))
        .expect("numbers reach no margin bound");
    found
}

#[test]
fn k_is_computed_from_ext_n_and_g() {
    assert_eq!(rows(Some(11), 3, 1, None), [[11, 3, 1, 3]]);
    assert_eq!(rows(Some(12), 4, 0, None), [[12, 4, 0, 3]]);
    assert_eq!(rows(Some(5), 1, 7, None), [[5, 1, 7, 5]]);
}

#[test]
fn no_row_where_n_does_not_divide_the_length_or_the_length_is_not_positive() {
    assert!(rows(Some(10), 3, 1, None).is_empty());
    assert!(rows(Some(4), 3, 2, None).is_empty());
    assert!(rows(Some(0), 3, 0, None).is_empty());
    assert!(rows(Some(6), 0, 1, None).is_empty());
}

#[test]
fn ext_is_computed_from_k_n_and_g() {
    assert_eq!(rows(None, 3, 1, Some(3)), [[11, 3, 1, 3]]);
    assert_eq!(rows(None, 4, 0, Some(3)), [[12, 4, 0, 3]]);
    assert_eq!(rows(None, 1, 7, Some(5)), [[5, 1, 7, 5]]);
}

#[test]
fn no_row_where_k_is_not_positive_or_n_is_zero() {
    assert!(rows(None, 3, 1, Some(0)).is_empty());
    assert!(rows(None, 3, 1, Some(-2)).is_empty());
    assert!(rows(None, 0, 1, Some(3)).is_empty());
}

#[test]
fn the_two_modes_agree() {
    for n in 1..6 {
        for g in 0..4 {
            for k in 1..6 {
                let [row] = rows(None, n, g, Some(k))[..] else { panic!("one extent") };
                assert_eq!(rows(Some(row[0]), n, g, None), [[row[0], n, g, k]]);
            }
        }
    }
}

#[test]
fn the_registry_declares_both_modes() {
    let relation = Registry::get().algebra_relation(&LibName("tile_size".into())).expect("the registry declares tile_size");
    let at = |bound: [bool; 4]| satisfied_mode(relation, &bound);
    assert!(at([true, true, true, false]).is_some());
    assert!(at([false, true, true, true]).is_some());
    assert_eq!(at([false, true, true, false]), None);
    assert_eq!(at([true, false, true, false]), None);
}
