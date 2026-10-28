//! The records of a form of the two lib files as the reader reads it,
//! before the registry's entries are made from them.

use super::*;

/// A relation macro, or a proposer written in arclog with its clause as the
/// definition, as its forms write it, before its declaration.
pub(super) struct WrittenRelation {
    pub(super) name: LibName,
    pub(super) place: SourcePlace,
    pub(super) columns: LabelColumns,
    pub(super) definition: Node<Body>,
    /// The items of the `(frames ...)` form of a macro, none for a proposer.
    pub(super) frames: Box<[SExpr]>,
    /// The rules of the `(types ...)` form of a macro, none for a proposer.
    pub(super) rules: Box<[TypeRule]>,
}

/// Each column of a form, with the label of the form's body that the
/// column stands for and the type the form declares for it, where it does.
pub(super) type LabelColumns = Box<[LabelColumn]>;

/// A `component` form's name, kind, type parameters and inputs, and the
/// items of its `outputs` form.
pub(super) struct ComponentHead<'e> {
    pub(super) name: LibName,
    pub(super) kind: ComponentKind,
    pub(super) type_parameters: Box<[TypeParameter]>,
    pub(super) inputs: Box<[InputPort]>,
    pub(super) outputs: &'e [SExpr],
}

/// A `(proposer <name> arclog (columns <Label> ...))` form: the proposer's
/// name, the place of its form, and the labels it names, in the order the
/// form gives them.
pub(super) struct ArclogProposer {
    pub(super) name: LibName,
    pub(super) place: SourcePlace,
    pub(super) columns: Box<[Box<str>]>,
}

/// A body of either file, whose reads [`FileReader::check_reads`] checks
/// once every form is read, and the place of its form.
pub(super) struct BodyInFile {
    pub(super) body: Node<Body>,
    pub(super) place: SourcePlace,
}
