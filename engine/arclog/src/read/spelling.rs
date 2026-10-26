//! The spellings of the closed vocabularies of an arclog file and of an
//! arcdata file, each in one table that the reader and the writer read in
//! the two directions.

use crate::program::{ClaimKind, ClauseKeyword, ConstraintOp, FactRelation, Plausibility, TypeName};

pub(crate) const CLAIM_KINDS: &[(ClaimKind, &str)] = &[(ClaimKind::Input, "INPUT"), (ClaimKind::Output, "OUTPUT")];

pub(crate) const CLAUSE_KEYWORDS: &[(ClauseKeyword, &str)] = &[
    (ClauseKeyword::Rule, "RULE"),
    (ClauseKeyword::Det, "DET"),
    (ClauseKeyword::DetOrRule, "DET_OR_RULE"),
    (ClauseKeyword::RuleOrDet, "RULE_OR_DET"),
];

pub(crate) const CONSTRAINT_OPS: &[(ConstraintOp, &str)] = &[
    (ConstraintOp::Eq, "="),
    (ConstraintOp::Ne, "!="),
    (ConstraintOp::Lt, "<"),
    (ConstraintOp::Le, "<="),
    (ConstraintOp::Gt, ">"),
    (ConstraintOp::Ge, ">="),
];

pub const FACT_RELATIONS: &[(FactRelation, &str)] = &[
    (FactRelation::Input, "input"),
    (FactRelation::ExInput, "ex_input"),
    (FactRelation::ExOutput, "ex_output"),
];

pub(crate) const INIT: &str = "INIT";
pub(crate) const CHOOSE: &str = "CHOOSE";
pub(crate) const RIGID_DET: &str = "RIGID_DET";
pub(crate) const DEMONSTRATED: &str = "DEMONSTRATED";
pub(crate) const DEMO_RULE: &str = "DEMO_RULE";
pub(crate) const ALTS: &str = "ALTS";
pub(crate) const ALT: &str = "ALT";
pub(crate) const APPROXIMATED: &str = "APPROXIMATED";
pub(crate) const NOT: &str = "NOT";
pub(crate) const OR: &str = "OR";
pub(crate) const IF: &str = "IF";
pub(crate) const ALL: &str = "ALL";
pub(crate) const ONE: &str = "ONE";
pub(crate) const SET: &str = "SET";
pub(crate) const KEY: &str = "key";
pub(crate) const FOR: &str = "for";
pub(crate) const FROM: &str = "from";
pub(crate) const NEVER: &str = "never";
pub(crate) const INSTANCE: &str = "instance";
/// The step of `&marker.pose`.
pub(crate) const POSE: &str = "pose";
/// The prefix of a read of a port of the component a registry definition
/// defines, `(self.<port> ...)`.
pub(crate) const SELF_PREFIX: &str = "self.";
/// The mark of a name the program declares.
pub(crate) const DECLARED_MARK: char = '&';
/// The mark of a site's head: `:C` of `(:C *V)`.
pub(crate) const COLUMN_MARK: char = ':';
pub(crate) const FRESH_MARK: char = '*';
pub(crate) const KEY_MARK: char = '^';
pub(crate) const ZERO: &str = "0";

/// The column types of an arcdata `param` form.
pub(crate) const TYPE_NAMES: &[(TypeName, &str)] = &[
    (TypeName::Number, "number"),
    (TypeName::Color, "Color"),
    (TypeName::Example, "Example"),
    (TypeName::Unit, "Unit"),
    (TypeName::Box, "Box"),
    (TypeName::Position, "Position"),
    (TypeName::Offset, "Offset"),
    (TypeName::Ident, "Ident"),
    (TypeName::C4, "C4"),
    (TypeName::D4, "D4"),
    (TypeName::Dir, "Dir"),
    (TypeName::DiagDir, "DiagDir"),
    (TypeName::Dir8, "Dir8"),
    (TypeName::Axis, "Axis"),
    (TypeName::DiagAxis, "DiagAxis"),
    (TypeName::Axis4, "Axis4"),
    (TypeName::Sym, "Sym"),
    (TypeName::Sense, "Sense"),
];

pub(crate) const PLAUSIBILITIES: &[(Plausibility, &str)] = &[
    (Plausibility::Ordinary, "ordinary"),
    (Plausibility::Variant, "variant"),
    (Plausibility::Borderline, "borderline"),
    (Plausibility::Foreign, "foreign"),
];

// The head symbols of an arcdata file's forms.
pub(crate) const REPRESENTATIVE: &str = "representative";
pub(crate) const PARAM: &str = "param";
pub(crate) const EXCLUDE: &str = "exclude";
pub(crate) const ALTS_RECORD: &str = "alts";
pub(crate) const ALT_RECORD: &str = "alt";
pub(crate) const APPROXIMATED_RECORD: &str = "approximated";
pub(crate) const WITNESS: &str = "witness";
pub(crate) const RELAXED: &str = "relaxed";
pub(crate) const SEPARATES: &str = "separates";
pub(crate) const ASSIGN: &str = "assign";
pub(crate) const INPUT: &str = "input";
pub(crate) const OUTPUT: &str = "output";
pub(crate) const GRID: &str = "grid";
/// A grid cell that gives no row.
pub(crate) const EMPTY_CELL: &str = "_";
/// The mark of a grid's anchor cell, `@_` or `@1`.
pub(crate) const ANCHOR_MARK: char = '@';
pub(crate) const UNDEFINED: &str = "undefined";
// The verdicts and the case name that are no alt's name.
pub(crate) const CONCEPT: &str = "concept";
pub(crate) const ANY: &str = "any";
pub(crate) const OTHER: &str = "other";

/// The spelling of `value` in `table`.
pub fn spelling<T: PartialEq>(table: &[(T, &'static str)], value: &T) -> &'static str {
    table.iter().find(|(v, _)| v == value).map(|(_, s)| *s).expect("each value of a closed vocabulary has a spelling")
}

/// The value `text` spells in `table`, if it spells one.
pub(crate) fn parse<T: Copy>(table: &[(T, &'static str)], text: &str) -> Option<T> {
    table.iter().find(|(_, s)| *s == text).map(|(v, _)| *v)
}
