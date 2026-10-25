//! The check of the columns of each site.

use super::reads::form_reads;
use super::types::result;
use super::{Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::NodePath;
use crate::program::SiteArg;
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
    /// record column that the record does not have, as
    /// [`ResolvedProgram::column_position`] and
    /// [`ResolvedProgram::column_group`] give the columns of a site. An atom
    /// whose read resolves to no relation of known columns, a relation that
    /// no block derives or a name the scope check refuses, has no site
    /// refused here.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let program = input.scope.program;
        let mut refused: Vec<(&'static str, NodePath)> = Vec::new();
        for read in form_reads(input.form, input.path) {
            let atom_at = input.path.join(&read.at);
            if reads_unreadable(program, input.scope.registry, &atom_at) {
                refused.push(("a body atom reads a lib relation or a relation macro, no proposer or component", read.at.clone()));
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
                    refused.push(("the atom has a site on the column of this site already", read.at.child(index)));
                    continue;
                }
                if position.is_some() {
                    continue;
                }
                if program.column_group(&at).is_none() {
                    refused.push(("the site is on a column that the relation its atom reads does not have", read.at.child(index)));
                    continue;
                }
                for (arg, field) in site.value.args.iter().zip(0u32..) {
                    let is_field = matches!(arg, SiteArg::NamedLabel { .. } | SiteArg::Field(_));
                    if is_field && program.column_position(&at.child(field)).is_none() {
                        refused.push(("the site names a field that the record of its column does not have", read.at.child(index).child(field)));
                    }
                }
            }
        }
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        result(refused.into_iter().map(|(message, at)| Refusal { message: message.into(), at: order.canonical_path(&at) }).collect())
    }

    /// Each refusal stands as soon as its site does, since the site's column
    /// and the relation its atom reads stand before its arguments.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        super::prefix::standing(prefix, self.check(&super::prefix::whole(prefix)), &|_| true)
    }
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
