//! The check of the `OUT` form (`docs/arclog/arclog.md#the-out-form`): its
//! atoms, its sites and the types of its two columns, and, for a form read
//! from a solver's files, its place in them and that the solver holds one.

use super::types::PoseOr;
use super::{Check, CheckCacheKey, CheckId, CheckInput, CheckResult, KeyInput, Prefix, PrefixResult, Refusal, Scope};
use super::prefix::refused;
use crate::program::canonical::{CanonicalOrder, SearchBudget};
use crate::program::path::{NodePath, NodeRef};
use crate::program::{Atom, ColumnName, Conjunct, FactRelation, Form, LabelId, LabelUse, Out, RelationRef, Site, SiteArg};
use crate::resolver::Resolution;
use crate::types::ValueType;

/// [`CheckId::Out`].
pub struct OutCheck;

/// The types of the columns an `OUT` selects, in written order: a Position,
/// which the engine holds as a box, then a Color.
const SELECTED: [ValueType; 2] = [ValueType::Box, ValueType::Color];

/// The refusal of an `OUT` form that selects other columns than a Position,
/// then a Color.
const COLUMNS: &str = "an `OUT` form selects a Position column, then a Color column";

/// Whether the form is read whole, or as a prefix of a decode, where a
/// refusal stands only if no completion undoes it.
#[derive(Clone, Copy)]
enum Reading<'p, 'a> {
    Whole,
    Prefix(&'p Prefix<'a>),
}

impl Reading<'_, '_> {
    /// Whether the form is complete: read whole, or a prefix that holds no
    /// open node.
    fn complete(&self) -> bool {
        match self {
            Reading::Whole => true,
            Reading::Prefix(prefix) => prefix.open.is_none(),
        }
    }

    /// Whether the node at `at`, a path relative to the form, is open: the
    /// decode may still add a site to an atom that is.
    fn is_open(&self, at: &NodePath) -> bool {
        match self {
            Reading::Whole => false,
            Reading::Prefix(prefix) => prefix.is_open(at),
        }
    }
}

impl Check for OutCheck {
    fn id(&self) -> CheckId {
        CheckId::Out
    }

    /// No key, since the check reads the other forms of the case program
    /// and the files it was read from.
    fn cache_key(&self, _: &KeyInput<'_>) -> Option<CheckCacheKey> {
        None
    }

    /// Refuses an `OUT` form that breaks a rule of
    /// `docs/arclog/arclog.md#the-out-form`: it holds one atom of two sites
    /// or two atoms of one site each, each atom reads `input` or a relation
    /// the program declares, each site selects one column, or one field of a
    /// record column, with one label marked `^`, the first such label is a
    /// Position and the second a Color; and, where the program was read from
    /// a solver's files, the form is the last of the solver's file, under no
    /// claim and in no `ALT` block, and the case program holds no other.
    fn check(&self, input: &CheckInput<'_>) -> CheckResult {
        let Form::Out(out) = input.form else { return CheckResult::Pass };
        let mut found = found(&input.scope, input.path, out.value(), Reading::Whole);
        found.extend(placed(input));
        if found.is_empty() {
            return CheckResult::Pass;
        }
        let order = CanonicalOrder::of(input.form, &mut SearchBudget::new());
        CheckResult::Refuse(found.into_iter().map(|(at, message)| Refusal { message: message.into(), at: order.canonical_path(&at) }).collect())
    }

    /// Refuses what no completion of the prefix undoes: a conjunct that is
    /// no atom, a third atom, an atom of a relation `OUT` does not read, a
    /// site that no label marked `^` alone completes, a second atom after a
    /// first of two sites, an atom or a site that no column of the type the
    /// next selected column has can complete, a label whose type is no
    /// Position, as the first, or no Color, as the second; and, once the form
    /// is complete, a form that selects fewer than two columns.
    fn check_prefix(&self, prefix: &Prefix<'_>) -> PrefixResult {
        let Form::Out(out) = prefix.partial else { return PrefixResult::Undecided };
        let found = found(&prefix.scope, prefix.path, out.value(), Reading::Prefix(prefix));
        refused(found.into_iter().map(|(at, message)| Refusal { message: message.into(), at }).collect())
    }
}

/// The refusals of the rules of the form `out`, at `form` in the program,
/// each at its path relative to the form.
fn found(scope: &Scope<'_>, form: &NodePath, out: &Out, reading: Reading<'_, '_>) -> Vec<(NodePath, &'static str)> {
    let body = NodePath::default().child(Out::BODY);
    let conjuncts = &out.key.body.value().conjuncts;
    let mut refused = Vec::new();
    let mut selected: Vec<(NodePath, LabelId)> = Vec::new();
    let mut counts = Vec::new();
    for (index, conjunct) in conjuncts.iter().enumerate() {
        let at = body.child(index as u32);
        let Conjunct::Atom(atom) = conjunct else {
            refused.push((at, "an `OUT` form holds atoms alone"));
            continue;
        };
        if index >= 2 {
            refused.push((at, "an `OUT` form holds one atom or two"));
            continue;
        }
        let atom = atom.value();
        if !reads_output(&atom.relation) {
            refused.push((at.clone(), "an `OUT` atom reads `input` or a relation the program declares"));
        }
        counts.push(atom.sites.len());
        let open = reading.is_open(&at);
        for (site_index, site) in atom.sites.iter().enumerate() {
            let site_at = at.child(site_index as u32);
            match key_label(site) {
                Ok(Some(label)) => selected.push((site_at, label)),
                Ok(None) if open => {
                    if let Some(wanted) = SELECTED.get(selected.len()) {
                        if !column_may_hold(scope, form, &at, atom, Some(&site.column), wanted) {
                            refused.push((site_at, COLUMNS));
                        }
                    }
                }
                Ok(None) => {}
                Err(message) => refused.push((site_at, message)),
            }
        }
        if open && atom.sites.is_empty() {
            if let Some(wanted) = SELECTED.get(selected.len()) {
                if !column_may_hold(scope, form, &at, atom, None, wanted) {
                    refused.push((at, COLUMNS));
                }
            }
        }
    }
    refused.extend(site_counts(&counts, &body, reading));
    for (position, (at, label)) in selected.iter().enumerate() {
        let Some(wanted) = SELECTED.get(position) else {
            refused.push((at.clone(), "an `OUT` form selects two columns"));
            continue;
        };
        match label_type(scope, *label) {
            Some(ty) if ty != wanted => refused.push((at.clone(), COLUMNS)),
            None if reading.complete() => refused.push((at.clone(), "the label of an `OUT` site has no type")),
            _ => {}
        }
    }
    refused
}

/// The refusals of the counts of sites of the atoms, `counts`: a one-atom
/// form holds two sites and a two-atom form one site in each atom, so that a
/// first atom of two sites, or of none or three once a second atom stands,
/// is refused, and so is a complete form that selects fewer than two
/// columns.
fn site_counts(counts: &[usize], body: &NodePath, reading: Reading<'_, '_>) -> Vec<(NodePath, &'static str)> {
    let message = "an `OUT` form holds one atom of two sites or two atoms of one site each";
    let mut refused = Vec::new();
    match counts {
        [] => {
            if reading.complete() {
                refused.push((body.clone(), message));
            }
        }
        [first] => {
            if *first > 2 || (reading.complete() && *first != 2) {
                refused.push((body.child(0), message));
            }
        }
        [first, second] => {
            if *first != 1 {
                refused.push((body.child(0), message));
            }
            if *second > 1 || (reading.complete() && *second != 1) {
                refused.push((body.child(1), message));
            }
        }
        _ => unreachable!("`found` counts the sites of two atoms at most"),
    }
    refused
}

/// Whether the atom at `atom_at` of the form at `form`, the open atom of an
/// `OUT` form, may still select a column of type `wanted`: at its site on
/// `column` where it has one, and otherwise at some column of its relation.
/// A relation whose columns are not known, and a column whose type is not
/// known, may.
fn column_may_hold(scope: &Scope<'_>, form: &NodePath, atom_at: &NodePath, atom: &Atom, column: Option<&ColumnName>, wanted: &ValueType) -> bool {
    let Some(Resolution::Node(node)) = scope.program.resolution(&form.join(atom_at)) else { return true };
    let Some(paths) = scope.program.read_row_paths(*node) else { return true };
    let Some(inference) = scope.inference.infer(form) else { return true };
    let reading = inference.reading(PoseOr::Given);
    paths
        .iter()
        .filter(|path| column.is_none_or(|column| path.first() == Some(column)))
        .any(|path| scope.inference.site_type(reading, atom, path).is_none_or(|ty| ty == *wanted))
}

/// Whether an atom of an `OUT` form may read `relation`: `input`, or a
/// relation the program declares, as a `RULE` body reads one.
fn reads_output(relation: &RelationRef) -> bool {
    match relation {
        RelationRef::Fact(fact) => *fact == FactRelation::Input,
        RelationRef::Declared(_) | RelationRef::Output(_) => true,
        RelationRef::Lib(_) | RelationRef::DefinedPort(_) => false,
    }
}

/// The label that `site` selects its column or field with, which is marked
/// `^` and is the only label of the site; none while the site holds no
/// label yet; or why the site is none.
fn key_label(site: &Site) -> Result<Option<LabelId>, &'static str> {
    const ONE: &str = "an `OUT` site selects one column, or one field of a record column, with one label marked `^`";
    let marked = |label: &LabelUse| match label {
        LabelUse::Key(label) => Ok(Some(*label)),
        _ => Err(ONE),
    };
    match &site.value.args[..] {
        [] => Ok(None),
        [SiteArg::Label(label) | SiteArg::NamedLabel { label, .. }] => marked(label),
        [SiteArg::Field(field)] => match &field.value.args[..] {
            [] => Ok(None),
            [SiteArg::Label(label) | SiteArg::NamedLabel { label, .. }] => marked(label),
            _ => Err(ONE),
        },
        _ => Err(ONE),
    }
}

/// A site that an `OUT` form selects a column with: the atom it stands in,
/// and the path, relative to the form, of the node that names the selected
/// column, as [`crate::resolver::ResolvedProgram::column_position`] takes it.
#[derive(Clone, Debug)]
pub struct SelectedSite<'a> {
    pub atom: &'a Atom,
    pub at: NodePath,
}

/// The sites that select the columns of `out`, in written order: the
/// Position column's, then the Color column's, in a form that passes the
/// check.
pub fn selected_sites(out: &Out) -> Vec<SelectedSite<'_>> {
    let body = NodePath::default().child(Out::BODY);
    let mut sites = Vec::new();
    for (index, conjunct) in out.key.body.value().conjuncts.iter().enumerate() {
        let Conjunct::Atom(atom) = conjunct else { continue };
        let atom_at = body.child(index as u32);
        for (site_index, site) in atom.value().sites.iter().enumerate() {
            let site_at = atom_at.child(site_index as u32);
            if let Ok(Some(_)) = key_label(site) {
                let at = match &site.value.args[..] {
                    [SiteArg::Label(_)] => site_at,
                    _ => site_at.child(0),
                };
                sites.push(SelectedSite { atom: atom.value(), at });
            }
        }
    }
    sites
}

/// The type of `label`, a label of the `OUT` form under check.
fn label_type<'s>(scope: &'s Scope<'_>, label: LabelId) -> Option<&'s ValueType> {
    scope.labels.iter().find(|entry| entry.scope.0.is_empty() && entry.label == label)?.ty.as_ref()
}

/// The refusals of the place of the form in the solver's files, where the
/// program was read from them: the form is the last form of the solver's
/// arclog file, outside every claim and `ALT` block, and the file holds no
/// other `OUT` form, at any depth, equal forms included.
fn placed(input: &CheckInput<'_>) -> Vec<(NodePath, &'static str)> {
    let Some(files) = input.scope.files else { return Vec::new() };
    let mut refused = Vec::new();
    let (_, owning, file_path) = files.file_of(input.path);
    let last = owning.program.value().forms.len();
    if file_path.0.len() != 1 || file_path.0[0].0 as usize + 1 != last {
        refused.push((NodePath::default(), "the `OUT` form is the last form of the file, under no claim and in no `ALT` block"));
    }
    let mut outs = 0;
    super::each_node(NodeRef::Program(owning.program.value()), &NodePath::default(), &mut |node, _| outs += usize::from(matches!(node, NodeRef::Out(_))));
    if outs > 1 {
        refused.push((NodePath::default(), "a solver holds one `OUT` form"));
    }
    refused
}

/// The refusal of a case program read from a solver's files that holds no
/// `OUT` form, at its last form, or at the program where it holds none.
pub(super) fn missing(program: &crate::program::Program) -> Option<Refusal> {
    let none = !program.forms.iter().any(|form| matches!(form, Form::Out(_)));
    let at = program.forms.len().checked_sub(1).map_or_else(NodePath::default, |last| NodePath::top(last as u32));
    none.then(|| Refusal { message: "a solver holds one `OUT` form".into(), at })
}
