//! The frame rules of the registry: for each lib column of type `Position` or
//! `Box`, how its values get their frame from the columns that compute them
//! ([`FrameRule`]), as the registry file's `frames` forms declare it and the
//! defaults fill in the rest.

use super::*;

/// Whether a column of type `ty` has a frame: `Box` and `Position`. An `Offset`
/// is a change of position, which stands in no frame.
pub fn has_frame(ty: &ValueType) -> bool {
    ty.is_box() && *ty != ValueType::Offset
}

impl Column {
    /// Whether the column has a frame: its declared type is fixed and
    /// [`has_frame`], or it is a type parameter whose bound is.
    pub fn has_frame(&self) -> bool {
        match &self.ty {
            ColumnType::Parameter(parameter) => parameter.bound.as_ref().is_some_and(has_frame),
            ty => ty.fixed().is_some_and(has_frame),
        }
    }
}

/// A column that a rule names: a column of a lib relation or macro, or
/// `<input>.<column>` of a component's output, the column of one of the
/// component's inputs.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct FrameColumn {
    /// The component's input, for a rule of a component's output.
    pub input: Option<PortName>,
    pub column: ColumnName,
}

/// How the values of a column get their frame from the columns that compute
/// them. A source of a column that the rule names ([`FrameRule::of`]) gives
/// the frame of that column's values, and a source of any other column gives
/// none.
///
/// - `(of <column> ...)`: the frame of those columns' values; `makes` is
///   false.
/// - `new`: a frame the column makes; `makes` is true and `of` is empty.
/// - `(new (of <column> ...))`: a frame the column makes that lies in the
///   frame of those columns' values; `makes` is true.
#[derive(Clone, PartialEq, Eq, Hash, Debug)]
pub struct FrameRule {
    pub makes: bool,
    pub of: Box<[FrameColumn]>,
}

impl FrameRule {
    /// Whether the rule names the column `column` of the relation, or of the
    /// input `input` of the component.
    pub fn names(&self, input: Option<&PortName>, column: &ColumnName) -> bool {
        self.of.iter().any(|named| named.input.as_ref() == input && named.column == *column)
    }
}

/// The rule that a `frames` form declares for the column `name`, if it does.
pub(super) fn declared_rule<'f>(frames: &'f [(ColumnName, FrameRule)], name: &ColumnName) -> Option<&'f FrameRule> {
    frames.iter().find(|(column, _)| column == name).map(|(_, rule)| rule)
}

impl Registry {
    /// The rule of the column `column` of the lib relation or relation macro
    /// `name` at `mode`, or `None` where the lib declares no such column or
    /// the column has no frame. A column that no `frames` form names takes
    /// `(of <each column that has a frame and that the mode binds>)`.
    pub fn relation_frame(&self, name: &LibName, mode: &Mode, column: &ColumnName) -> Option<FrameRule> {
        let relation = self.algebra_relation(name)?;
        if !relation.columns.iter().find(|own| own.name == *column)?.has_frame() {
            return None;
        }
        if let Some(rule) = declared_rule(&relation.frames, column) {
            return Some(rule.clone());
        }
        let of = relation.columns.iter().filter(|own| own.has_frame() && mode.bound.contains(&own.name)).map(|own| FrameColumn { input: None, column: own.name.clone() });
        Some(FrameRule { makes: false, of: of.collect() })
    }

    /// The rule of the column `column` of the output `output` of the component
    /// `component`, or `None` where the lib declares no such column or the
    /// column has no frame. A column that no `frames` form names takes
    /// `(of <each column that has a frame, other than key, of the component's inputs>)`.
    pub fn output_frame(&self, component: &LibName, output: &PortName, column: &ColumnName) -> Option<FrameRule> {
        let LibEntry::Component(component) = self.entry(component)? else { return None };
        let output = component.outputs.iter().find(|own| own.name == *output)?;
        if !output.columns.iter().find(|own| own.name == *column)?.has_frame() {
            return None;
        }
        if let Some(rule) = declared_rule(&output.frames, column) {
            return Some(rule.clone());
        }
        let of = component.inputs.iter().flat_map(|input| {
            input.port.columns.iter().filter(|own| !is_key(own) && own.has_frame()).map(|own| FrameColumn { input: Some(input.port.name.clone()), column: own.name.clone() })
        });
        Some(FrameRule { makes: false, of: of.collect() })
    }
}
