//! The check of the columns of each site.

use super::reads::form_reads;
use super::types::result;
use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::NodePath;
use crate::eval::determinations::relation_spelled;
use crate::program::{column_spelled, Form, OutputOwner, ProgramRelation, RelationRef, SiteArg};
use crate::registry::{LibEntry, Registry};
use crate::resolver::{Resolution, ResolvedProgram};

/// [`CheckId::SiteColumns`].
pub struct SiteColumnsCheck;

impl Check for SiteColumnsCheck {
    fn id(&self) -> CheckId {
        CheckId::SiteColumns
    }

    fn cache_key(&self, at: &KeyInput<'_>) -> Option<CheckCacheKey> {
        Some(at.base(self.id()))
    }

    /// Refuses each site of an atom of the form on a column that an earlier
    /// site of the atom names, and each site on a column that the
    /// relation the atom reads does not have, and each field of a site on a
    /// record column that the record does not have, and each field site at a
    /// site on one column, and each bare label at a site on a record, and each
    /// field site on a record that holds other than one bare label (the shapes
    /// that `IrBuilder::site` takes as impossible), as
    /// [`ResolvedProgram::column_position`] and
    /// [`ResolvedProgram::column_group`] give the columns of a site. An atom
    /// whose read resolves to no relation of known columns, a relation that
    /// no block derives or a name the scope check refuses, has no site
    /// refused here.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        site_refusals(input, false)
    }

    /// Each refusal stands as soon as its site does, since the site's column
    /// and the relation its atom reads stand before its arguments. A site of
    /// an `INIT` form's read of its own output, on a type parameter that no
    /// site of the partial form binds yet, waits for the form: the
    /// projection that binds the parameter can be the head of the input that
    /// holds the site, which the stream writes after the input's body.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::standing(prefix, site_refusals(&super::prefix::whole(prefix), true), &|_| true)
    }
}

/// The refusals of [`SiteColumnsCheck`] of the form of `input`, less those
/// at each site of a read of the form's own output on a record of no field
/// where `partial` holds, as [`SiteColumnsCheck::check_prefix`] gives.
fn site_refusals(input: &CheckInput<'_>, partial: bool) -> CheckResult {
    let program = input.scope.program;
    let mut refused: Vec<(String, NodePath)> = Vec::new();
    for read in form_reads(input.form, input.path) {
        let atom_at = input.path.join(&read.at);
        if reads_unreadable(program, input.scope.registry, &atom_at) {
            refused.push(("a body atom reads a lib relation or a relation macro, no proposer or component".to_owned(), read.at.clone()));
            continue;
        }
        if !has_columns(program, input.scope.registry, &atom_at) {
            continue;
        }
        for (site, index) in read.atom.sites.iter().zip(0u32..) {
            let at = atom_at.child(index);
            let position = program.column_position(&at);
            let on_column_already = read.atom.sites.iter().zip(0u32..).take(index as usize).any(|(earlier, before)| {
                let before_position = program.column_position(&atom_at.child(before));
                earlier.column == site.column || (position.is_some() && position == before_position)
            });
            if on_column_already {
                refused.push(("the atom has a site on the column of this site already".to_owned(), read.at.child(index)));
                continue;
            }
            let site_text = || format!("the site on column `{}` of the relation `{}`", column_spelled(&site.column), relation_text(&read.atom.relation));
            if position.is_some() {
                for (arg, field) in site.value.args.iter().zip(0u32..) {
                    if matches!(arg, SiteArg::Field(_)) {
                        refused.push((format!("{} holds a field site, and a column of a fixed type or of one label's type takes one label", site_text()), read.at.child(index).child(field)));
                    }
                }
                continue;
            }
            if partial && program.column_group(&at).is_some_and(|group| group.len == 0) && own_output(input.form, &read.atom.relation) {
                continue;
            }
            if program.column_group(&at).is_none() {
                refused.push(("the site is on a column that the relation its atom reads does not have".to_owned(), read.at.child(index)));
                continue;
            }
            for (arg, field) in site.value.args.iter().zip(0u32..) {
                let is_field = matches!(arg, SiteArg::NamedLabel { .. } | SiteArg::Field(_));
                if is_field && program.column_position(&at.child(field)).is_none() {
                    refused.push(("the site names a field that the record of its column does not have".to_owned(), read.at.child(index).child(field)));
                }
                match arg {
                    SiteArg::Label(_) => refused.push((format!("{} holds a bare label, and each argument of a site on a record is a site on one field, `(:<Field> <label>)`", site_text()), read.at.child(index).child(field))),
                    SiteArg::Field(inner) if !matches!(&inner.value.args[..], [SiteArg::Label(_)]) => {
                        refused.push((format!("{} holds a field site that is not on one bare label, and each argument of a site on a record is a site on one field, `(:<Field> <label>)`", site_text()), read.at.child(index).child(field)))
                    }
                    _ => {}
                }
            }
        }
    }
    if refused.is_empty() {
        return CheckResult::Pass;
    }
    let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
    result(refused.into_iter().map(|(message, at)| Refusal { message: message.into_boxed_str().into(), at: order.canonical_path(&at) }).collect())
}

/// Whether `relation` is an output of `form`, an `INIT` form.
fn own_output(form: &Form, relation: &RelationRef) -> bool {
    matches!((form, relation), (Form::Instance(instance), RelationRef::Output(output)) if output.of == OutputOwner::Instance(instance.value().name.clone()))
}

/// Whether the read at `atom`, a path in `program`, resolves to a lib
/// proposer or a lib component, which no body atom reads.
fn reads_unreadable(program: &ResolvedProgram, registry: &Registry, atom: &NodePath) -> bool {
    match program.resolution(atom) {
        Some(Resolution::Lib(name)) => matches!(registry.entry(name), Some(LibEntry::Proposer(_) | LibEntry::Component(_))),
        _ => false,
    }
}

/// Whether the read at `atom`, a path in `program`, resolves to a relation
/// whose columns the resolver places its sites on: a node of the graph, or
/// a lib relation or relation macro.
fn has_columns(program: &ResolvedProgram, registry: &Registry, atom: &NodePath) -> bool {
    match program.resolution(atom) {
        Some(Resolution::Node(_)) => true,
        Some(Resolution::Lib(name)) => match registry.entry(name) {
            Some(LibEntry::Relation(_) | LibEntry::Proposer(_) | LibEntry::Macro(_)) => true,
            Some(LibEntry::Component(_)) | None => false,
        },
        Some(Resolution::Undefined(_) | Resolution::Unresolved) | None => false,
    }
}

/// `relation` as the program spells it.
fn relation_text(relation: &RelationRef) -> String {
    match relation {
        RelationRef::Fact(fact) => fact.spelled(),
        RelationRef::Lib(name) => name.0.to_string(),
        RelationRef::Declared(name) => relation_spelled(&ProgramRelation::Declared(name.clone())),
        RelationRef::Output(name) => relation_spelled(&ProgramRelation::Output(name.clone())),
        RelationRef::DefinedPort(port) => port.0.to_string(),
    }
}
