//! The mapping of the key rows of Pose types, which the type check and the
//! inference share: the labels of a key row mapped to other labels, or its
//! key row replaced, in a type and in the fields of a record type.

use crate::program::LabelId;
use crate::types::{AssemblyId, KeyRow, ValueType};

/// `ty` with each label of a key row mapped by `map`.
pub(in crate::check) fn map_labels(ty: &ValueType, map: &dyn Fn(LabelId) -> LabelId) -> ValueType {
    try_map_labels(ty, &|label| Some(map(label))).expect("a map of every label maps each label of a type")
}

/// `ty` with each label of a key row mapped by `map`, or `None` where
/// `map` gives no label for one.
pub(in crate::check) fn try_map_labels(ty: &ValueType, map: &dyn Fn(LabelId) -> Option<LabelId>) -> Option<ValueType> {
    try_map_key_rows(ty, &|labels| Some(KeyRow::Labels(labels.iter().map(|label| map(*label)).collect::<Option<_>>()?)))
}

/// `ty` with each key row of labels replaced by the one `map` gives for
/// its labels, or `None` where `map` gives none.
pub(in crate::check) fn try_map_key_rows(ty: &ValueType, map: &dyn Fn(&[LabelId]) -> Option<KeyRow>) -> Option<ValueType> {
    Some(match ty {
        ValueType::Pose(AssemblyId { name, canonical_form, key: KeyRow::Labels(labels) }) => {
            ValueType::Pose(AssemblyId { name: name.clone(), canonical_form: canonical_form.clone(), key: map(labels)? })
        }
        ValueType::Record(fields) => {
            ValueType::Record(fields.iter().map(|(name, ty)| Some((name.clone(), try_map_key_rows(ty, map)?))).collect::<Option<_>>()?)
        }
        ty => ty.clone(),
    })
}
