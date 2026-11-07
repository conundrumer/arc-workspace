//! The check of the spelling of the program form: the names of labels and
//! of fields, and the elision of sites, as `docs/arclog/arclog.md#sites`
//! gives them.

use super::labels::each_list;
use super::safety::{form_bodies, label_scope, BodyPlace, FormBody};
use super::types::result;
use super::{each_node, CaseFiles, Check, CheckId, CheckInput, CheckResult, Prefix, PrefixResult, Refusal, CheckCacheKey, KeyInput};
use crate::program::path::{NodePath, NodeRef};
use crate::hash::StableHashSet;
use crate::program::{ColumnName, Conjunct, LabelId, LabelUse, Negated, SiteArg};
use crate::read::columns::made_labels;
use crate::safety::{each_label_use_at, list_of};

/// [`CheckId::Spelling`].
pub struct SpellingCheck;

impl Check for SpellingCheck {
    fn id(&self) -> CheckId {
        CheckId::Spelling
    }

    /// No key, since the check reads the text of the files of the case.
    fn cache_key(&self, _: &KeyInput<'_>) -> Option<CheckCacheKey> {
        None
    }

    /// Refuses:
    ///
    /// - a field site whose field name is not PascalCase;
    /// - in a program read from text, a site of one label on a column of a
    ///   fixed type, or a field site, whose label the file names by the
    ///   column's name and which the file does not write as the bare label;
    /// - in a program read from text, a label that a site makes under the
    ///   name of a label already in scope there, or of another label of
    ///   the same body, but where a later branch of an `OR` or an `IF`'s
    ///   else makes a label of the first branch or the then, and but for
    ///   the row's and the candidate's labels in a `never` clause.
    ///
    /// The two rules that read the file's text apply to a form the file
    /// writes as the case program holds it ([`CaseFiles::writes`]), not to
    /// a form that the case's reading of a line makes or rewrites.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let mut refused = field_case(input);
        if let Some(spelled) = input.scope.files.filter(|spelled| spelled.writes(input.path)) {
            refused.extend(elided(input, spelled));
            for form_body in form_bodies(input.form) {
                names(input, spelled, &form_body, &mut refused);
            }
        }
        if refused.is_empty() {
            return CheckResult::Pass;
        }
        result(refused.into_iter().map(|refusal| Refusal { at: input.refusal_path(&refusal.at), ..refusal }).collect())
    }

    /// Undecided: no token stream breaks the spelling, since the stream
    /// names nothing with text.
    fn check_prefix(&self, _prefix: &Prefix<'_>) -> PrefixResult {
        PrefixResult::Undecided
    }
}

fn refusal(message: &str, at: NodePath) -> Refusal {
    Refusal { message: message.into(), at }
}

/// Whether `name` is PascalCase: an uppercase letter, then letters, digits
/// and `_`.
fn is_pascal(name: &str) -> bool {
    let mut chars = name.chars();
    chars.next().is_some_and(|c| c.is_ascii_uppercase()) && chars.all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// The refusals of each field site of the form whose field name is not
/// PascalCase.
fn field_case(input: &CheckInput<'_>) -> Vec<Refusal> {
    let mut refused = Vec::new();
    each_node(NodeRef::from(input.form), &NodePath::default(), &mut |node, at| {
        let at = &NodePath::from(at);
        if let NodeRef::Site(site) = node {
            for (arg, index) in site.value.args.iter().zip(0u32..) {
                if let SiteArg::Field(field) = arg {
                    if matches!(&field.column, ColumnName::Written(name) if !is_pascal(name)) {
                        refused.push(refusal("a field's name is PascalCase", at.child(index)));
                    }
                }
            }
        }
    });
    refused
}

/// The name the file writes for the label `use_` at `at`, a path relative
/// to the form, where `use_` is a label's.
fn use_name<'a>(input: &CheckInput<'_>, spelled: &CaseFiles<'a>, at: &NodePath, use_: &LabelUse) -> Option<&'a str> {
    let label = match use_ {
        LabelUse::Fresh(label) | LabelUse::Join(label) | LabelUse::Key(label) => *label,
        LabelUse::Zero => return None,
    };
    let scope = label_scope(input.scope.labels, at).first().map(|entry| entry.scope.clone())?;
    spelled.label_name(&input.path.join(&scope), label)
}

/// The refusals of each site of an atom of the form, and of each field
/// site below one, that the file writes with its column's name where the
/// bare label spells it.
fn elided(input: &CheckInput<'_>, spelled: &CaseFiles<'_>) -> Vec<Refusal> {
    let mut refused = Vec::new();
    let named = |at: &NodePath, column: &ColumnName, args: &[SiteArg]| match (column, args) {
        (ColumnName::Written(column), [SiteArg::Label(use_)]) => use_name(input, spelled, at, use_) == Some(&**column),
        _ => false,
    };
    each_node(NodeRef::from(input.form), &NodePath::default(), &mut |node, at| {
        let at = &NodePath::from(at);
        match node {
        NodeRef::Conjunct(conjunct) => {
            let Some(atom) = conjunct.atom() else { return };
            let elided = spelled.layout(&input.path.join(at)).map_or(&[][..], |layout| &layout.elided_sites[..]);
            for (site, index) in atom.value().sites.iter().zip(0u32..) {
                if !elided.contains(&index) && named(at, &site.column, &site.value.args) {
                    refused.push(refusal("the site elides to its bare label", at.child(index)));
                }
            }
        }
        NodeRef::Site(site) => {
            for (arg, index) in site.value.args.iter().zip(0u32..) {
                if let SiteArg::Field(field) = arg {
                    if named(at, &field.column, &field.value.args) {
                        refused.push(refusal("the field site elides to its bare label", at.child(index)));
                    }
                }
            }
        }
        _ => {}
        }
    });
    refused
}

/// A label that a site of a body makes, at the site's path, with the
/// labels visible there and the labels of an `OR`'s first branch or an
/// `IF`'s then that the site's list may name.
struct Made {
    label: LabelId,
    at: NodePath,
    visible: StableHashSet<LabelId>,
    named: Vec<LabelId>,
}

/// Pushes onto `refused` each label of `form_body` that a site makes under
/// the name of a label in scope there, or of another label the body makes
/// before it, but for a label of an `OR`'s first branch or an `IF`'s then.
/// A `never` clause makes the row's and the candidate's labels again at
/// its own sites, so it is read with no labels from its context.
fn names(input: &CheckInput<'_>, spelled: &CaseFiles<'_>, form_body: &FormBody<'_>, refused: &mut Vec<Refusal>) {
    let given: Vec<LabelId> = match form_body.place {
        BodyPlace::Branch => form_body.fields.clone(),
        BodyPlace::List | BodyPlace::Input(..) => form_body.given.iter().chain(&form_body.fields).copied().collect(),
    };
    let visible: StableHashSet<LabelId> = given.iter().copied().chain(made_labels(form_body.body.value())).collect();
    let mut made = Vec::new();
    each_list(&list_of(form_body.body.value(), &form_body.at), &visible, &[], &mut |list, visible, named| {
        for (at, conjunct) in list {
            if let Conjunct::Atom(_) | Conjunct::Constraint(_) | Conjunct::Not(Negated::Atom(_)) = conjunct {
                each_label_use_at(NodeRef::Conjunct(conjunct), at, &mut |at, use_| {
                    if let LabelUse::Fresh(label) | LabelUse::Key(label) = use_ {
                        made.push(Made { label, at: at.clone(), visible: visible.clone(), named: named.to_vec() });
                    }
                });
            }
        }
    });
    made.sort_by(|a, b| a.at.cmp(&b.at));
    let name = |label: LabelId| use_name(input, spelled, &form_body.at, &LabelUse::Join(label));
    for (b, index) in made.iter().zip(0..) {
        let Some(b_name) = name(b.label) else { continue };
        let same = |label: LabelId| label != b.label && name(label) == Some(b_name) && !b.named.contains(&label);
        let earlier = || made[..index].iter().map(|a| a.label).filter(|&label| same(label));
        if given.iter().any(|&label| same(label)) || earlier().any(|label| b.visible.contains(&label)) {
            refused.push(refusal("the site makes a label already in scope", b.at.clone()));
        } else if earlier().next().is_some() {
            refused.push(refusal("the site makes a label under the name of another label of the body", b.at.clone()));
        }
    }
}
