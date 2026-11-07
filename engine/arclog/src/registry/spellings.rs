//! The spellings of the registry file's forms, and the helpers that read
//! an s-expression of a form or give the place of a file's start.

use super::*;

// The words of the registry file's forms.
pub(super) const RELATION: &str = "relation";
pub(super) const COMPONENT: &str = "component";
pub(super) const PROPOSER: &str = "proposer";
pub(super) const CONSTANTS: &str = "constants";
pub(super) const TYPE: &str = "type";
pub(super) const FACT: &str = "fact";
pub(super) const REFINES: &str = "refines";
pub(super) const MACRO: &str = "macro";
pub(super) const COLUMNS: &str = "columns";
pub(super) const MODES: &str = "modes";
pub(super) const TYPE_PARAMETERS: &str = "type-parameters";
pub(super) const INPUTS: &str = "inputs";
pub(super) const OUTPUTS: &str = "outputs";
pub(super) const DEFAULT: &str = "default";
pub(super) const READS_OUTPUTS: &str = "reads-outputs";
pub(super) const FROM_KEY: &str = "from-key";
pub(super) const REQUIRED: &str = "required";
pub(super) const ONE_OF: &str = "one-of";
pub(super) const COPIES: &str = "copies";
pub(super) const FRAMES: &str = "frames";
pub(super) const TYPES: &str = "types";
pub(super) const WHEN: &str = "when";
pub(super) const SAME_FRAME: &str = "same-frame";
pub(super) const OF: &str = "of";
pub(super) const NEW: &str = "new";
pub(super) const SIZE: &str = "size";
pub(super) const BY: &str = "by";
pub(super) const EITHER: &str = "either";
pub(super) const NATIVE: &str = "native";
pub(super) const DOMAIN: &str = "domain";
pub(super) const ARCLOG: &str = "arclog";
pub(super) const POSE: &str = "Pose";
pub(super) const SHARED_POSE: &str = "shared-pose";
pub(super) const POSE_OR: &str = "pose-or";
pub(super) const C4: &str = "C4";

pub(super) const COMPONENT_KINDS: &[(ComponentKind, &str)] = &[
    (ComponentKind::Construction, "construction"),
    (ComponentKind::Detector, "detector"),
    (ComponentKind::TaskStructure, "task-structure"),
];

/// The orientation type whose constants a column of `name` holds, where
/// `name` is one: `C4` is a part of `D4`, and `Dir8` and `Axis4` are unions.
pub(super) fn orientation_type(name: TypeName) -> Option<OrientationType> {
    match name {
        TypeName::Dir => Some(OrientationType::Dir),
        TypeName::DiagDir => Some(OrientationType::DiagDir),
        TypeName::Axis => Some(OrientationType::Axis),
        TypeName::DiagAxis => Some(OrientationType::DiagAxis),
        TypeName::D4 => Some(OrientationType::D4),
        TypeName::Sym => Some(OrientationType::Sym),
        TypeName::Sense => Some(OrientationType::Sense),
        TypeName::Number
        | TypeName::Int
        | TypeName::Nat
        | TypeName::Color
        | TypeName::Example
        | TypeName::Unit
        | TypeName::Box
        | TypeName::Position
        | TypeName::Offset
        | TypeName::Ident
        | TypeName::C4
        | TypeName::Dir8
        | TypeName::Axis4 => None,
    }
}

/// The items of `expr` after its head, where it is a list headed by `head`.
pub(super) fn headed<'e>(expr: &'e SExpr, head: &str) -> Option<&'e [SExpr]> {
    match expr {
        SExpr::List { items, .. } => match items.split_first() {
            Some((SExpr::Symbol { text, .. }, rest)) if &**text == head => Some(rest),
            _ => None,
        },
        _ => None,
    }
}

/// The place of the start of `file`, where a fault of no one form stands.
pub(super) fn file_start(file: SourceFile) -> SourcePlace {
    SourcePlace { file, start: 0, end: 0, line: 1, column: 1 }
}
