//! The writer of arclog and arcdata files. Reading a file of the corpus and
//! writing it again gives the same bytes.
//!
//! [`write_solver`] stays `todo!()` for a later stage.

#![allow(unused_variables, dead_code)]

mod arcdata;
mod arclog;

pub(crate) use arclog::{declared, output_name, relation_ref};

use crate::layout::Layout;
use crate::program::{Arcdata, Form, Node, Program};
use std::sync::Arc;
use crate::registry::Registry;
use crate::solver::Solver;
use crate::terms::InternTable;

/// The text of a solver's two files.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct SolverText {
    pub arclog: String,
    pub arcdata: String,
}

/// The text of the arclog file that `program` and `layout`, as
/// [`crate::read::read_arclog`] reads them, give: each token at the place
/// its node's layout gives, each comment of the layout, and each site the
/// layout elides as its bare label. A token whose node has no layout stands
/// one space after the token before it. Each name and column of `program`
/// is written as a file writes it, and each label is named in the layout of
/// its scope, a form that an `ALT` gave to a `DEMO_RULE` form a scope of its
/// own; a slot of a decode is a fault.
pub fn write_arclog(program: &Node<Program>, layout: &Layout) -> String {
    arclog::write(program.value(), layout)
}

/// The text of the arcdata file that `arcdata` and `layout`, as
/// [`crate::read::read_arcdata`] reads them, give, as [`write_arclog`]
/// writes the arclog file: each token at the place its node's layout gives,
/// and each comment of the layout whose place is in
/// [`crate::layout::SourceFile::Arcdata`]. A value read from the file is
/// written as the file wrote it.
pub fn write_arcdata(arcdata: &Node<Arcdata>, layout: &Layout) -> String {
    arcdata::write(arcdata.value(), layout)
}

/// The two files of `solver`, laid out as the converter lays out each form,
/// with the comments, strings and label names of its layout.
pub fn write_solver(solver: &Solver) -> SolverText {
    todo!()
}

/// A synthesized program as an arclog file, in the program form and the
/// s-expression layout, with names in place of token ids, and a relation slot
/// written by its index. A column named by its slot is written by the name
/// its label takes, as the next paragraph gives. That name takes the spelling
/// of a fixed-type column (`docs/arclog/arclog.md#sites`), so the reader
/// reads a site on that column as a site on a fixed-type column, and no type
/// parameter's column is so spelled.
///
/// A label that a [`crate::program::SiteArg::NamedLabel`] holds takes that
/// argument's `name`, so the file reads that field at that site. Each name
/// so taken is reserved in its scope, as [`crate::program::LabelId`] gives
/// a scope, before any other label is named. Each other label takes the
/// name of the column or field of the site that makes it, PascalCase, in the
/// order of the labels' ids, which a decode gives in the order of the labels'
/// makes, with the
/// least digit suffix that gives a name no other label of its scope holds
/// or has reserved: in `(:a *A2) (:key *A)`, where the site at `:key` holds a
/// `NamedLabel { name: A }` and the label at `:a` is another label made at
/// `:a`, the label at `:key` is written `A` and the label at
/// `:a` is written `A2`.
///
/// The sites of a read of a derived relation (`&rn`), each on a column named
/// by its slot, are written in ascending order of the relation's slots as the
/// text gives them: the columns of a clause are the labels its written body
/// makes, in the order of the text, so a body that reads a relation with its
/// sites reordered can move its own columns, and the reads of that clause
/// follow the moved slots. A read stays in the order of the program where the
/// new order would change the order of its `^` labels, which is the order of
/// key columns, and where a join of the read would then stand before the site
/// that makes its label.
/// The labels are named in the order the text makes them, so the text reads
/// back to a program that writes the same text. Reads of the outputs of an
/// instance or of a `RIGID_DET`, and of lib relations, keep their order.
///
/// Two labels take one name only where [`Node::apply`](crate::program::Node::apply)
/// gives them one, so the file reads back to the same labels:
/// `(OR ((r (:key *X))) ((s (:key *X))))` is written with `X` at each site,
/// and reads back as two labels.
///
/// A relation slot `n` is written `&rn`. The writer prints each form a decode
/// builds, `RULE`, `DET`, `INIT`, `CHOOSE`, `RIGID_DET`, `OUT` and
/// `DEMONSTRATED`, including
/// explicit record-field sites. It writes a site of an `OUT` form that is a column of one
/// label as `^<column>`, with the column's name whatever the other labels of
/// the form are named, since no label of an `OUT` is read again.
pub fn write_synthesized(program: &Node<Program>, registry: &Registry) -> String {
    synthesized::write(program, registry, None)
}

/// A mutation's display namespace, keyed by the unchanged native LabelIds.
/// It has no part in checked AST equality, stream identity or evaluation.
pub type LabelNames = Vec<Vec<(crate::program::LabelId, Box<str>)>>;

pub(crate) fn write_synthesized_named(program: &Node<Program>, registry: &Registry,
    preferred: Option<&LabelNames>) -> String {
    synthesized::write(program, registry, preferred)
}

pub(crate) fn label_names_named(program: &Node<Program>, registry: &Registry,
    preferred: Option<&LabelNames>) -> LabelNames {
    synthesized::named_forms(program, registry, preferred).into_iter().map(|(_, names, _, _, _)| names).collect()
}

/// `program` with the sites of each read of a derived relation in the order
/// that [`write_synthesized`] writes them. A decode takes its sites in the
/// order its tokens give, which the text does not keep, so this order is the
/// one a program has in common with its text.
pub(crate) fn in_text_order(program: &Node<Program>, registry: &Registry) -> Node<Program> {
    synthesized::in_text_order(program, registry)
}

/// The name of each label of each form of `program`, in form order, as
/// [`write_synthesized`] names them: the form's reserved names, then its
/// other labels in the order of their ids, and then each label of a column or
/// a record field that no site of the form makes. It refuses the programs that
/// `write_synthesized` refuses.
pub fn label_names(program: &Node<Program>, registry: &Registry) -> Vec<Vec<(crate::program::LabelId, Box<str>)>> {
    label_names_named(program, registry, None)
}

/// Engine-written display text keyed by the ORIGINAL AST paths. Synthesized
/// named-record field wrappers are presentation only, never new source paths.
pub(crate) fn node_texts(program: &Node<Program>, layout: Option<&Layout>, registry: &Registry, preferred: Option<&LabelNames>)
    -> Result<std::collections::BTreeMap<crate::program::path::NodePath, String>, String>
{
    use crate::program::path::{NodePath,NodeRef};
    use crate::program::LabelId;
    use crate::layout::SourceFile;
    type NestedSlots = crate::hash::StableHashMap<NodePath, synthesized::Slots>;
    let named = match layout {
        Some(layout) => program.value().forms.iter().enumerate().map(|(i,f)| {
            let names = layout.node(SourceFile::Arclog,&NodePath::top(i as u32))
                .map(|n|n.label_names.to_vec()).unwrap_or_default();
            (f.clone(),names,None,None,NestedSlots::default())
        }).collect(),
        None => synthesized::named_forms(program,registry,preferred).into_iter()
            .map(|(form,names,slots,nested,nested_slots)| (form,names,Some(slots),Some(nested),nested_slots)).collect::<Vec<_>>(),
    };
    /// The layout nodes of `layout` at and below `from`, moved to `to`.
    fn moved(layout: &Layout, from: &NodePath, to: &NodePath) -> Layout {
        let mut out = Layout::default();
        for ((file, path), node) in layout.nodes.range((SourceFile::Arclog, from.clone())..) {
            if *file != SourceFile::Arclog || !path.0.starts_with(&from.0) { break; }
            let path = NodePath(to.0.iter().chain(path.0[from.0.len()..].iter()).cloned().collect());
            out.nodes.insert((SourceFile::Arclog, path), node.clone());
        }
        out
    }
    /// The names of the label scopes of a `DEMONSTRATED` form, the form at
    /// the top-level path `NodePath::top(0)`, and the slots that each form
    /// of its rules reads in, by the form's path below the form.
    struct Within<'w> { alone: &'w Layout, slots: &'w NestedSlots }
    fn walk<'w>(original: NodeRef<'_>, mut display: NodeRef<'_>, at: &NodePath, slots: Option<&'w synthesized::Slots>,
        names: &'w [(LabelId,Box<str>)], within: Option<&Within<'w>>, out: &mut std::collections::BTreeMap<NodePath,String>) -> Result<(),String> {
        // NamedLabel at a decoded record field is printed as (:field LABEL).
        // Its source node is still LABEL, at the original argument path.
        if matches!(original,NodeRef::Label(_)) && matches!(display,NodeRef::Site(_)) {
            let children = display.children();
            if children.len()!=1 {return Err(format!("display field shape mismatch at {at:?}"));}
            display=children[0];
        }
        let text = match (display, within) {
            (NodeRef::DemoRule(rule), Some(within)) => arclog::rule_snippet(rule, &moved(within.alone, &in_alone(at), &NodePath::default())),
            _ => arclog::snippet(display,names)?,
        };
        out.insert(at.clone(),text);
        walk_children(original, display, at, slots, names, within, out)
    }
    /// The path in the layout of a `DEMONSTRATED` form alone of the node at
    /// `at`, a path within the form.
    fn in_alone(at: &NodePath) -> NodePath {
        NodePath(NodePath::top(0).0.iter().chain(at.0[1..].iter()).cloned().collect())
    }
    fn walk_children<'w>(original: NodeRef<'_>, display: NodeRef<'_>, at: &NodePath, slots: Option<&'w synthesized::Slots>,
        names: &'w [(LabelId,Box<str>)], within: Option<&Within<'w>>, out: &mut std::collections::BTreeMap<NodePath,String>) -> Result<(),String> {
        let original_children=original.children();let display_children=display.children();
        if original_children.len()!=display_children.len() {
            return Err(format!("display child count mismatch at {at:?}"));
        }
        // The sites of a read that the writer put in slot order: the site at
        // position `k` of the display is the original's site `order[k]`.
        let order = original.atom().zip(slots).and_then(|(atom, slots)| synthesized::read_order(atom, slots));
        for (k,display) in display_children.into_iter().enumerate() {
            let i = order.as_ref().map_or(k, |order| order[k]);
            let child_at = at.child(i as u32);
            // Within a `DEMONSTRATED` form, a rule and a form an `ALT` gave
            // a rule name the labels of a scope of their own, and each form
            // of a rule reads in the slots it was ordered by.
            let (names, slots) = match within {
                Some(within) => {
                    let names = if crate::program::canonical::opens_scope(original, i, original_children[i]) {
                        within.alone.node(SourceFile::Arclog, &in_alone(&child_at)).map_or(&[][..], |node| &node.label_names[..])
                    } else { names };
                    (names, within.slots.get(&NodePath(child_at.0[1..].into())).or(slots))
                }
                None => (names, slots),
            };
            walk(original_children[i],display,&child_at,slots,names,within,out)?;
        }
        Ok(())
    }
    let mut out=std::collections::BTreeMap::new();
    for (i,(original,(display,names,slots,nested,nested_slots))) in program.value().forms.iter().zip(named).enumerate() {
        let at = NodePath::top(i as u32);
        // A `DEMONSTRATED` form's rules are scopes of their own: the form
        // has the text of its own alone, and the nodes below it the names
        // of the scope each stands in.
        if let Form::Demonstrated(_) = original {
            let mut alone = Layout::default();
            match (layout, nested) {
                (_, Some(nested)) => synthesized::name_scopes(&mut alone, 0, names.clone(), nested),
                // A read form keeps the layout the file gave it, moved to
                // the place of the program's one form.
                (Some(layout), None) => alone = moved(layout, &at, &NodePath::top(0)),
                (None, None) => return Err(format!("the DEMONSTRATED form {i} has no names for its scopes")),
            }
            out.insert(at.clone(), write_arclog(&Node::new(Program { forms: Arc::from([display.clone()]) }), &alone).trim().to_owned());
            let within = Within { alone: &alone, slots: &nested_slots };
            walk_children(NodeRef::from(original),NodeRef::from(&display),&at,slots.as_ref(),&names,Some(&within),&mut out)?;
            continue;
        }
        walk(NodeRef::from(original),NodeRef::from(&display),&at,slots.as_ref(),&names,None,&mut out)?;
    }
    out.insert(NodePath::default(),match layout {Some(l)=>write_arclog(program,l),None=>write_synthesized_named(program,registry,preferred)});
    Ok(out)
}

/// The numbers a writer gives the Idents it writes, private to the crate's
/// writers, since a number is an order of encodings.
///
/// The Idents are numbered by the order of their contents' encodings, which
/// `TermId::encoding` gives, from the inside out. A value read from a file
/// is written as it was read, and the other Idents of that type in the file
/// are numbered after the largest such value.
#[derive(Clone, Debug, Default)]
pub struct IdentNumbering {
    numbers: crate::hash::StableHashMap<crate::terms::Ident, u32>,
}

impl IdentNumbering {
    /// The numbering of `idents`, the Idents one file writes.
    pub fn new(idents: &[crate::terms::Ident], table: &InternTable) -> Self {
        todo!()
    }

    /// The number written for `ident`.
    pub(crate) fn number(&self, ident: crate::terms::Ident) -> u32 {
        todo!()
    }
}

/// Marks in `layout` each site of the atoms of `out`, the `OUT` form at
/// `form`, that is a column of one label, as written elided: `^<column>`.
pub(crate) fn elide_out_sites(out: &crate::program::Out, form: &crate::program::path::NodePath, layout: &mut Layout) {
    use crate::layout::SourceFile;
    use crate::program::SiteArg;
    let body = form.child(crate::program::Out::BODY);
    for (index, conjunct) in out.key.body.value().conjuncts.iter().enumerate() {
        let Some(atom) = conjunct.atom() else { continue };
        let elided = atom.value().sites.iter().enumerate().filter(|(_, site)| matches!(&site.value.args[..], [SiteArg::Label(_)])).map(|(at, _)| at as u32);
        layout.nodes.entry((SourceFile::Arclog, body.child(index as u32))).or_default().elided_sites = elided.collect();
    }
}

/// The program form of a decoded program: its slots named, its labels named
/// in the scope of each form, and the program written with that layout.
mod synthesized {
    use std::sync::Arc;

    use crate::hash::StableHashMap;
    use crate::layout::{Layout, NodeLayout, SourceFile, SourcePlace};
    use crate::program::path::{NodePath, NodeRef};
    use crate::program::*;
    use crate::registry::{Registry, ColumnType, ParameterSite, TypeParameter, binding_sites};
    use crate::resolver::columns::projection;
    use crate::resolver::form_columns::rigid_outputs;
    use crate::resolver::registry_columns::{component, proposer_columns};
    use crate::trace::label_names::label_name;

    /// Each form of `program` as written, with the name of each of its labels.
    pub(super) fn named_forms(
        program: &Node<Program>,
        registry: &Registry,
        preferred: Option<&super::LabelNames>,
    ) -> Vec<(Form, Vec<(LabelId, Box<str>)>, Slots, Vec<Scope>, StableHashMap<NodePath, Slots>)> {
        let mut synth = Synthesizer::new(registry);
        let mut named = Vec::new();
        for (index, form) in program.value().forms.iter().enumerate() {
            let slots = synth.slots.clone();
            synth.nested_slots.clear();
            let (form, ranks) = synth.in_slot_order(form);
            let form = &form;
            let generated = synth.label_names(form, &ranks);
            // Existing labels keep gold's spellings, including names no longer
            // used after a deletion. Only genuinely new IDs allocate a name.
            // Keep the canonical site's field spelling: the ordinary writer
            // emits an explicit field wrapper when its label differs.
            let names = match preferred.and_then(|all| all.get(index)) {
                None => generated,
                Some(gold) => {
                    let mut held = gold.clone();
                    for (id, name) in generated {
                        if held.iter().any(|(label, _)| *label == id) { continue; }
                        let fresh = label_name(&name, |candidate| held.iter().any(|(_, name)| &**name == candidate));
                        held.push((id, fresh.into()));
                    }
                    held
                }
            };
            let written = synth.form(form, &Names(&names));
            let nested = std::mem::take(&mut synth.nested);
            named.push((written, names, slots, nested, std::mem::take(&mut synth.nested_slots)));
        }
        named
    }

    /// The forms of `program` with the sites of each read of a derived
    /// relation in the order the text writes them, as [`write`] puts them,
    /// and nothing else changed: the program a reader of that text builds,
    /// up to the names and the ids of its labels.
    pub(super) fn in_text_order(program: &Node<Program>, registry: &Registry) -> Node<Program> {
        let mut synth = Synthesizer::new(registry);
        let forms: Vec<Form> = program.value().forms.iter().map(|form| synth.in_slot_order(form).0).collect();
        Node::new(Program { forms: forms.into() })
    }

    pub(super) fn write(program: &Node<Program>, registry: &Registry, preferred: Option<&super::LabelNames>) -> String {
        let mut forms = Vec::new();
        let mut layout = Layout::default();
        for (index, (form, names, _, nested, _)) in named_forms(program, registry, preferred).into_iter().enumerate() {
            name_scopes(&mut layout, index, names, nested);
            if let Form::Out(out) = &form {
                super::elide_out_sites(out.value(), &NodePath::top(index as u32), &mut layout);
            }
            forms.push(form);
        }
        super::write_arclog(&Node::new(Program { forms: forms.into() }), &layout)
    }

    /// The label names of a scope below a form, a `DEMO_RULE` form or a form
    /// that an `ALT` gave one, by its path below the form.
    pub(crate) type Scope = (NodePath, Vec<(LabelId, Box<str>)>);

    /// Puts into `layout` the label names of the form at `index`, `names`,
    /// and those of each scope below it, `nested`.
    pub(super) fn name_scopes(layout: &mut Layout, index: usize, names: Vec<(LabelId, Box<str>)>, nested: Vec<Scope>) {
        let place = SourcePlace { file: SourceFile::Arclog, start: 0, end: 0, line: index as u32 + 1, column: 1 };
        let at = NodePath::top(index as u32);
        let node = |names: Vec<(LabelId, Box<str>)>| NodeLayout { tokens: Box::new([place]), label_names: names.into(), ..NodeLayout::default() };
        layout.nodes.insert((SourceFile::Arclog, at.clone()), node(names));
        for (below, names) in nested {
            let path = NodePath(at.0.iter().chain(below.0.iter()).cloned().collect());
            layout.nodes.insert((SourceFile::Arclog, path), node(names));
        }
    }

    /// The slot each column of a derived relation takes in the text: the
    /// entry at an old slot is the new slot. A relation with no entry, or a
    /// slot past its entry, keeps its slots.
    pub(crate) type Slots = StableHashMap<RelationName, Vec<u32>>;

    /// The place of a label in the order the text makes the labels of its
    /// form, where that is not the order of the ids.
    type Ranks = StableHashMap<LabelId, u32>;

    /// The labels that the site makes (`*X`, `^X`) and the labels it joins,
    /// the sites of its fields included.
    fn site_labels(site: &Site, made: &mut Vec<LabelId>, joined: &mut Vec<LabelId>) {
        for arg in site.value.args.iter() {
            match arg {
                SiteArg::Label(label) | SiteArg::NamedLabel { label, .. } => match label {
                    LabelUse::Fresh(id) | LabelUse::Key(id) => made.push(*id),
                    LabelUse::Join(id) => joined.push(*id),
                    LabelUse::Zero => {}
                },
                SiteArg::Field(field) => site_labels(field, made, joined),
            }
        }
    }

    /// The `^` labels that the site, or a field site of it, makes.
    fn site_keys(site: &Site, keys: &mut Vec<LabelId>) {
        for arg in site.value.args.iter() {
            match arg {
                SiteArg::Label(LabelUse::Key(id)) | SiteArg::NamedLabel { label: LabelUse::Key(id), .. } => keys.push(*id),
                SiteArg::Field(field) => site_keys(field, keys),
                _ => {}
            }
        }
    }

    /// The order in which the text writes the sites of `atom`, where that is
    /// not the order of the program: the position `k` of the text holds the
    /// atom's site `order[k]`. A read of a derived relation, with each site
    /// on a column named by its slot, is written in ascending order of the
    /// slots the text gives (`slots`), sites on one slot keeping their
    /// order. A read stays as it is where the order would change the order of
    /// its `^` labels, which is the order of the key columns of a key body
    /// or an `OUT` form, and where a join of the atom would otherwise stand
    /// before the site of the atom that makes its label, since the stream
    /// names a label after it makes it.
    pub(crate) fn read_order(atom: &Atom, slots: &Slots) -> Option<Vec<usize>> {
        let RelationRef::Declared(name) = &atom.relation else { return None };
        let keys: Option<Vec<u32>> = atom.sites.iter().map(|site| match &site.column {
            ColumnName::Slot(slot) => Some(slots.get(name).and_then(|new| new.get(*slot as usize)).copied().unwrap_or(*slot)),
            ColumnName::Written(_) => None,
        }).collect();
        let keys = keys?;
        let mut order: Vec<usize> = (0..keys.len()).collect();
        order.sort_by_key(|&index| keys[index]);
        if order.iter().enumerate().all(|(position, &index)| position == index) {
            return None;
        }
        let key_order = |indices: &mut dyn Iterator<Item = usize>| {
            let mut keys = Vec::new();
            for index in indices {
                site_keys(&atom.sites[index], &mut keys);
            }
            keys
        };
        if key_order(&mut (0..order.len())) != key_order(&mut order.iter().copied()) {
            return None;
        }
        let labels: Vec<(Vec<LabelId>, Vec<LabelId>)> = atom.sites.iter().map(|site| {
            let (mut made, mut joined) = (Vec::new(), Vec::new());
            site_labels(site, &mut made, &mut joined);
            (made, joined)
        }).collect();
        let mut seen: Vec<LabelId> = Vec::new();
        for &index in &order {
            let (made, joined) = &labels[index];
            let early = joined.iter().any(|id| !seen.contains(id) && labels.iter().any(|(made, _)| made.contains(id)));
            if early {
                return None;
            }
            seen.extend(made);
        }
        Some(order)
    }

    /// `atom` with its sites in the order `read_order` gives. `ranks` takes
    /// the places of the labels the atom makes: the ids of those labels, in
    /// ascending order, go to them in the order of the new sites.
    fn in_order(atom: &Node<Atom>, slots: &Slots, ranks: &mut Ranks) -> Node<Atom> {
        let Some(order) = read_order(atom.value(), slots) else { return atom.clone() };
        let sites = &atom.value().sites;
        let made = |indices: &[usize]| {
            let mut made = Vec::new();
            for &index in indices {
                site_labels(&sites[index], &mut made, &mut Vec::new());
            }
            made
        };
        let program_order: Vec<usize> = (0..order.len()).collect();
        let mut places: Vec<u32> = made(&program_order).iter().map(|label| ranks.get(label).copied().unwrap_or(label.0)).collect();
        places.sort_unstable();
        for (label, place) in made(&order).into_iter().zip(places) {
            ranks.insert(label, place);
        }
        Node::new(Atom { relation: atom.value().relation.clone(), sites: order.iter().map(|&index| sites[index].clone()).collect() })
    }

    fn body_in_order(body: &Node<Body>, slots: &Slots, ranks: &mut Ranks) -> Node<Body> {
        Node::new(Body { conjuncts: body.value().conjuncts.iter().map(|conjunct| conjunct_in_order(conjunct, slots, ranks)).collect() })
    }

    fn conjunct_in_order(conjunct: &Conjunct, slots: &Slots, ranks: &mut Ranks) -> Conjunct {
        match conjunct {
            Conjunct::Atom(atom) => Conjunct::Atom(in_order(atom, slots, ranks)),
            Conjunct::Not(Negated::Atom(atom)) => Conjunct::Not(Negated::Atom(in_order(atom, slots, ranks))),
            Conjunct::Not(Negated::Form(inner)) => Conjunct::Not(Negated::Form(Arc::new(conjunct_in_order(inner, slots, ranks)))),
            Conjunct::Constraint(_) => conjunct.clone(),
            Conjunct::Or(branches) => Conjunct::Or(branches.iter().map(|branch| body_in_order(branch, slots, ranks)).collect()),
            Conjunct::If { test, then, otherwise } => Conjunct::If {
                test: body_in_order(test, slots, ranks),
                then: body_in_order(then, slots, ranks),
                otherwise: body_in_order(otherwise, slots, ranks),
            },
            Conjunct::All { domain, body } => Conjunct::All { domain: body_in_order(domain, slots, ranks), body: body_in_order(body, slots, ranks) },
        }
    }

    fn key_in_order(key: &KeyBody, slots: &Slots, ranks: &mut Ranks) -> KeyBody {
        KeyBody { body: body_in_order(&key.body, slots, ranks), columns: key.columns.clone() }
    }

    fn input_in_order(input: &Node<InstanceInput>, slots: &Slots, ranks: &mut Ranks) -> Node<InstanceInput> {
        let input = input.value();
        Node::new(InstanceInput { name: input.name.clone(), head: input.head.clone(), body: body_in_order(&input.body, slots, ranks) })
    }

    /// The slot of each of `old`, the columns of a relation, among `new`,
    /// the columns of the relation as the text makes them.
    fn moved(old: &[LabelId], new: &[LabelId]) -> Vec<u32> {
        old.iter().enumerate().map(|(slot, label)| new.iter().position(|own| own == label).unwrap_or(slot) as u32).collect()
    }

    /// The name of the `:Pose` column that each output of a `RIGID_DET` holds.
    const POSE_COLUMN: &str = "Pose";

    struct Names<'n>(&'n [(LabelId, Box<str>)]);

    impl Names<'_> {
        fn get(&self, label: LabelId) -> &str {
            self.0.iter().find(|(id, _)| *id == label).map(|(_, name)| &**name).expect("every label of the form is named")
        }
    }

    /// The written name of each field of `site` that a
    /// [`SiteArg::NamedLabel`] names by a slot, where no binding names the
    /// record's fields: the name of the field's label, with the least digit
    /// suffix that no other field of the site takes. A label at two fields
    /// so names two fields, as `(:n C (:C2 C))`.
    fn own_fields(site: &Site, names: &Names) -> Vec<(ColumnName, ColumnName)> {
        let slotted = |arg: &SiteArg| match arg {
            SiteArg::NamedLabel { name: name @ ColumnName::Slot(_), label: LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id) } => Some((name.clone(), names.get(*id))),
            _ => None,
        };
        let mut taken: Vec<String> = site.value.args.iter().filter_map(|arg| match arg {
            SiteArg::NamedLabel { name: ColumnName::Written(name), .. } => Some(name.to_string()),
            SiteArg::Field(field) => written(&field.column).map(str::to_owned),
            arg => slotted(arg).map(|(_, name)| name.to_owned()),
        }).collect();
        let mut own: Vec<(ColumnName, ColumnName)> = Vec::new();
        for (slot, name) in site.value.args.iter().filter_map(slotted) {
            let text = match own.iter().any(|(_, to)| written(to) == Some(name)) {
                false => name.to_owned(),
                true => {
                    let fresh = (2..).map(|n| format!("{name}{n}")).find(|fresh| !taken.contains(fresh)).expect("a free suffix");
                    taken.push(fresh.clone());
                    fresh
                }
            };
            own.push((slot, ColumnName::Written(text.into())));
        }
        own
    }

    struct Synthesizer<'r> {
        registry: &'r Registry,
        /// The written names of the columns of each relation a form before
        /// the current one declares, by the position of the column.
        columns: StableHashMap<ProgramRelation, Vec<String>>,
        /// Record field names belong to the parameter's binding, not to the
        /// label a later read happens to use for the field's value.
        records: StableHashMap<(ProgramRelation, ColumnName), Vec<(ColumnName, ColumnName)>>,
        /// The slot each column of a relation a form before the current one
        /// declares takes in the text, by the column's slot in the program.
        slots: Slots,
        /// The label names of each scope below the form being written.
        nested: Vec<Scope>,
        /// The places of the labels of each scope below the form being
        /// ordered, by the scope's path below the form.
        nested_ranks: StableHashMap<NodePath, Ranks>,
        /// The slots that each form of a `DEMO_RULE` below the form being
        /// ordered reads in, by the form's path below the form.
        nested_slots: StableHashMap<NodePath, Slots>,
    }

    fn slot_text(slot: u32) -> String {
        format!("&r{slot}")
    }

    fn declared(name: &DeclaredName) -> DeclaredName {
        match name {
            DeclaredName::Written(text) => DeclaredName::Written(text.clone()),
            DeclaredName::Slot(slot) => DeclaredName::Written(slot_text(*slot).into()),
        }
    }

    fn output(name: &OutputName) -> OutputName {
        let of = match &name.of {
            OutputOwner::Instance(InstanceName(owner)) => OutputOwner::Instance(InstanceName(declared(owner))),
            OutputOwner::RigidDet(RigidDetName(owner)) => OutputOwner::RigidDet(RigidDetName(declared(owner))),
        };
        let path = name.path.iter().map(|step| match step {
            OutputStep::Part(part) => OutputStep::Part(declared(part)),
            other => other.clone(),
        });
        OutputName { of, path: path.collect() }
    }

    fn program_relation(relation: &ProgramRelation) -> ProgramRelation {
        match relation {
            ProgramRelation::Declared(RelationName(name)) => ProgramRelation::Declared(RelationName(declared(name))),
            ProgramRelation::Output(name) => ProgramRelation::Output(output(name)),
        }
    }

    fn relation_ref(relation: &RelationRef) -> RelationRef {
        match relation {
            RelationRef::Declared(RelationName(name)) => RelationRef::Declared(RelationName(declared(name))),
            RelationRef::Output(name) => RelationRef::Output(output(name)),
            other => other.clone(),
        }
    }

    /// The relation an atom reads, as a key of the declared columns.
    fn read_relation(relation: &RelationRef) -> Option<ProgramRelation> {
        match relation {
            RelationRef::Declared(name) => Some(ProgramRelation::Declared(name.clone())),
            RelationRef::Output(name) => Some(ProgramRelation::Output(name.clone())),
            RelationRef::Fact(_) | RelationRef::Lib(_) | RelationRef::DefinedPort(_) => None,
        }
    }

    /// `columns`, each named as its label is in the form.
    fn named_columns(columns: &[RelationColumn], names: &Names) -> Arc<[RelationColumn]> {
        columns.iter().map(|column| RelationColumn { name: ColumnName::Written(names.get(column.label).into()), label: column.label }).collect()
    }

    fn written(column: &ColumnName) -> Option<&str> {
        match column {
            ColumnName::Written(text) => Some(text),
            ColumnName::Slot(_) => None,
        }
    }

    impl<'r> Synthesizer<'r> {
        fn new(registry: &'r Registry) -> Self {
            Synthesizer { registry, columns: StableHashMap::default(), records: StableHashMap::default(), slots: Slots::default(), nested: Vec::new(), nested_ranks: StableHashMap::default(), nested_slots: StableHashMap::default() }
        }

        /// The text of `column` of a site on `relation`.
        fn column_text(&self, relation: Option<&RelationRef>, column: &ColumnName) -> String {
            match column {
                ColumnName::Written(text) => text.to_string(),
                ColumnName::Slot(slot) => {
                    let names = relation.and_then(read_relation).and_then(|relation| self.columns.get(&relation));
                    names.and_then(|names| names.get(*slot as usize)).cloned().unwrap_or_else(|| panic!("a column slot {slot} of a relation whose columns no form before declares, or of a record: {relation:?} {:?}", relation.and_then(read_relation).and_then(|r| self.columns.get(&r))))
                }
            }
        }

        /// The name of each label of `form`: the reserved names, then the
        /// other labels in the order of their ids. A label of an `OUT` form
        /// takes the name of the column of its site whatever other label
        /// takes it, since the form writes each such site as `^<column>`.
        fn label_names(&self, form: &Form, ranks: &Ranks) -> Vec<(LabelId, Box<str>)> {
            let mut uses = Uses::default();
            self.form_uses(form, &mut uses);
            if matches!(form, Form::Out(_)) {
                let made = uses.made.iter().filter(|(label, _)| !uses.reserved.iter().any(|(id, _)| id == label));
                let mut names: Vec<(LabelId, Box<str>)> = uses.reserved.iter().cloned().chain(made.map(|(label, column)| (*label, column.as_str().into()))).collect();
                name_unmade(&mut names, &uses.unmade, &[], &[]);
                return names;
            }
            // A column of a relation that a `RIGID_DET` part can read, or an
            // instance column of a `RIGID_DET`, is a column of an output that
            // has a `:Pose` column of its own, and a text names its columns
            // apart.
            let in_output = output_labels(form);
            named_uses(Vec::new(), uses, ranks, &in_output)
        }

        /// `names`, the names of a scope so far, with the names of the labels
        /// of `form`, which the scope holds. The columns of the relations
        /// that the forms before `form` declare are known.
        fn form_names(&self, names: Vec<(LabelId, Box<str>)>, form: &Form, ranks: Option<&Ranks>) -> Vec<(LabelId, Box<str>)> {
            let mut uses = Uses::default();
            self.form_uses(form, &mut uses);
            named_uses(names, uses, ranks.unwrap_or(&Ranks::default()), &output_labels(form))
        }

        /// `demonstrated`, a `DEMONSTRATED` form, in the order its labels and
        /// sites take in the text. The places of the labels of its key and
        /// inputs are in `ranks`, and those of each rule's scope in
        /// `nested_ranks`.
        fn demonstrated_in_slot_order(&mut self, demonstrated: &Demonstrated, ranks: &mut Ranks) -> Demonstrated {
            let slots = &self.slots;
            let key = demonstrated.key.as_ref().map(|key| {
                let key = key.value();
                Node::new(KeyClause { key: key_in_order(&key.key, slots, ranks), inputs: key.inputs.iter().map(|input| input_in_order(input, slots, ranks)).collect() })
            });
            let inputs = demonstrated.inputs.iter().map(|input| input_in_order(input, slots, ranks)).collect();
            let root = NodePath::default();
            let children = super::arclog::ChildPaths::of(&root, NodeRef::Demonstrated(demonstrated));
            let mut rules = Vec::new();
            for rule in demonstrated.rules.iter() {
                let rule = rule.value();
                let at = children.path(NodeRef::DemoRule(rule));
                let forms_at = super::arclog::ChildPaths::of(&at, NodeRef::DemoRule(rule));
                let mut rule_ranks = Ranks::default();
                let mut forms = Vec::new();
                for (index, form) in rule.forms.iter().enumerate() {
                    let alt = rule.forms.from_alt(index);
                    let form_at = forms_at.path(NodeRef::from(form));
                    self.nested_slots.insert(form_at.clone(), self.slots.clone());
                    let (ordered, own) = self.in_slot_order(form);
                    if alt {
                        self.nested_ranks.insert(form_at, own);
                    } else {
                        rule_ranks.extend(own);
                    }
                    forms.push((ordered, alt));
                }
                self.nested_ranks.insert(at, rule_ranks);
                rules.push(Node::new(DemoRule { forms: forms.into_iter().collect(), ..rule.clone() }));
            }
            Demonstrated { key, inputs, rules: rules.into(), ..demonstrated.clone() }
        }

        /// The labels of `form` that are columns of an output with a `:Pose`
        /// column of its own.


        /// `form` with the sites of each read of a derived relation in the
        /// order `read_order` gives, and the place of each label the change
        /// moves. The slots that the form's own relation takes in the text
        /// follow from the order of its labels, and the reads of a later
        /// form take them.
        fn in_slot_order(&mut self, form: &Form) -> (Form, Ranks) {
            let mut ranks = Ranks::default();
            if let Form::Demonstrated(demonstrated) = form {
                let ordered = self.demonstrated_in_slot_order(demonstrated.value(), &mut ranks);
                return (Form::Demonstrated(Node::new(ordered)), ranks);
            }
            let slots = &self.slots;
            let (form, declared) = match form {
                Form::Clause(clause) => {
                    let clause = clause.value();
                    let body = body_in_order(&clause.body, slots, &mut ranks);
                    let declared = match &clause.derives {
                        ProgramRelation::Declared(name) => {
                            let old: Vec<LabelId> = clause.columns.iter().map(|column| column.label).collect();
                            Some((name.clone(), moved(&old, &crate::read::columns::made_labels(body.value()))))
                        }
                        ProgramRelation::Output(_) => None,
                    };
                    (Form::Clause(Node::new(Clause { body, ..clause.clone() })), declared)
                }
                Form::Instance(instance) => {
                    let instance = instance.value();
                    let key = instance.key.as_ref().map(|key| {
                        let key = key.value();
                        Node::new(KeyClause {
                            key: key_in_order(&key.key, slots, &mut ranks),
                            inputs: key.inputs.iter().map(|input| input_in_order(input, slots, &mut ranks)).collect(),
                        })
                    });
                    let inputs = instance.inputs.iter().map(|input| input_in_order(input, slots, &mut ranks)).collect();
                    (Form::Instance(Node::new(Instance { key, inputs, ..instance.clone() })), None)
                }
                Form::Choose(choose) => {
                    let choose = choose.value();
                    let rows = choose.rows.as_ref().map(|rows| key_in_order(rows, slots, &mut ranks));
                    let from = body_in_order(&choose.from, slots, &mut ranks);
                    let never = choose.never.iter().map(|never| body_in_order(never, slots, &mut ranks)).collect();
                    let old: Vec<LabelId> = choose.rows.iter().flat_map(|rows| rows.columns.iter()).chain(choose.candidate_columns.iter()).map(|column| column.label).collect();
                    let mut new = rows.as_ref().map_or_else(Vec::new, |rows| crate::read::columns::key_labels(rows.body.value()));
                    new.extend(crate::read::columns::made_labels(from.value()));
                    let declared = Some((choose.name.clone(), moved(&old, &new)));
                    (Form::Choose(Node::new(Choose { rows, from, never, ..choose.clone() })), declared)
                }
                Form::RigidDet(rigid) => {
                    let rigid = rigid.value();
                    let key = rigid.key.as_ref().map(|key| key_in_order(key, slots, &mut ranks));
                    let instance = rigid.instance.as_ref().map(|instance| key_in_order(instance, slots, &mut ranks));
                    (Form::RigidDet(Node::new(RigidDet { key, instance, ..rigid.clone() })), None)
                }
                Form::Out(out) => (Form::Out(Node::new(Out { key: key_in_order(&out.value().key, slots, &mut ranks) })), None),
                other => (other.clone(), None),
            };
            if let Some((name, new)) = declared {
                self.slots.insert(name, new);
            }
            (form, ranks)
        }

        fn form_uses(&self, form: &Form, uses: &mut Uses) {
            column_labels(form, &mut uses.unmade);
            match form {
                // The key and the inputs; each rule is a scope of its own.
                Form::Demonstrated(demonstrated) => {
                    let demonstrated = demonstrated.value();
                    if let Some(key) = &demonstrated.key {
                        self.body_uses(key.value().key.body.value(), uses);
                        key.value().inputs.iter().for_each(|input| self.input_uses(input.value(), uses));
                    }
                    demonstrated.inputs.iter().for_each(|input| self.input_uses(input.value(), uses));
                }
                Form::Clause(clause) => self.body_uses(clause.value().body.value(), uses),
                Form::Instance(instance) => {
                    let instance = instance.value();
                    if let Some(key) = &instance.key {
                        self.body_uses(key.value().key.body.value(), uses);
                        key.value().inputs.iter().for_each(|input| self.input_uses(input.value(), uses));
                    }
                    instance.inputs.iter().for_each(|input| self.input_uses(input.value(), uses));
                }
                Form::Choose(choose) => {
                    let choose = choose.value();
                    choose.rows.iter().for_each(|rows| self.body_uses(rows.body.value(), uses));
                    self.body_uses(choose.from.value(), uses);
                    choose.never.iter().for_each(|never| self.body_uses(never.value(), uses));
                }
                Form::RigidDet(rigid) => {
                    let rigid = rigid.value();
                    rigid.key.iter().chain(rigid.instance.iter()).for_each(|clause| self.body_uses(clause.body.value(), uses));
                    for part in rigid.parts.iter() {
                        let part = part.value();
                        part.sites.iter().for_each(|site| self.site_uses(Some(&part.relation), site, uses));
                    }
                }
                Form::Out(out) => self.body_uses(out.value().key.body.value(), uses),
                _ => panic!("write_synthesized writes the forms a decode builds: RULE, DET, INIT, CHOOSE, RIGID_DET and OUT"),
            }
        }

        /// The uses of an input: its body, then its head.
        fn input_uses(&self, input: &InstanceInput, uses: &mut Uses) {
            self.body_uses(input.body.value(), uses);
            input.head.iter().for_each(|site| self.site_uses(None, site, uses));
            // A `DEMONSTRATED` form names the columns of its clauses by the labels at its heads.
            for site in input.head.iter() {
                crate::types::each_site_label(site, &mut Vec::new(), &mut |use_, _| uses.unmade.extend(crate::types::use_label(use_).map(|label| (label, COLUMN_BASE.to_owned()))));
            }
        }

        fn body_uses(&self, body: &Body, uses: &mut Uses) {
            body.conjuncts.iter().for_each(|conjunct| self.conjunct_uses(conjunct, uses));
        }

        fn conjunct_uses(&self, conjunct: &Conjunct, uses: &mut Uses) {
            match conjunct {
                Conjunct::Atom(atom) | Conjunct::Not(Negated::Atom(atom)) => atom.value().sites.iter().for_each(|site| self.site_uses(Some(&atom.value().relation), site, uses)),
                Conjunct::Not(Negated::Form(inner)) => self.conjunct_uses(inner, uses),
                Conjunct::Constraint(constraint) => {
                    for operand in [Some(constraint.first), constraint_second(constraint)].into_iter().flatten() {
                        if operand.fresh {
                            uses.made.push((operand.label, "V".to_owned()));
                        }
                    }
                }
                Conjunct::Or(branches) => branches.iter().for_each(|branch| self.body_uses(branch.value(), uses)),
                Conjunct::If { test, then, otherwise } => [test, then, otherwise].into_iter().for_each(|body| self.body_uses(body.value(), uses)),
                Conjunct::All { domain, body } => [domain, body].into_iter().for_each(|body| self.body_uses(body.value(), uses)),
            }
        }

        fn site_uses(&self, relation: Option<&RelationRef>, site: &Site, uses: &mut Uses) {
            let column = self.column_text(relation, &site.column);
            for arg in site.value.args.iter() {
                match arg {
                    SiteArg::Label(LabelUse::Fresh(id) | LabelUse::Key(id)) => uses.made.push((*id, column.clone())),
                    SiteArg::Label(LabelUse::Join(_) | LabelUse::Zero) => {}
                    SiteArg::NamedLabel { name, label: label @ (LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id)) } => {
                        // The writer asks the name of this label whichever scope makes it.
                        uses.unmade.push((*id, column.clone()));
                        match written(name) {
                            // A label at a second field, or at a field whose name
                            // another label holds, takes a name of its own, and the
                            // site names the field.
                            Some(name) if uses.reserved.iter().any(|(own, held)| own == id || &**held == name) => {
                                if !matches!(label, LabelUse::Join(_)) {
                                    uses.made.push((*id, name.to_owned()));
                                }
                            }
                            Some(name) => uses.reserved.push((*id, name.into())),
                            None if matches!(label, LabelUse::Join(_)) => {}
                            None => uses.made.push((*id, column.clone())),
                        }
                    }
                    SiteArg::NamedLabel { label: LabelUse::Zero, .. } => {}
                    SiteArg::Field(field) => {
                        let mut field = field.clone();
                        if let Some(to) = self.record_field(relation, &site.column, &field.column) {
                            field.column = to.clone();
                        }
                        self.site_uses(None, &field, uses);
                    },
                }
            }
        }

        fn form(&mut self, form: &Form, names: &Names) -> Form {
            match form {
                Form::Clause(clause) => Form::Clause(Node::new(self.clause(clause.value(), names))),
                Form::Instance(instance) => Form::Instance(Node::new(self.instance(instance.value(), names))),
                Form::Choose(choose) => Form::Choose(Node::new(self.choose(choose.value(), names))),
                Form::RigidDet(rigid) => Form::RigidDet(Node::new(self.rigid_det(rigid.value(), names))),
                Form::Out(out) => Form::Out(Node::new(Out { key: self.key_body(&out.value().key, names) })),
                Form::Demonstrated(demonstrated) => Form::Demonstrated(Node::new(self.demonstrated(demonstrated.value(), names))),
                _ => panic!("write_synthesized writes the forms a decode builds: RULE, DET, INIT, CHOOSE, RIGID_DET, OUT and DEMONSTRATED"),
            }
        }

        /// `demonstrated` as written, its key and inputs with `names`, and
        /// each rule, and each form an `ALT` gave a rule, with the names of
        /// its own scope, which go to `nested`. A label of a `&prediction`
        /// clause that fills a column takes the name of the key's or the
        /// `value` head's label at that column, since the text names the
        /// clause's columns by its labels.
        fn demonstrated(&mut self, demonstrated: &Demonstrated, names: &Names) -> Demonstrated {
            let ports = crate::stream::demonstrated::ports();
            let no_fields = StableHashMap::default();
            let key = demonstrated.key.as_ref().map(|key| {
                let value = key.value();
                let inputs = value.inputs.iter().map(|input| Node::new(self.input(input.value(), names, ports, &no_fields))).collect();
                Node::new(KeyClause { key: self.key_body(&value.key, names), inputs })
            });
            let inputs = demonstrated.inputs.iter().map(|input| Node::new(self.input(input.value(), names, ports, &no_fields))).collect();
            let relation = ProgramRelation::Declared(demonstrated.name.clone());
            if let (Some(old), Some(new)) = (&demonstrated.key, &key) {
                let fields = old.value().key.columns.iter().zip(new.value().key.columns.iter()).map(|(old, new)| (old.name.clone(), new.name.clone())).collect();
                self.records.insert((relation.clone(), crate::resolver::columns::key()), fields);
            }
            let head = Demonstrated { name: RelationName(declared(&demonstrated.name.0)), key, inputs, rules: Arc::from([]) };
            let columns = crate::resolver::form_columns::demonstrated_columns(&head).names().map(|column| written(column).unwrap_or_default().to_owned()).collect();
            self.columns.insert(relation, columns);
            // The column each target of a `&prediction` clause names, and the
            // label of the key or the `value` head at that column.
            let targets: Vec<ColumnName> = crate::stream::demonstrated::prediction_targets(demonstrated)
                .into_iter()
                .enumerate()
                .map(|(at, name)| name.unwrap_or(ColumnName::Slot(u32::MAX - at as u32)))
                .collect();
            let mut target_labels: Vec<LabelId> = demonstrated.key.iter().flat_map(|key| key.value().key.columns.iter().map(|column| column.label)).collect();
            if let Some(value) = crate::resolver::form_columns::demonstrated_value(demonstrated) {
                for site in value.head.iter() {
                    crate::types::each_site_label(site, &mut Vec::new(), &mut |use_, _| target_labels.extend(crate::types::use_label(use_)));
                }
            }
            let reserved = |forms: &[&Form]| -> Vec<(LabelId, Box<str>)> {
                let mut reserved = Vec::new();
                for form in forms {
                    let Form::Clause(clause) = form else { continue };
                    let clause = clause.value();
                    if crate::program::canonical::relation_of(&clause.derives) != crate::program::canonical::prediction() {
                        continue;
                    }
                    for column in clause.columns.iter() {
                        let Some(at) = targets.iter().position(|target| *target == column.name) else { continue };
                        // A field of a record of the `value` head is named by
                        // the field, and any other column by its label.
                        let name: Option<Box<str>> = match &targets[at] {
                            ColumnName::Written(field) => Some(field.clone()),
                            ColumnName::Slot(_) => target_labels.get(at).map(|label| names.get(*label).into()),
                        };
                        reserved.extend(name.map(|name| (column.label, name)));
                    }
                }
                reserved
            };
            let root = NodePath::default();
            let children = super::arclog::ChildPaths::of(&root, NodeRef::Demonstrated(demonstrated));
            let mut rules = Vec::new();
            for rule in demonstrated.rules.iter() {
                let rule = rule.value();
                let at = children.path(NodeRef::DemoRule(rule));
                let forms_at = super::arclog::ChildPaths::of(&at, NodeRef::DemoRule(rule));
                let own: Vec<&Form> = rule.forms.iter().enumerate().filter(|(index, _)| !rule.forms.from_alt(*index)).map(|(_, form)| form).collect();
                let rule_ranks = self.nested_ranks.get(&at).cloned();
                let fields = Uses { reserved: reserved(&own), made: rule.fields.iter().map(|field| (field.label, FIELD_BASE.to_owned())).collect(), unmade: Vec::new() };
                // Each form is named after the forms before it are written,
                // whose relations its reads name.
                let mut rule_names = named_uses(Vec::new(), fields, rule_ranks.as_ref().unwrap_or(&Ranks::default()), &[]);
                let mut forms = Vec::new();
                for (index, form) in rule.forms.iter().enumerate() {
                    let alt = rule.forms.from_alt(index);
                    let written_form = if alt {
                        let form_at = forms_at.path(NodeRef::from(form));
                        let alt_ranks = self.nested_ranks.get(&form_at).cloned();
                        let alt_names = self.form_names(reserved(&[form]), form, alt_ranks.as_ref());
                        let written_form = self.form(form, &Names(&alt_names));
                        self.nested.push((form_at, alt_names));
                        written_form
                    } else {
                        rule_names = self.form_names(rule_names, form, rule_ranks.as_ref());
                        self.form(form, &Names(&rule_names))
                    };
                    forms.push((written_form, alt));
                }
                self.nested.push((at, rule_names));
                rules.push(Node::new(DemoRule { forms: forms.into_iter().collect(), ..rule.clone() }));
            }
            Demonstrated { rules: rules.into(), ..head }
        }

        fn clause(&mut self, clause: &Clause, names: &Names) -> Clause {
            let columns = named_columns(&clause.columns, names);
            let derived: Vec<String> = match (columns.is_empty(), clause.proposers.first()) {
                (true, Some(proposer)) => proposer_columns(self.registry, proposer).map_or_else(Vec::new, |columns| columns.iter().filter_map(|column| written(column).map(str::to_owned)).collect()),
                _ => columns.iter().filter_map(|column| written(&column.name).map(str::to_owned)).collect(),
            };
            self.columns.insert(clause.derives.clone(), derived);
            Clause { derives: program_relation(&clause.derives), body: self.body(&clause.body, names), columns, ..clause.clone() }
        }

        fn instance(&mut self, instance: &Instance, names: &Names) -> Instance {
            let component_ports =
                component(self.registry, &instance.component).expect("the lib names the component");
            let mut fields: StableHashMap<TypeParameter, Vec<(ColumnName, ColumnName)>> =
                StableHashMap::default();
            for sites in binding_sites(instance, &component_ports.inputs) {
                let names_of_fields = match sites.binding {
                    ParameterSite::Key(key) => key
                        .key
                        .columns
                        .iter()
                        .map(|column| {
                            (
                                column.name.clone(),
                                ColumnName::Written(names.get(column.label).into()),
                            )
                        })
                        .collect(),
                    ParameterSite::Head { site, .. } => {
                        let old = projection(site);
                        let written = self.site(None, site, names);
                        old.zip(projection(&written))
                            .map(|(old, new)| {
                                old.iter().cloned().zip(new.iter().cloned()).collect()
                            })
                            .unwrap_or_default()
                    }
                };
                fields.insert(sites.parameter.clone(), names_of_fields);
            }
            let written_inputs: Vec<_> = component_ports
                .inputs
                .iter()
                .map(|input| &input.port.name)
                .collect();
            for port in component_ports.relation_ports(&written_inputs) {
                let name = OutputName {
                    of: OutputOwner::Instance(instance.name.clone()),
                    path: Arc::from([OutputStep::Port(port.name.clone())]),
                };
                let relation = ProgramRelation::Output(name);
                for column in port.columns.iter() {
                    if let ColumnType::Parameter(parameter) = &column.ty {
                        if let Some(fields) = fields.get(parameter) {
                            self.records
                                .insert((relation.clone(), column.name.clone()), fields.clone());
                        }
                    }
                }
                self.columns.insert(
                    relation,
                    port.columns
                        .iter()
                        .filter_map(|column| written(&column.name).map(str::to_owned))
                        .collect(),
                );
            }
            let key = instance.key.as_ref().map(|key| {
                let value = key.value();
                let inputs = value
                    .inputs
                    .iter()
                    .map(|input| {
                        Node::new(self.input(input.value(), names, component_ports, &fields))
                    })
                    .collect();
                Node::new(KeyClause {
                    key: self.key_body(&value.key, names),
                    inputs,
                })
            });
            let inputs = instance
                .inputs
                .iter()
                .map(|input| Node::new(self.input(input.value(), names, component_ports, &fields)))
                .collect();
            Instance {
                name: InstanceName(declared(&instance.name.0)),
                component: instance.component.clone(),
                key,
                inputs,
            }
        }

        fn choose(&mut self, choose: &Choose, names: &Names) -> Choose {
            let rows = choose.rows.as_ref().map(|rows| self.key_body(rows, names));
            let candidate_columns = named_columns(&choose.candidate_columns, names);
            let row_columns = rows.iter().flat_map(|rows| rows.columns.iter());
            let written_columns = row_columns.chain(candidate_columns.iter()).filter_map(|column| written(&column.name).map(str::to_owned)).collect();
            self.columns.insert(ProgramRelation::Declared(choose.name.clone()), written_columns);
            let never = choose.never.iter().map(|never| self.body(never, names)).collect();
            Choose { name: RelationName(declared(&choose.name.0)), rows, candidate_columns, from: self.body(&choose.from, names), from_inside_for: choose.from_inside_for, never }
        }

        fn rigid_det(&mut self, rigid: &RigidDet, names: &Names) -> RigidDet {
            let name = RigidDetName(declared(&rigid.name.0));
            let key = rigid.key.as_ref().map(|key| self.key_body(key, names));
            let instance = rigid.instance.as_ref().map(|instance| self.key_body(instance, names));
            let parts = rigid.parts.iter().map(|part| self.atom(part, names)).collect();
            let value = RigidDet { name, key, instance, parts };
            // The outputs of `rigid` hold the paths as the later sites name
            // them, and those of `value` the columns as written. A later site
            // names an output column by the slot that the decoder named it
            // with, which is not its position.
            for ((path, columns), (_, written_columns)) in rigid_outputs(rigid).into_iter().zip(rigid_outputs(&value)) {
                let output = OutputName { of: OutputOwner::RigidDet(rigid.name.clone()), path };
                if let (Some(old), Some(new)) = (&rigid.key, &value.key) {
                    let fields = old.columns.iter().zip(new.columns.iter())
                        .map(|(old,new)|(old.name.clone(),new.name.clone())).collect();
                    self.records.insert((ProgramRelation::Output(output.clone()), crate::resolver::columns::key()), fields);
                }
                let mut texts: Vec<String> = Vec::new();
                for (column, text) in columns.names().zip(written_columns.names()) {
                    let ColumnName::Slot(slot) = column else { continue };
                    texts.resize(texts.len().max(*slot as usize + 1), String::new());
                    texts[*slot as usize] = written(text).map(str::to_owned).unwrap_or_default();
                }
                self.columns.insert(ProgramRelation::Output(output), texts);
            }
            value
        }

        fn key_body(&self, key: &KeyBody, names: &Names) -> KeyBody {
            KeyBody { body: self.body(&key.body, names), columns: named_columns(&key.columns, names) }
        }

        fn input(
            &self,
            input: &InstanceInput,
            names: &Names,
            component: &crate::registry::Component,
            fields: &StableHashMap<TypeParameter, Vec<(ColumnName, ColumnName)>>,
        ) -> InstanceInput {
            let head = input
                .head
                .iter()
                .map(|site| {
                    let parameter = component
                        .inputs
                        .iter()
                        .find(|port| port.port.name == input.name)
                        .and_then(|port| port.port.columns.iter().find(|c| c.name == site.column))
                        .and_then(|c| match &c.ty {
                            ColumnType::Parameter(p) => fields.get(p),
                            _ => None,
                        });
                    self.site_with_fields(None, site, names, parameter.map(Vec::as_slice))
                })
                .collect();
            InstanceInput {
                name: input.name.clone(),
                head,
                body: self.body(&input.body, names),
            }
        }

        fn body(&self, body: &Node<Body>, names: &Names) -> Node<Body> {
            Node::new(Body { conjuncts: body.value().conjuncts.iter().map(|conjunct| self.conjunct(conjunct, names)).collect() })
        }

        fn conjunct(&self, conjunct: &Conjunct, names: &Names) -> Conjunct {
            let bodies = |bodies: &[Node<Body>]| -> Arc<[Node<Body>]> { bodies.iter().map(|body| self.body(body, names)).collect() };
            match conjunct {
                Conjunct::Atom(atom) => Conjunct::Atom(self.atom(atom, names)),
                Conjunct::Not(Negated::Atom(atom)) => Conjunct::Not(Negated::Atom(self.atom(atom, names))),
                Conjunct::Not(Negated::Form(inner)) => Conjunct::Not(Negated::Form(Arc::new(self.conjunct(inner, names)))),
                Conjunct::Constraint(constraint) => Conjunct::Constraint(*constraint),
                Conjunct::Or(branches) => Conjunct::Or(bodies(branches)),
                Conjunct::If { test, then, otherwise } => Conjunct::If { test: self.body(test, names), then: self.body(then, names), otherwise: self.body(otherwise, names) },
                Conjunct::All { domain, body } => Conjunct::All { domain: self.body(domain, names), body: self.body(body, names) },
            }
        }

        fn atom(&self, atom: &Node<Atom>, names: &Names) -> Node<Atom> {
            let atom = atom.value();
            Node::new(Atom { relation: relation_ref(&atom.relation), sites: atom.sites.iter().map(|site| self.site(Some(&atom.relation), site, names)).collect() })
        }

        fn site(&self, relation: Option<&RelationRef>, site: &Site, names: &Names) -> Site {
            let fields = relation
                .and_then(read_relation)
                .and_then(|r| self.records.get(&(r, site.column.clone())));
            self.site_with_fields(relation, site, names, fields.map(Vec::as_slice))
        }

        fn record_field(&self, relation: Option<&RelationRef>, column: &ColumnName, field: &ColumnName) -> Option<&ColumnName> {
            let fields = self.records.get(&(relation.and_then(read_relation)?, column.clone()))?;
            fields.iter().find(|(from,_)| from == field).map(|(_,to)|to)
        }

        fn site_with_fields(
            &self,
            relation: Option<&RelationRef>,
            site: &Site,
            names: &Names,
            fields: Option<&[(ColumnName, ColumnName)]>,
        ) -> Site {
            let own = own_fields(site, names);
            let args = site.value.args.iter().map(|arg| match arg {
                SiteArg::NamedLabel { name, label: LabelUse::Zero } => {
                    let field = fields.and_then(|fields| fields.iter().find(|(from,_)|from == name)).map(|(_,to)|to.clone())
                        .or_else(|| matches!(name, ColumnName::Written(_)).then(||name.clone()))
                        .expect("a zero at a record field has the binding's field name");
                    SiteArg::Field(Site { column: field, value: SiteValue { args: Arc::from([SiteArg::Label(LabelUse::Zero)]) } })
                },
                SiteArg::NamedLabel {
                    name: old @ ColumnName::Slot(_),
                    label: label @ (LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id)),
                } => {
                    let field = fields
                        .and_then(|fields| fields.iter().find(|(from, _)| from == old))
                        .map(|(_, to)| to.clone())
                        .or_else(|| own.iter().find(|(from, _)| from == old).map(|(_, to)| to.clone()))
                        .unwrap_or_else(|| ColumnName::Written(names.get(*id).into()));
                    if written(&field) == Some(names.get(*id)) {
                        SiteArg::NamedLabel {
                            name: field,
                            label: *label,
                        }
                    } else {
                        SiteArg::Field(Site {
                            column: field,
                            value: SiteValue {
                                args: Arc::from([SiteArg::Label(*label)]),
                            },
                        })
                    }
                }
                SiteArg::Field(field) => {
                    let mut field = field.clone();
                    if let Some(to) = fields.and_then(|fields|fields.iter().find(|(from,_)|from == &field.column)).map(|(_,to)|to) {
                        field.column = to.clone();
                    }
                    SiteArg::Field(self.site_with_fields(None, &field, names, None))
                },
                // A field of a record whose label has another name.
                SiteArg::NamedLabel { name: field @ ColumnName::Written(text), label: label @ (LabelUse::Fresh(id) | LabelUse::Join(id) | LabelUse::Key(id)) }
                    if site.value.args.len() > 1 && **text != *names.get(*id) =>
                {
                    SiteArg::Field(Site { column: field.clone(), value: SiteValue { args: Arc::from([SiteArg::Label(*label)]) } })
                }
                other => other.clone(),
            });
            Site {
                column: ColumnName::Written(self.column_text(relation, &site.column).into()),
                value: SiteValue {
                    args: args.collect(),
                },
            }
        }
    }

    /// The base of the name of a field of a `DEMO_RULE` form.
    const FIELD_BASE: &str = "F";

    /// The labels of `form` that are columns of an output with a `:Pose`
    /// column of its own, which a text names apart from `Pose`.
    fn output_labels(form: &Form) -> Vec<LabelId> {
        match form {
            Form::Clause(clause) => clause.value().columns.iter().map(|column| column.label).collect(),
            Form::Choose(choose) => {
                let choose = choose.value();
                choose.rows.iter().flat_map(|rows| rows.columns.iter()).chain(choose.candidate_columns.iter()).map(|column| column.label).collect()
            }
            Form::RigidDet(rigid) => rigid.value().instance.iter().flat_map(|instance| instance.columns.iter()).map(|column| column.label).collect(),
            _ => Vec::new(),
        }
    }

    /// `names` with the name of each label of `uses` that it lacks: the
    /// reserved names, then the other labels in the order of their places in
    /// `ranks`, or of their ids.
    fn named_uses(mut names: Vec<(LabelId, Box<str>)>, mut uses: Uses, ranks: &Ranks, in_output: &[LabelId]) -> Vec<(LabelId, Box<str>)> {
        let reserved: Vec<&str> = uses.reserved.iter().map(|(_, name)| &**name).collect();
        names.extend(uses.reserved.iter().filter(|(id, _)| !names.iter().any(|(own, _)| own == id)).cloned().collect::<Vec<_>>());
        names.dedup_by_key(|(id, _)| *id);
        uses.made.sort_by_key(|(label, _)| ranks.get(label).copied().unwrap_or(label.0));
        for (label, base) in &uses.made {
            if names.iter().any(|(id, _)| id == label) {
                continue;
            }
            let apart = in_output.contains(label);
            let taken = |name: &str| names.iter().any(|(_, held)| &**held == name) || reserved.contains(&name) || (apart && name == POSE_COLUMN);
            names.push((*label, label_name(base, taken).into()));
        }
        name_unmade(&mut names, &uses.unmade, &reserved, in_output);
        names
    }

    /// Adds to `names` a name for each label of `unmade` that it lacks, after
    /// the names of the labels that sites make, so that those keep their names.
    fn name_unmade(names: &mut Vec<(LabelId, Box<str>)>, unmade: &[(LabelId, String)], reserved: &[&str], in_output: &[LabelId]) {
        for (label, base) in unmade {
            if names.iter().any(|(id, _)| id == label) {
                continue;
            }
            let apart = in_output.contains(label);
            let taken = |name: &str| names.iter().any(|(_, held)| &**held == name) || reserved.contains(&name) || (apart && name == POSE_COLUMN);
            let name = label_name(base, taken);
            names.push((*label, name.into()));
        }
    }

    /// The labels at the columns of the relations that `form` declares, which
    /// the writer names whether or not a site of the form makes them: a label
    /// that a site of a part of a body leaves to another part, as the body of
    /// a prefix does, still names its column.
    fn column_labels(form: &Form, out: &mut Vec<(LabelId, String)>) {
        let columns = |columns: &[RelationColumn], out: &mut Vec<(LabelId, String)>| out.extend(columns.iter().map(|column| (column.label, COLUMN_BASE.to_owned())));
        match form {
            Form::Clause(clause) => columns(&clause.value().columns, out),
            Form::Instance(instance) => {
                if let Some(key) = &instance.value().key {
                    columns(&key.value().key.columns, out);
                }
            }
            Form::Choose(choose) => {
                let choose = choose.value();
                if let Some(rows) = &choose.rows {
                    columns(&rows.columns, out);
                }
                columns(&choose.candidate_columns, out);
            }
            Form::RigidDet(rigid) => {
                let rigid = rigid.value();
                for key in rigid.key.iter().chain(rigid.instance.iter()) {
                    columns(&key.columns, out);
                }
            }
            Form::Out(out_form) => columns(&out_form.value().key.columns, out),
            Form::Demonstrated(demonstrated) => {
                if let Some(key) = &demonstrated.value().key {
                    columns(&key.value().key.columns, out);
                }
            }
            _ => {}
        }
    }

    /// The base of the name of a label that no site of its form makes.
    const COLUMN_BASE: &str = "V";

    /// The labels of one form, collected in any order.
    #[derive(Default)]
    struct Uses {
        /// The labels a `NamedLabel` names, with the names, which no other
        /// label of the scope takes.
        reserved: Vec<(LabelId, Box<str>)>,
        /// Each label with the column of the site that makes it.
        made: Vec<(LabelId, String)>,
        /// The labels the writer asks a name of that a site of the form may
        /// not make: the labels at columns and at fields, with a base for the
        /// name of each. They are named after the labels that sites make.
        unmade: Vec<(LabelId, String)>,
    }
}
