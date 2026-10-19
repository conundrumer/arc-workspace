//! The orientation algebra's relations, each as its fact set: the tables of
//! [`super::tables`] and the relations computed from the D4 action of
//! [`super::geometry`]: the enumerations, `sym_member`, the group relations,
//! `pose_difference`, and the relation macros over orientation values alone.

use super::geometry::{D4Element, Edges, Geometry, Meaning};
use super::tables::OrientationTables;
use super::Algebra;
use crate::hash::StableHashMap;
use crate::registry::{LibName, Registry};
use crate::relations::RowSet;
use crate::terms::{ReachedMarginBound, TermId};
use crate::types::ValueType;

/// A relation of the orientation algebra: its fact set.
#[derive(Debug)]
pub struct OrientationRelation {
    name: &'static str,
    rows: RowSet,
}

impl OrientationRelation {
    /// Each relation of the orientation algebra, by its registry name: each
    /// table of [`OrientationTables::get`], and each relation this module
    /// computes.
    pub fn all() -> impl Iterator<Item = (&'static LibName, &'static OrientationRelation)> {
        static RELATIONS: std::sync::OnceLock<StableHashMap<LibName, OrientationRelation>> = std::sync::OnceLock::new();
        RELATIONS
            .get_or_init(|| {
                let tables = OrientationTables::get();
                let computed = computed_relations(Registry::get(), Geometry::get());
                let read = tables.names().map(|name| (name.clone(), tables.rows(name).expect("a table's rows").clone()));
                computed
                    .into_iter()
                    .chain(read)
                    .map(|(name, rows)| {
                        let leaked: &'static str = Box::leak(name.0.clone());
                        (name, OrientationRelation { name: leaked, rows })
                    })
                    .collect()
            })
            .iter()
    }
}

impl Algebra for OrientationRelation {
    fn name(&self) -> &'static str {
        self.name
    }

    /// Each row of the fact set that agrees with `bound`. A fact set holds no
    /// Box, so this never reaches the margin bound.
    fn evaluate(
        &self,
        bound: &[Option<TermId>],
        _registry: &Registry,
        emit: &mut dyn FnMut(&[TermId]),
    ) -> Result<(), ReachedMarginBound> {
        for row in self.rows.rows() {
            if bound.iter().zip(row).all(|(b, value)| b.is_none_or(|b| b == *value)) {
                emit(row);
            }
        }
        Ok(())
    }
}

/// The relations of the orientation algebra that the D4 action gives, each
/// as its fact set, by its registry name.
fn computed_relations(registry: &Registry, geometry: &Geometry) -> Vec<(LibName, RowSet)> {
    let column_type = |name: &str, column: usize| -> ValueType {
        let declared = super::declaration(registry, name);
        declared.columns[column].ty.fixed().cloned().expect("a column of a fixed type")
    };
    let rows = |arity: u16, rows: Vec<Vec<TermId>>| {
        let mut set = RowSet::empty(arity);
        for row in rows {
            set.insert(row.into());
        }
        set
    };
    let elements = || geometry.domain(&ValueType::D4).iter().map(|&t| (t, geometry.element(t)));
    let mut relations = Vec::new();
    let enumerations = [
        "dir_elem",
        "axis_elem",
        "diag_dir_elem",
        "diag_axis_elem",
        "d4_elem",
        "c4_elem",
        "sense_elem",
        "sym_elem",
        "dir8_elem",
        "axis4_elem",
    ];
    for name in enumerations {
        let domain = geometry.domain(&column_type(name, 0));
        relations.push((name, rows(1, domain.iter().map(|&value| vec![value]).collect())));
    }
    let mut sym_member = Vec::new();
    for &s in geometry.domain(&ValueType::Sym) {
        let Meaning::Subgroup(members) = geometry.meaning(s).1 else { unreachable!("a Sym constant") };
        sym_member.extend(elements().filter(|(_, x)| members & x.bit() != 0).map(|(t, _)| vec![s, t]));
    }
    relations.push(("sym_member", rows(2, sym_member)));
    let mut compose = Vec::new();
    for (a, x) in elements() {
        for (b, y) in elements() {
            compose.push(vec![a, b, geometry.element_constant(x.after(y))]);
        }
    }
    relations.push(("d4_compose", rows(3, compose)));
    // The element that takes the placement at pose a onto the placement at
    // pose b, `docs/arclog/rigid.md#the-pose`: b is it after a.
    let mut difference = Vec::new();
    for (a, x) in elements() {
        for (b, y) in elements() {
            difference.push(vec![a, b, geometry.element_constant(y.after(x.inverse()))]);
        }
    }
    relations.push(("pose_difference", rows(3, difference)));
    relations.push(("d4_inverse", rows(2, elements().map(|(t, x)| vec![t, geometry.element_constant(x.inverse())]).collect())));
    relations.push(("d4_identity", rows(1, vec![vec![geometry.element_constant(D4Element::IDENTITY)]])));
    let dirs = geometry.domain(&ValueType::Dir);
    let mut perp_dir = Vec::new();
    for &d in dirs {
        for &d2 in dirs {
            if geometry.edge(d2) != geometry.edge(d) && geometry.edge(d2) != geometry.edge(d).opposite() {
                perp_dir.push(vec![d, d2]);
            }
        }
    }
    relations.push(("perp_dir", rows(2, perp_dir)));
    let mut diag_dirs = Vec::new();
    for &diag in geometry.domain(&ValueType::DiagDir) {
        for &a in geometry.domain(&ValueType::Axis) {
            let on_axis = |on: bool| {
                geometry.direction(Edges::of(&[geometry.corner_edge(diag, a, on)])).expect("a Dir of each edge")
            };
            diag_dirs.push(vec![diag, a, on_axis(true), on_axis(false)]);
        }
    }
    relations.push(("diag_dirs", rows(4, diag_dirs)));
    for (name, ty) in [("apply_dir", ValueType::Dir), ("apply_diag_dir", ValueType::DiagDir), ("apply_dir8", ValueType::Dir8)] {
        let mut applied = Vec::new();
        for (t, x) in elements() {
            for &d in geometry.domain(&ty) {
                applied.push(vec![t, d, geometry.under(x, d)]);
            }
        }
        relations.push((name, rows(3, applied)));
    }
    relations.into_iter().map(|(name, rows)| (LibName(name.into()), rows)).collect()
}
