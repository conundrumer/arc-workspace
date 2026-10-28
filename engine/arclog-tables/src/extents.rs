//! The extents of the made frames of a table's `Box` columns, per row.
//!
//! A `Box` value in a made frame covers a box of the frame, and its margins
//! alone do not say which: the frame's extent (V rows, H columns) does. The
//! engine keeps no extent, since a Box term is its four margins, so the extent
//! is computed here, from a second evaluation of the bodies that give the
//! table's rows, with the label of each of their columns kept
//! ([`arclog::eval::body_view::BodyView::widened`]).
//!
//! The extent of a frame follows from the own size of a value, the size of the
//! box it covers, which no move within frames changes: a Box `v` in a frame of
//! extent (V, H) has own size (V - top - bottom, H - left - right), and a
//! Position has own size (1, 1). The extent of the frame of `v` is its own
//! size plus (top + bottom, left + right).
//!
//! In a widened body, the extent of the frame of the value of a label is:
//!
//! - for a label of type `Position`, the one its value gives: (top + bottom +
//!   1, left + right + 1);
//! - for a label of type `Box`, the one of each source of the label in the
//!   body, as [`column_flows`] gives the sources and their frames, and `None`
//!   where two differ or one has none:
//!   - the frame of the input or output grid: the extent of the example's
//!     grid;
//!   - a frame that a lib column makes, `Made`: the own size of the label at
//!     the `size` column of the maker's atom ([`Registry::frame_size`]), with
//!     its rows and columns swapped where the D4 element that the label at
//!     the `by` column holds moves the top edge to the left or the right edge,
//!     plus the margins of the label at the maker's column;
//!   - the frame of the column the source reads, `Read`: the extent of the
//!     frame of that column in the latest earlier table of the relation read,
//!     at the rows of that table whose cells equal the labels of the atom's
//!     sites in the row, at the example and the assignment of the `DET`s of the
//!     row's evaluation: the grid's extent where the frame is the input's or
//!     the output's, the value's where the column is a `Position`, and the
//!     table's own extent where the column is one of its [`Extents::columns`].
//!     The example is the row's, or, where the atom reads its relation lifted
//!     over the examples, the one that the cell of the atom's Example label
//!     holds.
//!
//! The rows of an input of an instance come from the clauses that the instance
//! writes for it, widened in the same way ([`arclog::eval::body_view::BodyView::at`]),
//! and the rows of an output of an instance take the extent of the frame its
//! rule names (or of the input column it copies) over the rows of the input
//! with the row's key, or with any key where the output or the input has none.
//! The rows of a widened body are those of its relation at each model of each
//! assignment (`relation_examples` of the `tables` module), all of which give the
//! entry's rows.
//!
//! A row of a table takes the one extent that the rows of the widened bodies
//! that give it give ([`Merged`]), and none where they give two or where one
//! of them gives none.
//!
//! Every extent is at least 1 in each cell. A value whose margins reach past
//! its frame (a negative margin, in `programs/lib/box.dl`) can make a frame's
//! own size plus margins fall below 1: such a derivation gives no extent, and
//! so does a value that does not fit in its extent (`fitted_size`).
//!
//! The derivation visits no more rows than the table's work cap admits. Each
//! model of a body or of an output charges its count of rows to the count of
//! [`TableWork`] before the derivation visits them, as does each read of an
//! earlier table's rows. An entry whose model is refused the charge, or whose
//! derivation leaves the count past the cap, gets the stop
//! ([`EntryExtents::Stopped`]) in place of extents.
//!
//! An entry that holds rows and has no extent says why in
//! [`EntryExtents::Lost`]: the fault of a widened body, or the reason the
//! extents do not derive its rows.
//!
//! The extents of a table stand beside its rows in [`Contents`], for each
//! example, assignment and model, as [`Extents::entry`] gives them.

use std::cell::RefCell;
use std::ops::Range;
use std::rc::Rc;

use arclog::algebra::geometry::{Edge, Geometry};
use arclog::check::CheckedProgram;
use arclog::decode::{relation_dets, Decoder};
use arclog::eval::body_view::BodyView;
use arclog::eval::ir::{Argument, Arguments, IrNode, IrPaths, NodePaths};
use arclog::eval::determinations::relation_spelled;
use arclog::eval::join::each_row;
use arclog::eval::{RelationValue, Stop, TableWork};
use arclog::hash::StableHashMap;
use arclog::judge::determination::Assignment;
use arclog::program::path::{node_at, NodePath, NodeRef};
use arclog::program::{Atom, ColumnName, Conjunct, Instance, LabelId, PortName, Site};
use arclog::registry::Registry;
use arclog::relations::Relation;
use arclog::resolver::given::Given;
use arclog::resolver::registry_columns;
use arclog::resolver::{DependencyKind, Resolution};
use arclog::terms::{Constant, Example, Margins, Term, TermId};
use arclog::types::{use_label, GraphRelation, ValueType};

use crate::columns::{extent_columns, fault_spelled, locate, names_of, read_index, Named, TableNames, INPUT_FRAME, OUTPUT_FRAME};
use crate::flows::{body_column_flows, column_placements, output_copies, output_frames, ColumnSource, Maker, OutputFrame, Placement, SourceFrame};
use crate::tables::{relation_examples, Contents, ExampleRows, Table, EVIDENCE_FACTS};

/// The extent of a frame: its count of rows V and its count of columns H, each
/// at least 1; [`Extent::new`] is the one constructor.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct Extent {
    pub rows: i32,
    pub columns: i32,
}

impl Extent {
    /// The extent of `rows` rows and `columns` columns, none where either is
    /// below 1: no frame has a side below 1.
    pub fn new(rows: i32, columns: i32) -> Option<Extent> {
        (rows >= 1 && columns >= 1).then_some(Extent { rows, columns })
    }
}

/// The one extent that the derivations of a row give, as the derivations come:
/// none yet, one, or none because two differ or one has none.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub enum Merged {
    #[default]
    Unset,
    One(Extent),
    None,
}

impl Merged {
    /// Takes the extent `extent` of one more derivation.
    pub fn merge(&mut self, extent: Option<Extent>) {
        *self = match (*self, extent) {
            (Merged::Unset, Some(extent)) => Merged::One(extent),
            (Merged::One(held), Some(extent)) if held == extent => Merged::One(held),
            _ => Merged::None,
        };
    }

    /// The extent, none where there is none or no derivation gave one.
    pub fn extent(&self) -> Option<Extent> {
        match self {
            Merged::One(extent) => Some(*extent),
            Merged::Unset | Merged::None => None,
        }
    }
}

/// The extents of one entry of a table, a model at an assignment on an example.
#[derive(Clone, Debug)]
pub enum EntryExtents {
    /// For each row of the model's relation, in the order of [`each_row`], the
    /// extent of each of the table's extent columns, in their order.
    Rows(Vec<Box<[Option<Extent>]>>),
    /// The entry has no extent: its model holds no rows.
    Absent,
    /// The entry holds rows and has no extent, for this reason: the message
    /// and form of the fault of a widened body (`"<message> at <form>"`), or
    /// why the extents do not derive its rows.
    Lost(String),
    /// The evaluation of the bodies stopped at this bound.
    Stopped(Stop),
}

/// The extents of the made frames of a table's `Box` columns.
#[derive(Clone, Debug)]
pub struct Extents {
    /// Every Position, Box and Offset column in native scalar-column order.
    pub columns: Vec<u32>,
    /// Native proof that a column has no reference grid (not missing evidence).
    pub no_grid: Vec<bool>,
    /// Direct grid evidence is independent of whether a different column's
    /// derivation stops. Keep it without retaining or re-evaluating any rows.
    grids: Vec<DirectGrids>,
    /// For each example of the table, for each assignment of its rows, for each
    /// model; empty for an example whose rows fault.
    examples: Vec<Vec<Vec<EntryExtents>>>,
}

#[derive(Clone, Copy, Debug)]
struct DirectGrids {
    input: Option<Extent>,
    output: Option<Extent>,
}

impl DirectGrids {
    fn at(&self, frame: &str) -> Option<Extent> {
        match frame {
            INPUT_FRAME => self.input,
            OUTPUT_FRAME => self.output,
            _ => None,
        }
    }
}

fn direct_grids(decoder: &Decoder<'_>, contents: &Contents) -> Vec<DirectGrids> {
    contents.examples.iter().map(|example| DirectGrids {
        input: grid_extent(decoder, INPUT_FRAME, example.example),
        output: grid_extent(decoder, OUTPUT_FRAME, example.example),
    }).collect()
}

impl Extents {
    /// The extents of the entry at `model` of the assignment `assignment` on
    /// the example `example` of the table.
    pub fn entry(&self, example: usize, assignment: usize, model: usize) -> Option<&EntryExtents> {
        self.examples.get(example)?.get(assignment)?.get(model)
    }

    /// Evidence that does not depend on a widened-body query. Also used by
    /// downstream native reads when another column's derivation stopped.
    fn direct_at(&self, contents: &Contents, example: usize, column: usize, value: TermId) -> Option<Extent> {
        match contents.columns[column].ty {
            ValueType::Position => position_extent(value, &ValueType::Position),
            ValueType::Box => {
                let extent = self.grids.get(example)?.at(&contents.frames[column])?;
                fitted_size(extent, margins_of(value, &ValueType::Box)?).map(|_| extent)
            }
            _ => None,
        }
    }
}

/// What the derivations of one entry of a relation give so far.
#[derive(Default)]
struct Gathered {
    /// For each row, the merged extent of each wanted column.
    rows: StableHashMap<Box<[TermId]>, Vec<Merged>>,
    /// The bound that stopped the evaluation of a body at this entry.
    stop: Option<Stop>,
    /// The first reason that a body which gives the entry's rows faulted, or
    /// that the extents cannot derive them.
    lost: Option<String>,
}

impl Gathered {
    /// Records `reason` as the reason the entry lost its extents, where it has
    /// none yet.
    fn lose(&mut self, reason: &str) {
        self.lost.get_or_insert_with(|| reason.to_owned());
    }
}

/// The relation whose rows' extents are wanted: its node, the type of each of
/// its row positions, its rows on each example at each assignment, and the
/// row positions (increasing) whose extents are wanted.
struct Subject<'a> {
    checked: &'a CheckedProgram,
    relation: Option<&'a GraphRelation>,
    types: &'a [ValueType],
    examples: &'a [ExampleRows],
    columns: &'a [u32],
    /// Parallel to the full extent-column list, never a compressed interface.
    /// Internal port derivations have already selected their wanted columns.
    needed: Option<&'a [bool]>,
}

impl Subject<'_> {
    fn needs(&self, column: usize) -> bool {
        self.needed.is_none_or(|needed| needed[column])
    }
}

/// Export coverage does not request evaluation. Only a Box without a direct
/// proof needs a widened derivation. A task-wide/lifted request with no single
/// example retains derivation, since its rows can refer to different grids.
fn derivation_mask(contents: &Contents, columns: &[u32], no_grid: &[bool], grids: &[DirectGrids]) -> Vec<bool> {
    columns.iter().enumerate().map(|(k, &column)| {
        let column = column as usize;
        contents.columns[column].ty == ValueType::Box && !no_grid[k]
            && !grids.iter().all(|grid| grid.at(&contents.frames[column]).is_some())
    }).collect()
}

/// Only positive native provenance proves no_grid. Empty/unknown frame names
/// alone do not. Copying a previously proved no-grid column preserves that fact.
fn no_grid_columns(decoder:&Decoder<'_>, earlier:&[&Table], contents:&Contents, columns:&[u32])->Vec<bool> {
    let names=names_of(decoder.registry(),earlier);
    let dets=contents.dets.iter().map(|d|relation_spelled(&d.relation)).collect::<Vec<_>>();
    columns.iter().map(|c| {
        if contents.columns[*c as usize].ty==ValueType::Offset {return true;}
        let Some(sources)=contents.flows.get(*c as usize).filter(|s|!s.is_empty()) else {return false;};
        sources.iter().all(|source| {
            if source.frames.is_empty() && matches!(source.kind,crate::flows::SourceKind::Constant|crate::flows::SourceKind::LibName) {return true;}
            if source.frames.iter().any(|f|!matches!(f,SourceFrame::Read)) {return false;}
            let located=locate(&names,&dets,source);
            let Some(named)=located.table else {return false;};
            let Some(index)=read_index(&located,source) else {return false;};
            let Some(table)=named.row.checked_sub(EVIDENCE_FACTS.len() as u32).and_then(|i|earlier.get(i as usize)) else {return false;};
            table.contents.as_ref().ok().and_then(|c|c.extents.as_ref()).is_some_and(|e| {
                e.columns.iter().position(|c|*c as usize==index).is_some_and(|k|e.no_grid[k])
            })
        })
    }).collect()
}

fn completed_rows(decoder:&Decoder<'_>,contents:&Contents,example:Option<Example>,relation:&Relation,columns:&[u32],no_grid:&[bool],gathered:Option<&Gathered>)->Vec<Box<[Option<Extent>]>> {
    let mut result=Vec::new();
    each_row(relation,&mut |row| {
        let slots=gathered.and_then(|e|e.rows.get(row));
        result.push(columns.iter().enumerate().map(|(k,c)| {
            if no_grid[k] {return None;}
            let column=*c as usize;
            match &contents.columns[column].ty {
                ValueType::Position=>position_extent(row[column],&ValueType::Position),
                ValueType::Box=>{
                    let extent=grid_extent(decoder,&contents.frames[column],example)
                        .or_else(||slots.and_then(|s|s[k].extent()))?;
                    fitted_size(extent,margins_of(row[column],&ValueType::Box)?).map(|_|extent)
                },
                _=>None,
            }
        }).collect());
    });result
}

fn direct_extents(decoder:&Decoder<'_>,contents:&Contents,columns:Vec<u32>,no_grid:Vec<bool>)->Extents {
    let examples=contents.examples.iter().map(|e|e.rows.as_ref().map_or_else(|_|Vec::new(),|a|a.at.iter().map(|(_,models)|models.iter().map(|v|match v {
        // These rows were already materialized and charged. This is the same
        // formatting walk as the native value buffer, not another evaluation.
        RelationValue::Rows(rows)=>EntryExtents::Rows(completed_rows(decoder,contents,e.example,rows,&columns,&no_grid,None)),
        _=>EntryExtents::Absent,
    }).collect()).collect())).collect();
    Extents {columns,no_grid,examples,grids:direct_grids(decoder,contents)}
}

/// Native per-cell annotation, in the relation's each_row order. This is used
/// for body/component buffers and the full-held-choice sidecar alike.
pub fn annotated_rows(contents:&Contents,example:usize,assignment:usize,model:usize,relation:&Relation)->Vec<Vec<(u8,Option<Extent>)>> {
    let columns=contents.columns.iter().enumerate().filter(|(_,c)|c.ty.is_box()).map(|(i,_)|i as u32).collect::<Vec<_>>();
    let extents=contents.extents.as_ref();
    let held=extents.and_then(|e|e.entry(example,assignment,model));
    let mut result=Vec::new();let mut at=0;
    each_row(relation,&mut |row| {
        result.push(columns.iter().enumerate().map(|(k,c)| {
            let no_grid=contents.columns[*c as usize].ty==ValueType::Offset || extents.is_some_and(|e|e.no_grid.get(k)==Some(&true));
            if no_grid {return (0,None);}
            let extent=match held {Some(EntryExtents::Rows(rows))=>rows.get(at).and_then(|r|r.get(k)).copied().flatten(),_=>None}
                .or_else(||match contents.columns[*c as usize].ty {
                    ValueType::Position=>position_extent(row[*c as usize],&ValueType::Position),
                    ValueType::Box=>extents?.direct_at(contents,example,*c as usize,row[*c as usize]),
                    _=>None,
                });
            (if extent.is_some(){1}else{2},extent)
        }).collect());at+=1;
    });result
}

/// The extents of the made frames of the `Box` columns of the table of
/// `relation`, whose contents are `contents` with their `frames`, in `checked`:
/// none where the table has no such column. The columns are those of
/// `extent_columns` of `contents.frames`. `earlier` are the tables before it
/// that its rows read.
pub fn table_extents(decoder: &Decoder<'_>, earlier: &[&Table], checked: &CheckedProgram, relation: &GraphRelation, contents: &Contents) -> Option<Extents> {
    let types: Vec<ValueType> = contents.columns.iter().map(|column| column.ty.clone()).collect();
    let columns = extent_columns(&types, &contents.frames);
    if columns.is_empty() { return None; }
    let no_grid = no_grid_columns(decoder, earlier, contents, &columns);
    let grids = direct_grids(decoder, contents);
    let needed = derivation_mask(contents, &columns, &no_grid, &grids);
    if !needed.iter().any(|needed| *needed) {
        return Some(direct_extents(decoder,contents,columns,no_grid));
    }
    let names = names_of(decoder.registry(), earlier);
    let reads = Reads { names, tables: earlier, cache: RefCell::default(), work: decoder.table_work() };
    let subject = Subject { checked, relation:Some(relation), types: &types, examples: &contents.examples, columns: &columns, needed:Some(&needed) };
    let gathered = derive(decoder, &reads, &subject);
    Some(Extents { examples: finish(decoder, contents, &gathered, &columns, &no_grid), columns, no_grid, grids })
}

/// Extents of a checked body query, using the same native derivation and
/// earlier-table lookup as relation tables, with its exact result interface.
pub fn body_extents(decoder:&Decoder<'_>,earlier:&[&Table],checked:&CheckedProgram,view:&BodyView,contents:&Contents)->Option<Extents> {
    let types=contents.columns.iter().map(|c|c.ty.clone()).collect::<Vec<_>>();
    let columns=extent_columns(&types,&contents.frames);
    if columns.is_empty() {return None;}
    let no_grid=no_grid_columns(decoder,earlier,contents,&columns);
    let grids=direct_grids(decoder,contents);
    let needed=derivation_mask(contents,&columns,&no_grid,&grids);
    if !needed.iter().any(|needed| *needed) {
        return Some(direct_extents(decoder,contents,columns,no_grid));
    }
    let reads=Reads {names:names_of(decoder.registry(),earlier),tables:earlier,cache:RefCell::default(),work:decoder.table_work()};
    let subject=Subject {checked,relation:None,types:&types,examples:&contents.examples,columns:&columns,needed:Some(&needed)};
    let mut gathered=subject.examples.iter().map(|e|e.rows.as_ref().map_or_else(|_|Vec::new(),|a|a.at.iter().map(|_|Gathered::default()).collect())).collect::<Vec<Vec<Gathered>>>();
    let placements=view.clause.columns.iter().enumerate().map(|(i,v)|Some(Placement {slot:i as u32,label:Some(view.paths.labels[v.0 as usize])})).collect::<Vec<_>>();
    let dets=contents.dets.iter().map(|d|relation_spelled(&d.relation)).collect::<Vec<_>>();
    match view.widened() {
        Ok(views)=>for sub in &views {gather(decoder,&reads,&dets,&subject,sub,&placements,&mut gathered)},
        Err(fault)=>lose_all(&mut gathered,&fault_spelled(&fault)),
    }
    Some(Extents {examples:finish(decoder,contents,&gathered,&columns,&no_grid),columns,no_grid,grids})
}

/// What the derivations of the rows of `subject` give for each of its
/// examples, for each of its assignments: the widened bodies of the clauses
/// that give the relation, or of the clauses that an instance writes for an
/// input, or the inputs of the instance that an output reads.
fn derive(decoder: &Decoder<'_>, reads: &Reads<'_>, subject: &Subject<'_>) -> Vec<Vec<Gathered>> {
    let registry = decoder.registry();
    let (checked, relation) = (subject.checked, subject.relation.expect("relation derivation has a subject"));
    let mut gathered: Vec<Vec<Gathered>> = subject.examples.iter().map(|example| example.rows.as_ref().map_or_else(|_| Vec::new(), |rows| rows.at.iter().map(|_| Gathered::default()).collect())).collect();
    let dets: Vec<String> = relation_dets(checked, relation.node).iter().map(|det| relation_spelled(&det.relation)).collect();
    let kind = &checked.program.graph.nodes[relation.node.0 as usize].kind;
    let root = NodeRef::Program(checked.program.program.value());
    // The clauses that the instance of an input writes, widened, and how many of them the givens have used.
    let mut used = 0;
    for given in checked.program.given(relation.node, registry) {
        if relation.output.as_deref().zip(given.output.as_deref()).is_some_and(|(read, own)| read != own) {
            continue;
        }
        let placements = || column_placements(checked, relation.node, relation.output.as_deref(), &given.form, subject.types.len(), registry);
        match (node_at(root, &given.form), kind) {
            (Some(NodeRef::Clause(_)), _) => {
                let placements=placements();
                gather_view(decoder,reads,&dets,subject,&given.form.child(0),&placements,&mut gathered);
            }
            (Some(NodeRef::Choose(_)), _) => {
                let placements=placements();
                // Every selected row is an original option. Match its whole
                // native row against the checked for/from derivations; do
                // not treat selection as a new frame or widen the pick.
                match BodyView::choose_options(checked,&given.form).and_then(|view|view.widened()) {
                    Ok(views)=>for view in &views {gather(decoder,reads,&dets,subject,view,&placements,&mut gathered)},
                    Err(fault)=>lose_all(&mut gathered,&fault_spelled(&fault)),
                }
            }
            (Some(NodeRef::RigidDet(_)), DependencyKind::RigidAssembly(_)) => {
                // Rigid outputs are native D4 images, not the rows of a
                // widened clause. flows_visiting deliberately marks moved
                // part frames Unknown: the pre-image's frame is not proof
                // of the image's extent. Leave these slots Unset, which
                // finish exports as unresolved, rather than reporting a
                // fault in already evaluated native rows. Intrinsic Position
                // and known grid-frame evidence is completed independently.
            }
            (Some(NodeRef::Instance(_)), DependencyKind::InstanceInput { input, .. }) => {
                let placements=placements();
                let all=checked.program.input_bodies(&given.form,input);
                match all.get(used) {
                    Some(body)=>gather_view(decoder,reads,&dets,subject,&given.form.join(body),&placements,&mut gathered),
                    None=>lose_all(&mut gathered,"the instance writes no clause for the input at this form"),
                }
                used+=1;
            }
            (Some(NodeRef::Instance(instance)),DependencyKind::RecursiveInstance(_))=>{
                let port=given.output.as_deref().and_then(|steps|match steps {[arclog::program::OutputStep::Port(port)]=>Some(port),_=>None});
                let component=registry_columns::component(registry,&instance.component).expect("checked component");
                match port {
                    Some(port) if !component.outputs.iter().any(|own|own.name==*port)=>{
                        let placements=placements();
                        let all=checked.program.input_bodies(&given.form,port);
                        for at in all {gather_view(decoder,reads,&dets,subject,&given.form.join(&at),&placements,&mut gathered);}
                    }
                    _=>gather_output(decoder,reads,subject,&given,instance,&mut gathered),
                }
            }
            (Some(NodeRef::Instance(instance)), DependencyKind::InstanceOutput { .. }) => gather_output(decoder, reads, subject, &given, instance, &mut gathered),
            _ => lose_all(&mut gathered, &format!("the rows of a {} form are not derived", kind_spelled(kind))),
        }
    }
    gathered
}

/// The spelling of the kind of form that gives a relation's rows, as the
/// program writes the form where it has a keyword.
fn kind_spelled(kind: &DependencyKind) -> &'static str {
    match kind {
        DependencyKind::Fact(_) => "fact",
        DependencyKind::Clause(_) => "clause",
        DependencyKind::InstanceInput { .. } => "instance input",
        DependencyKind::InstanceOutput { .. } => "instance output",
        DependencyKind::Parameter(_) => "parameter",
        DependencyKind::Chosen(_) => "CHOOSE",
        DependencyKind::RigidAssembly(_) => "RIGID_DET",
        DependencyKind::Demonstrated(_) => "DEMONSTRATED",
        DependencyKind::RecursiveInstance(_) => "recursive instance",
        DependencyKind::Out(_) => "OUT",
    }
}

/// Marks every entry as lost, for `reason`.
fn lose_all(gathered: &mut [Vec<Gathered>], reason: &str) {
    for entry in gathered.iter_mut().flatten() {
        entry.lose(reason);
    }
}

/// Adds to `gathered` the extents that the rows of the widened body `body`
/// give: each row of the body derives the relation's row at the label of each of
/// its columns (`placements`), with the extent of each wanted column. `dets` are
/// the `DET`s of the relation.
fn gather_view(decoder:&Decoder<'_>,reads:&Reads<'_>,dets:&[String],subject:&Subject<'_>,at:&NodePath,placements:&[Option<Placement>],gathered:&mut [Vec<Gathered>]) {
    match BodyView::at(subject.checked,at).and_then(|view|view.widened()) {
        Ok(views)=>for view in &views {gather(decoder,reads,dets,subject,view,placements,gathered)},
        Err(fault)=>lose_all(gathered,&fault_spelled(&fault)),
    }
}

fn gather(decoder: &Decoder<'_>, reads: &Reads<'_>, dets: &[String], subject: &Subject<'_>, sub: &BodyView, placements: &[Option<Placement>], gathered: &mut [Vec<Gathered>]) {
    let at_label = |placement: &Option<Placement>| placement.and_then(|placement| placement.label).and_then(|label| sub.column_of(label));
    let Some(key) = placements.iter().map(at_label).collect::<Option<Vec<usize>>>() else {
        return lose_all(gathered, "a relation column has no label in its checked derivation");
    };
    let checked=subject.checked;
    let types=sub.clause.columns.iter().map(|v|sub.clause.variables[v.0 as usize].ty.clone()).collect::<Vec<_>>();
    let sources=body_column_flows(checked,&sub.clause,&sub.paths,decoder.registry());
    let analysis=Analysis {decoder,registry:decoder.registry(),checked,sub,types:&types,sources,reads,dets};
    let walked=crate::tables::body_tables::dets(checked,sub);
    let values=crate::tables::body_tables::examples(decoder,checked,sub,&walked,&reads.work);
    for (place, example) in subject.examples.iter().enumerate() {
        let Ok(rows) = &example.rows else { continue };
        let entries = &mut gathered[place];
        let Some(found) = values.iter().find(|own| own.example == example.example) else {
            entries.iter_mut().for_each(|entry| entry.lose("the widened body is not evaluated on the example"));
            continue;
        };
        let assigned = match &found.rows {
            Ok(assigned) => assigned,
            Err(fault) => {
                entries.iter_mut().for_each(|entry| entry.lose(&fault_spelled(fault)));
                continue;
            }
        };
        for ((table_assignment, _), entry) in rows.at.iter().zip(entries.iter_mut()) {
            let mut matched = false;
            for (body_assignment, models) in assigned.at.iter().filter(|(own, _)| consistent(table_assignment, own)) {
                matched = true;
                for value in models {
                    match value {
                        RelationValue::Rows(body_rows) => {
                            if let Err(stop) = reads.charge(body_rows.len(), &sub.form) {
                                entry.stop = Some(stop);
                                continue;
                            }
                            let ctx = Ctx { example: example.example, assignment: body_assignment };
                            each_row(body_rows, &mut |row| {
                                let derived: Box<[TermId]> = key.iter().map(|&column| row[column]).collect();
                                let slots = entry.rows.entry(derived).or_insert_with(|| vec![Merged::Unset; subject.columns.len()]);
                                for (k, (slot, &column)) in slots.iter_mut().zip(subject.columns).enumerate() {
                                    if subject.needs(k) {
                                        slot.merge(analysis.extent_of(key[column as usize], row, &ctx, 0));
                                    }
                                }
                            });
                            // The reads of earlier tables that the rows made may have passed the cap.
                            if let Err(stop) = reads.charge(0, &sub.form) {
                                entry.stop = Some(stop);
                            }
                        }
                        RelationValue::Stopped(stop) => entry.stop = Some(stop.clone()),
                        RelationValue::Undefined => entry.lose("the relation of the widened body is undefined"),
                    }
                }
            }
            if !matched {
                entry.stop = entry.stop.take().or_else(|| assigned.stop.clone());
            }
        }
    }
}

/// An input of an instance that the extents of an output read: its name, its
/// node, the row positions of its key, the row positions whose extents are
/// wanted, and their derivation.
struct PortRows {
    name: PortName,
    relation:GraphRelation,
    key: Option<Range<usize>>,
    wanted: Vec<u32>,
    derived: Option<(Vec<ExampleRows>, Vec<Vec<Gathered>>)>,
}

impl PortRows {
    /// What the derivations give of the port at the assignment `assigned` on
    /// `example`.
    fn entry(&self, example: Option<Example>, assigned: &[Assignment]) -> Option<&Gathered> {
        let (examples, gathered) = self.derived.as_ref()?;
        let place = examples.iter().position(|own| own.example == example)?;
        let rows = examples[place].rows.as_ref().ok()?;
        let at = rows.at.iter().position(|(own, _)| consistent(assigned, own))?;
        gathered[place].get(at)
    }
}

/// Where the extent of an output column comes from: the wanted position of the
/// port `port` at index `slot` among the port's wanted positions.
struct Source {
    port: usize,
    slot: usize,
}

/// How the extent of a wanted column of an output is found: from the rows of
/// the `sources`, matched to the output's rows by the key and the cell of the
/// column where `by_cell` holds, and by the key alone otherwise.
struct ColumnPlan {
    sources: Vec<Source>,
    by_cell: bool,
}

/// The inputs of an instance that the extents of its output read, and how each
/// wanted column of the output reads them, none for a column with no extent.
struct OutputPlan {
    ports: Vec<PortRows>,
    columns: Vec<Option<ColumnPlan>>,
    /// The row positions of the output's key.
    key: Option<Range<usize>>,
}

impl OutputPlan {
    /// The plan for the wanted columns of the output of the instance `instance`
    /// that `given` gives, where each wanted column `c` takes its extent from:
    ///
    /// - a column of the output's key: the same key column of an input that has a
    ///   key, over the rows of that input with the row's key;
    /// - a column that a declared row of `copies` maps from input columns: those
    ///   columns, over the rows of the inputs with the row's key whose cell
    ///   there equals the row's;
    /// - another column whose frame rule makes no frame and names input columns:
    ///   those columns, over the rows of the inputs with the row's key.
    ///
    /// The key is dropped where the output or an input has none. Any other
    /// column has no extent.
    fn new(decoder: &Decoder<'_>, subject: &Subject<'_>, given: &Given, instance: &Instance) -> Option<OutputPlan> {
        let registry = decoder.registry();
        let (checked, relation) = (subject.checked, subject.relation.expect("relation derivation has a subject"));
        let width = subject.types.len();
        let frames = output_frames(checked, relation.node, relation.output.as_deref(), &given.form, width, registry);
        let copies = output_copies(checked, relation.node, relation.output.as_deref(), &given.form, width, registry);
        let component = registry_columns::component(registry, &instance.component)?;
        let key = key_range(given.slots.iter().map(|slot| (slot.is_key, slot.width)));
        let mut ports: Vec<PortRows> = Vec::new();
        // The index among `ports` of the input `name`, which `ports` gains when it lacks it.
        let port_of = |name: &PortName, ports: &mut Vec<PortRows>| -> Option<usize> {
            if let Some(place) = ports.iter().position(|own| own.name == *name) {
                return Some(place);
            }
            let relation=arclog::eval::input_relation(checked,&instance.name,name)?;
            let input = component.inputs.iter().find(|input| input.port.name == *name)?;
            let slots = checked.program.instance_port_slots(&given.form, &input.port, registry)?;
            ports.push(PortRows { name: name.clone(), relation, key: key_range(slots.iter().map(|slot| (slot.is_key, slot.width))), wanted: Vec::new(), derived: None });
            Some(ports.len() - 1)
        };
        let mut columns: Vec<Option<ColumnPlan>> = Vec::new();
        for (k, &column) in subject.columns.iter().enumerate() {
            if !subject.needs(k) {
                columns.push(None);
                continue;
            }
            let position = column as usize;
            let wants: Option<(Vec<(PortName, usize)>, bool)> = match &key {
                Some(key) if key.contains(&position) => component.inputs.iter().find_map(|input| {
                    let place = port_of(&input.port.name, &mut ports)?;
                    let held = ports[place].key.as_ref().filter(|held| held.len() == key.len())?;
                    Some((vec![(input.port.name.clone(), held.start + position - key.start)], false))
                }),
                _ if !copies[position].is_empty() => copies[position].iter().all(|(_, range)| range.len() == 1).then(|| (copies[position].iter().map(|(name, range)| (name.clone(), range.start)).collect(), true)),
                _ => frames[position].as_ref().filter(|frame| usable(frame)).map(|frame| (frame.named.iter().map(|(name, range)| (name.clone(), range.start)).collect(), false)),
            };
            columns.push(wants.and_then(|(wants, by_cell)| {
                let sources = wants
                    .iter()
                    .map(|(name, wanted)| {
                        let port = port_of(name, &mut ports)?;
                        let wanted = u32::try_from(*wanted).ok()?;
                        let slot = ports[port].wanted.iter().position(|&own| own == wanted).unwrap_or_else(|| {
                            ports[port].wanted.push(wanted);
                            ports[port].wanted.len() - 1
                        });
                        Some(Source { port, slot })
                    })
                    .collect::<Option<Vec<Source>>>()?;
                Some(ColumnPlan { sources, by_cell })
            }));
        }
        Some(OutputPlan { ports, columns, key })
    }

    /// Derives the rows of each input whose extents a column wants.
    fn derive_ports(&mut self, decoder: &Decoder<'_>, reads: &Reads<'_>, checked: &CheckedProgram) {
        for port in self.ports.iter_mut().filter(|port| !port.wanted.is_empty()) {
            let port_relation=port.relation.clone();
            let Some(types) = checked.types.columns(&port_relation) else { continue };
            let examples = relation_examples(decoder, checked, &port_relation, &relation_dets(checked, port_relation.node), &reads.work);
            let port_subject = Subject { checked, relation: Some(&port_relation), types, examples: &examples, columns: &port.wanted, needed:None };
            let derived = derive(decoder, reads, &port_subject);
            port.derived = Some((examples, derived));
        }
    }

    /// The extents that the inputs give each wanted column at the assignment
    /// `assigned` on `example`; a stop of an input's derivation stops `entry`.
    fn lookups(&self, example: Option<Example>, assigned: &[Assignment], entry: &mut Gathered) -> Vec<Lookup> {
        let held: Vec<Option<&Gathered>> = self.ports.iter().map(|port| port.entry(example, assigned)).collect();
        self.columns
            .iter()
            .map(|plan| {
                let mut lookup = Lookup::default();
                let Some(plan) = plan else {
                    lookup.bad = true;
                    return lookup;
                };
                lookup.by_cell = plan.by_cell;
                lookup.keyed = self.key.is_some() && plan.sources.iter().all(|source| self.ports[source.port].key.is_some());
                for source in &plan.sources {
                    let port = &self.ports[source.port];
                    let Some(rows) = held[source.port] else {
                        lookup.bad = true;
                        continue;
                    };
                    if let Some(stop) = &rows.stop {
                        entry.stop = Some(stop.clone());
                    }
                    lookup.bad |= rows.lost.is_some();
                    let position = port.wanted[source.slot] as usize;
                    for (row, slots) in &rows.rows {
                        let extent = slots[source.slot].extent();
                        let key: Box<[TermId]> = match (&port.key, lookup.keyed) {
                            (Some(key), true) => row[key.clone()].into(),
                            _ => Box::default(),
                        };
                        lookup.any.merge(extent);
                        if lookup.by_cell {
                            lookup.cells.entry((key, row[position])).or_insert(Merged::Unset).merge(extent);
                        } else if lookup.keyed {
                            lookup.keys.entry(key).or_insert(Merged::Unset).merge(extent);
                        }
                    }
                }
                lookup
            })
            .collect()
    }
}

/// Adds to `gathered` the extents of the rows of the output of the instance
/// `instance` that `given` gives, as [`OutputPlan::new`] gives them.
fn gather_output(decoder: &Decoder<'_>, reads: &Reads<'_>, subject: &Subject<'_>, given: &Given, instance: &Instance, gathered: &mut [Vec<Gathered>]) {
    let Some(mut plan) = OutputPlan::new(decoder, subject, given, instance) else { return lose_all(gathered, "the component of the instance is not in the registry") };
    plan.derive_ports(decoder, reads, subject.checked);
    for (place, example) in subject.examples.iter().enumerate() {
        let Ok(rows) = &example.rows else { continue };
        for ((assigned, models), entry) in rows.at.iter().zip(gathered[place].iter_mut()) {
            let lookups = plan.lookups(example.example, assigned, entry);
            for model in models {
                let RelationValue::Rows(model_rows) = model else { continue };
                if let Err(stop) = reads.charge(model_rows.len(), &given.form) {
                    entry.stop = Some(stop);
                    continue;
                }
                each_row(model_rows, &mut |row| {
                    let slots: Vec<Merged> = subject.columns.iter().zip(&lookups).map(|(&column, lookup)| lookup.of(row, column as usize, plan.key.as_ref())).collect();
                    entry.rows.entry(row.into()).or_insert(slots);
                });
            }
        }
    }
}

/// The extents that the rows of the inputs of an instance give one wanted
/// column of its output.
#[derive(Default)]
struct Lookup {
    /// Whether the column has no extent.
    bad: bool,
    /// Whether the rows match by the key, and by the cell of the column.
    keyed: bool,
    by_cell: bool,
    /// The merged extent at all the rows, at each key, and at each key and cell.
    any: Merged,
    keys: StableHashMap<Box<[TermId]>, Merged>,
    cells: StableHashMap<(Box<[TermId]>, TermId), Merged>,
}

impl Lookup {
    /// The extent of the output row `row`, whose cell at the wanted column
    /// `column` is `row[column]` and whose key stands at `key`.
    fn of(&self, row: &[TermId], column: usize, key: Option<&Range<usize>>) -> Merged {
        if self.bad {
            return Merged::None;
        }
        let key: Box<[TermId]> = match key {
            Some(key) if self.keyed => row[key.clone()].into(),
            _ => Box::default(),
        };
        let found = match (self.by_cell, self.keyed) {
            (true, _) => self.cells.get(&(key, row[column])),
            (false, true) => self.keys.get(&key),
            (false, false) => return self.any,
        };
        found.copied().unwrap_or(Merged::Unset)
    }
}

/// The row positions of the key among those of a relation whose columns are
/// `slots`, each whether it is the `key` column and its width.
fn key_range(slots: impl Iterator<Item = (bool, usize)>) -> Option<Range<usize>> {
    let mut start = 0;
    for (is_key, width) in slots {
        if is_key {
            return Some(start..start + width);
        }
        start += width;
    }
    None
}

/// Whether the frame rule `frame` of an output column gives the frame of the
/// columns it names, each of one row position: a rule that makes no frame and
/// names a column.
fn usable(frame: &OutputFrame) -> bool {
    !frame.rule.makes && !frame.named.is_empty() && frame.named.iter().all(|(_, range)| range.len() == 1)
}

/// The extents of `contents`' entries, from what their derivations gave.
fn finish(decoder: &Decoder<'_>, contents: &Contents, gathered: &[Vec<Gathered>], columns: &[u32], no_grid: &[bool]) -> Vec<Vec<Vec<EntryExtents>>> {
    contents
        .examples
        .iter()
        .zip(gathered)
        .map(|(example, entries)| match &example.rows {
            Err(_) => Vec::new(),
            Ok(rows) => rows
                .at
                .iter()
                .zip(entries)
                .map(|((_, models), entry)| {
                    models
                        .iter()
                        .map(|value| match (value, &entry.stop) {
                            (RelationValue::Rows(_), Some(stop)) => EntryExtents::Stopped(stop.clone()),
                            (RelationValue::Rows(relation), None) => match &entry.lost {
                                Some(reason) if !relation.is_empty() => EntryExtents::Lost(reason.clone()),
                                Some(_) => EntryExtents::Absent,
                                None => EntryExtents::Rows(completed_rows(decoder,contents,example.example,relation,columns,no_grid,Some(entry))),
                            },
                            _ => EntryExtents::Absent,
                        })
                        .collect()
                })
                .collect(),
        })
        .collect()
}

/// Whether the assignment `table` of the `DET`s of a table's relation and the
/// assignment `body` of those of a body that gives its rows give each `DET` the
/// two share one value.
fn consistent(table: &[Assignment], body: &[Assignment]) -> bool {
    table.iter().all(|(relation, value)| body.iter().find(|(own, _)| own == relation).is_none_or(|(_, held)| same_rows(held, value)))
}

fn same_rows(left: &Relation, right: &Relation) -> bool {
    std::ptr::eq(left, right) || left.rows_hash() == right.rows_hash()
}

/// Where a row is evaluated: its example, and the assignment of the `DET`s of
/// the body that gives it.
struct Ctx<'a> {
    example: Option<Example>,
    assignment: &'a [Assignment],
}

/// The earlier tables that the rows of a table read, and the work count of the
/// table's derivation.
struct Reads<'a> {
    /// The tables before the table, as the columns of the case name them.
    names: TableNames,
    tables: &'a [&'a Table],
    /// For a column of a table read, the extent at each key of the cells of the
    /// columns that the read fixes, as [`Reads::extent_at`] builds it.
    cache: RefCell<StableHashMap<LookupKey, Rc<StableHashMap<Box<[TermId]>, Merged>>>>,
    /// The count that the derivation's evaluations, and the rows it visits, are charged to.
    work: TableWork,
}

/// A table of the stream by its number, the place of the example and of the
/// assignment of its entry, the column read, and the columns whose cells the
/// read fixes.
type LookupKey = (u32, usize, usize, usize, Vec<usize>);

impl Reads<'_> {
    /// Adds `rows` visited rows to the table's work count; the stop at the work
    /// cap, at the form `form`, where the count is then past the cap.
    fn charge(&self, rows: u64, form: &NodePath) -> Result<(), Stop> {
        self.work.charge(rows).map_err(|bound| Stop { bound, form: form.clone() })
    }

    /// The extent of the frame of the column `index` of the table `named`, at its rows
    /// whose cells at the columns of `constraints` are the cells they pair them
    /// with, on `example` at the assignment `assignment`; none where the rows give
    /// two extents, where none matches, or where the table has more than one model at
    /// the assignment.
    fn extent_at(&self, named: &Named, index: usize, example: Option<Example>, constraints: &[(usize, TermId)], assignment: &[Assignment]) -> Option<Extent> {
        let table = self.tables.get((named.row as usize).checked_sub(EVIDENCE_FACTS.len())?)?;
        let contents = table.contents.as_ref().ok()?;
        let place = contents.examples.iter().position(|own| own.example == example).or_else(|| contents.examples.iter().position(|own| own.example.is_none()))?;
        let rows = contents.examples[place].rows.as_ref().ok()?;
        let at = rows.at.iter().position(|(assigned, _)| consistent(assigned, assignment))?;
        let [RelationValue::Rows(relation)] = &rows.at[at].1[..] else { return None };
        let fixed: Vec<usize> = constraints.iter().map(|&(column, _)| column).collect();
        let key = (named.row, place, at, index, fixed);
        let held = self.cache.borrow().get(&key).cloned();
        let lookup = match held {
            Some(held) => held,
            None => {
                let built = Rc::new(self.build(contents, place, at, relation, index, &key.4));
                self.cache.borrow_mut().insert(key, Rc::clone(&built));
                built
            }
        };
        let cells: Box<[TermId]> = constraints.iter().map(|&(_, cell)| cell).collect();
        lookup.get(&cells).and_then(Merged::extent)
    }

    /// The merged extent of the frame of the column `index` of the rows `relation` of
    /// the entry (`place`, `at`) of `contents`, by the cells of the columns `fixed`.
    fn build(&self, contents: &Contents, place: usize, at: usize, relation: &Relation, index: usize, fixed: &[usize]) -> StableHashMap<Box<[TermId]>, Merged> {
        let ty = contents.columns.get(index).map(|column| &column.ty);
        let held = match contents.extents.as_ref().and_then(|extents| extents.entry(place, at, 0)) {
            Some(EntryExtents::Rows(held)) => Some(held),
            _ => None,
        };
        let held_at = contents.extents.as_ref().and_then(|extents| extents.columns.iter().position(|&column| column as usize == index));
        let mut merged: StableHashMap<Box<[TermId]>, Merged> = StableHashMap::default();
        if self.work.charge(relation.len()).is_err() {
            return merged;
        }
        let mut row_at = 0;
        each_row(relation, &mut |row| {
            let extent = match ty {
                Some(ValueType::Position) => position_extent(row[index], &ValueType::Position),
                _ => held.zip(held_at).and_then(|(held, column)| held.get(row_at)?.get(column).copied().flatten())
                    .or_else(|| contents.extents.as_ref()?.direct_at(contents, place, index, row[index])),
            };
            let key: Box<[TermId]> = fixed.iter().map(|&column| row[column]).collect();
            merged.entry(key).or_insert(Merged::Unset).merge(extent);
            row_at += 1;
        });
        merged
    }
}

/// The analysis of a widened body: the sources of the labels of its columns.
struct Analysis<'a> {
    decoder: &'a Decoder<'a>,
    registry: &'a Registry,
    checked:&'a CheckedProgram,
    sub: &'a BodyView,
    /// The type of each column of the body's relation.
    types: &'a [ValueType],
    /// The sources of each column ([`column_flows`]).
    sources: Vec<Vec<ColumnSource>>,
    reads: &'a Reads<'a>,
    /// The `DET`s of the relation the body gives rows of, as their relations are spelled.
    dets: &'a [String],
}

/// The deepest chain of sizes that the extent of a frame follows.
const DEPTH: u8 = 16;

impl Analysis<'_> {
    /// The extent of the frame of the value at column `column` of `row`, a row
    /// of the body.
    fn extent_of(&self, column: usize, row: &[TermId], ctx: &Ctx<'_>, depth: u8) -> Option<Extent> {
        match self.types.get(column)? {
            ValueType::Position => position_extent(row[column], &ValueType::Position),
            ValueType::Box if depth < DEPTH => {
                let mut found: Option<Extent> = None;
                for source in &self.sources[column] {
                    for frame in &source.frames {
                        let extent = match frame {
                            SourceFrame::Unknown => None,
                            SourceFrame::Made { maker, at, .. } => self.made_extent(maker, at, row, ctx, depth),
                            SourceFrame::Read => self.read_extent(source, row, ctx),
                        }?;
                        if *found.get_or_insert(extent) != extent {
                            return None;
                        }
                    }
                }
                found
            }
            _ => None,
        }
    }

    /// The extent of the frame that the lib column `maker` makes at the atom
    /// `at`: the own size of the value at the maker's `size` column of the atom,
    /// with its rows and columns swapped where the D4 element at the `by` column
    /// moves the top edge to the left or the right edge, plus the margins of the
    /// value at the maker's column.
    fn made_extent(&self, maker: &Maker, at: &NodePath, row: &[TermId], ctx: &Ctx<'_>, depth: u8) -> Option<Extent> {
        // A column of an output makes a frame in the output's table alone: a body reads it as a column of that table.
        let Maker::Relation { relation, column } = maker else { return None };
        let size = self.registry.frame_size(relation, column)?;
        let atom = atom_at(self.checked, at)?;
        let made = self.sub.column_of(site_label(atom, column)?)?;
        let sized = self.sub.column_of(site_label(atom, &size.column.column)?)?;
        let margins = margins_of(row[made], self.types.get(made)?)?;
        let (mut own_rows, mut own_columns) = self.own_size(sized, row, ctx, depth)?;
        if let Some(by) = &size.by {
            let element = self.sub.column_of(site_label(atom, &by.column)?)?;
            if matches!(Geometry::get().element(row[element]).image(Edge::Top), Edge::Left | Edge::Right) {
                (own_rows, own_columns) = (own_columns, own_rows);
            }
        }
        Extent::new(own_rows + margins.top + margins.bottom, own_columns + margins.left + margins.right)
    }

    /// The own size of the value at column `column` of `row`: (1, 1) for a
    /// Position, and for a Box the extent of its frame less its margins
    /// ([`fitted_size`]).
    fn own_size(&self, column: usize, row: &[TermId], ctx: &Ctx<'_>, depth: u8) -> Option<(i32, i32)> {
        match self.types.get(column)? {
            ValueType::Position => Some((1, 1)),
            ValueType::Box => {
                let extent = self.extent_of(column, row, ctx, depth + 1)?;
                fitted_size(extent, margins_of(row[column], &ValueType::Box)?)
            }
            _ => None,
        }
    }

    /// The extent of the frame of the column that `source` reads, in the latest
    /// earlier table of the relation it reads.
    fn read_extent(&self, source: &ColumnSource, row: &[TermId], ctx: &Ctx<'_>) -> Option<Extent> {
        let located = locate(&self.reads.names, self.dets, source);
        let named = located.table?;
        let index = read_index(&located, source)?;
        let frame = named.frames.get(index)?;
        // A global frame name can be unavailable while exact matching source
        // rows still carry an unambiguous native per-row extent.
        let example = self.read_example(source, row, ctx)?;
        match frame.as_str() {
            INPUT_FRAME | OUTPUT_FRAME => grid_extent(self.decoder, frame, example),
            _ => {
                let constraints = self.constraints(named, located.det, source, row)?;
                self.reads.extent_at(named, index, example, &constraints, ctx.assignment)
            }
        }
    }

    /// The arguments of the atom of `source` in the IR of the body, with the
    /// paths of the IR; none where the body does not compile.
    fn read_arguments(&self, source: &ColumnSource) -> Option<(&Arguments, &IrPaths)> {
        let (clause,paths)=(&self.sub.clause,&self.sub.paths);
        let arguments = clause.nodes.iter().zip(paths.nodes.iter()).find_map(|(node, at)| match (node, at) {
            (IrNode::Atom(atom), NodePaths::Atom(path)) if *path == source.atom => Some(&atom.arguments),
            _ => None,
        })?;
        Some((arguments, paths))
    }

    /// The column of the body that the label of `argument` stands at, none for
    /// a term.
    fn argument_column(&self, argument: &Argument, paths: &IrPaths) -> Option<usize> {
        let Argument::Variable(variable) = argument else { return None };
        paths.labels.get(usize::from(variable.0)).and_then(|label| self.sub.column_of(*label))
    }

    /// The example that the read of `source` is on: the row's, or, where the
    /// atom reads its relation lifted over the examples, the one that the cell
    /// of its Example label holds. The outer none is a lifted read whose
    /// Example label holds no example.
    fn read_example(&self, source: &ColumnSource, row: &[TermId], ctx: &Ctx<'_>) -> Option<Option<Example>> {
        if !self.checked.program.reads_lifted(&source.atom) {
            return Some(ctx.example);
        }
        let (arguments, paths) = self.read_arguments(source)?;
        let (_, argument) = arguments.0.iter().find(|(position, _)| position.0 == 0)?;
        match Term::decode(row[self.argument_column(argument, paths)?], &ValueType::Example) {
            Term::Constant(Constant::Example(example)) => Some(Some(example)),
            _ => None,
        }
    }

    /// The cells of the columns of the table `named` that the atom of `source`
    /// fixes in `row`: each argument of the atom that stands on a label of the
    /// body, with the column of the table at its position, which is one less
    /// than the atom's where the atom reads its relation lifted over the
    /// examples and its first argument is the Example. None where the body does
    /// not compile.
    fn constraints(&self, named: &Named, det: i32, source: &ColumnSource, row: &[TermId]) -> Option<Vec<(usize, TermId)>> {
        let program = &self.checked.program;
        let lifted = program.reads_lifted(&source.atom);
        let (arguments, paths) = self.read_arguments(source)?;
        let Some(Resolution::Node(node)) = program.resolution(&source.atom) else { return None };
        let node_paths = program.row_paths(*node);
        let mut fixed = Vec::new();
        for (position, argument) in arguments.0.iter() {
            let Some(column) = self.argument_column(argument, paths) else { continue };
            let Some(position) = (if lifted { position.0.checked_sub(1) } else { Some(position.0) }).map(usize::from) else { continue };
            let held = match (&named.paths, node_paths.as_ref().and_then(|paths| paths.get(position))) {
                (Some(held), Some(path)) => held.iter().position(|own| own == path),
                (None, _) if det < 0 => Some(position),
                _ => None,
            };
            if let Some(held) = held {
                fixed.push((held, row[column]));
            }
        }
        Some(fixed)
    }
}

/// The extent of the frame of a value of type `ty` that is a Position: (top +
/// bottom + 1, left + right + 1).
pub(crate) fn position_extent(id: TermId, ty: &ValueType) -> Option<Extent> {
    let margins = margins_of(id, ty)?;
    Extent::new(margins.top + margins.bottom + 1, margins.left + margins.right + 1)
}

/// The own size of a Box of margins `margins` in a frame of extent `extent`:
/// the extent less the margins, none where that is below 1 on an axis, which is
/// where the value does not fit in the frame.
fn fitted_size(extent: Extent, margins: Margins) -> Option<(i32, i32)> {
    let own = Extent::new(extent.rows - margins.top - margins.bottom, extent.columns - margins.left - margins.right)?;
    Some((own.rows, own.columns))
}

fn margins_of(id: TermId, ty: &ValueType) -> Option<Margins> {
    match Term::decode(id, ty) {
        Term::Box(margins) => Some(margins),
        _ => None,
    }
}

/// The extent of the input grid, for the frame `input`, or the output grid, for
/// `output`, of `example`: none for a task-wide request and for a test example's
/// output.
fn grid_extent(decoder: &Decoder<'_>, frame: &str, example: Option<Example>) -> Option<Extent> {
    let example = example?;
    let (task, _, _) = decoder.evaluation_inputs();
    let grid = match frame {
        INPUT_FRAME => task.input(example),
        OUTPUT_FRAME => &task.train.get(usize::from(example.index()))?.output,
        _ => return None,
    };
    let rows = grid.rows();
    Extent::new(i32::try_from(rows.len()).ok()?, i32::try_from(rows.first()?.len()).ok()?)
}

/// The atom at `path` of `program`.
fn atom_at<'p>(program: &'p CheckedProgram, path: &NodePath) -> Option<&'p Atom> {
    match node_at(NodeRef::Program(program.program.program.value()), path)? {
        NodeRef::Conjunct(Conjunct::Atom(atom)) => Some(atom.value()),
        NodeRef::Atom(atom) => Some(atom),
        _ => None,
    }
}

/// The label at the site of `atom` on the column `column`, none where the atom
/// writes no site there or the site holds anything but one label.
fn site_label(atom: &Atom, column: &ColumnName) -> Option<LabelId> {
    single_label(atom.sites.iter().find(|site| site.column == *column)?)
}

/// The label that `site` holds alone.
fn single_label(site: &Site) -> Option<LabelId> {
    let [arg] = &site.value.args[..] else { return None };
    arg.label().and_then(use_label)
}
