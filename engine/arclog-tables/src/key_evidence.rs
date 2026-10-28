//! Key-local frame proofs, evaluated independently of the keyed input join.
//! The native key projection remains the membership relation of that join.
use super::*;
use arclog::eval::ir::AtomSource;
use crate::flows::ReadCoordinates;

pub(super) struct KeyEvidence {
    view: BodyView,
    key: Vec<LabelId>,
    labels: Vec<LabelId>,
    examples: Vec<ExampleRows>,
    entries: Vec<Vec<Gathered>>,
    layout: AssignmentLayout,
}

impl KeyEvidence {
    fn entries_at(&self, ctx:&Ctx<'_>)->Vec<&Gathered> {
        let mut result=Vec::new();
        for (i,example) in self.examples.iter().enumerate().filter(|(_,e)|e.example==ctx.example) {
            if let Ok(assigned)=&example.rows {
                for at in ctx.layout.select(ctx.ordinal,ctx.assignment,&self.layout,assigned) {result.push(&self.entries[i][at]);}
            }
        }
        result
    }

    fn key_of(&self,sub:&BodyView,row:&[TermId])->Option<Box<[TermId]>> {
        self.key.iter().map(|label|sub.column_of(*label).map(|i|row[i])).collect()
    }

    fn contains(&self,sub:&BodyView,row:&[TermId],ctx:&Ctx<'_>)->bool {
        let Some(key)=self.key_of(sub,row) else {return false};
        self.entries_at(ctx).iter().any(|entry|entry.rows.contains_key(&key))
    }

    fn extent(&self,label:LabelId,sub:&BodyView,row:&[TermId],ctx:&Ctx<'_>)->Option<Extent> {
        let slot=self.labels.iter().position(|own|*own==label)?;
        let key=self.key_of(sub,row)?;
        let mut merged=Merged::Unset;
        for entry in self.entries_at(ctx) {
            if entry.stop.is_some() || entry.lost.is_some() {return None;}
            if let Some(slots)=entry.rows.get(&key) {merged.merge(slots[slot].extent());}
        }
        merged.extent()
    }
}

/// Keep the exact compiled key scope and native projected labels, while
/// evaluating each key's own witnesses independently. Evidence from different
/// examples or incompatible determinations never shares a lookup. As in the
/// original derivation, all models that contribute the same native row must
/// agree on its frame; model ordinals from independent queries are not joined.
pub(super) fn key_evidence(decoder:&Decoder<'_>,reads:&Reads<'_>,checked:&CheckedProgram,sub:&BodyView)->arclog::eval::Outcome<Vec<KeyEvidence>> {
    let mut result=Vec::new();
    for key in sub.key_views() {
        let key_labels=key.clause.columns.iter().map(|v|key.paths.labels[v.0 as usize]).collect::<Vec<_>>();
        let views=key.widened()?;
        for view in views {
            let dets=crate::tables::body_tables::dets(checked,&view);
            let examples=crate::tables::body_tables::examples_with_context(decoder,checked,&view,&dets,&reads.work,reads.query_context());
            let mut contents=crate::tables::body_tables::metadata(decoder,checked,&view,0,&dets,examples,reads.tables)?;
            contents.assignment_layout=reads.query_context().layout();
            contents.extents=body_extents_in(decoder,reads,checked,&view,&contents);
            let geom=extent_columns(&contents.columns.iter().map(|c|c.ty.clone()).collect::<Vec<_>>(),&contents.frames);
            let labels=geom.iter().map(|c|contents.columns[*c as usize].label_id.expect("IR columns have scoped labels")).collect();
            let positions=key_labels.iter().map(|l|view.column_of(*l)).collect::<Option<Vec<_>>>();
            let mut entries=Vec::new();
            for (example,e) in contents.examples.iter().enumerate() {
                let mut gathered=Vec::new();
                if let Ok(assigned)=&e.rows {for (at,(_,models)) in assigned.at.iter().enumerate() {
                    let mut entry=Gathered::default();
                    for (model,value) in models.iter().enumerate() {match value {
                        RelationValue::Rows(rows)=>{
                            if let Err(stop)=reads.charge(rows.len(),&view.form) {entry.stop=Some(stop);continue;}
                            if let Some(EntryExtents::Stopped(stop))=contents.extents.as_ref().and_then(|e|e.entry(example,at,model)) {entry.stop=Some(stop.clone());}
                            if let Some(EntryExtents::Lost(reason))=contents.extents.as_ref().and_then(|e|e.entry(example,at,model)) {entry.lose(reason);}
                            let annotation=annotated_rows(&contents,example,at,model,rows);
                            let mut i=0;
                            each_row(rows,&mut |row| {
                                if let Some(positions)=&positions {
                                    let key:Box<[_]>=positions.iter().map(|p|row[*p]).collect();
                                    let slots=entry.rows.entry(key).or_insert_with(||vec![Merged::Unset;geom.len()]);
                                    for (slot,(_,extent)) in slots.iter_mut().zip(&annotation[i]) {slot.merge(*extent);}
                                }
                                i+=1;
                            });
                        },
                        RelationValue::Stopped(stop)=>entry.stop=Some(stop.clone()),
                        RelationValue::Undefined=>entry.lose("key evidence is undefined"),
                    }}
                    gathered.push(entry);
                }}
                entries.push(gathered);
            }
            result.push(KeyEvidence {view,key:key_labels.clone(),labels,examples:contents.examples.into_vec(),entries,layout:contents.assignment_layout.clone()});
        }
    }
    Ok(result)
}

impl Analysis<'_> {
    pub(super) fn key_source_present(&self,source:&ColumnSource,row:&[TermId],ctx:&Ctx<'_>)->Option<bool> {
        let mut owns=false;let mut present=false;
        for key in self.keys {
            if frame_context::node_at_path(&key.view.clause,&key.view.paths,&source.atom).is_some() {
                owns=true;present |= key.contains(self.sub,row,ctx);
            }
        }
        owns.then_some(present)
    }

    pub(super) fn key_stop(&self,ctx:&Ctx<'_>)->Option<Stop> {
        for key in self.keys {
            for e in key.examples.iter().filter(|e|e.example==ctx.example) {
                if let Ok(assigned)=&e.rows {if let Some(stop)=&assigned.stop {return Some(stop.clone());}}
            }
            if let Some(stop)=key.entries_at(ctx).iter().find_map(|entry|entry.stop.clone()) {return Some(stop);}
        }
        None
    }

    pub(super) fn key_fault(&self,ctx:&Ctx<'_>)->Option<String> {
        for key in self.keys {
            for e in key.examples.iter().filter(|e|e.example==ctx.example) {
                if let Err(fault)=&e.rows {return Some(fault_spelled(fault));}
            }
            if let Some(lost)=key.entries_at(ctx).iter().find_map(|entry|entry.lost.clone()) {return Some(lost);}
        }
        None
    }

    /// A hidden key source uses its separately aggregated proof, never a
    /// guessed source row or the key-local variable's numeric id as a column.
    pub(super) fn key_read_extent(&self,source:&ColumnSource,row:&[TermId],ctx:&Ctx<'_>)->Option<Option<Extent>> {
        let mut found=Merged::Unset;
        let mut owns=false;
        for key in self.keys {
            let Some((atom,paths))=frame_context::read_at(&key.view.clause,&key.view.paths,&source.atom) else {continue};
            owns=true;
            let coordinates=ReadCoordinates::new(matches!(atom.source,AtomSource::Fact(arclog::program::FactRelation::Input)),
                self.checked.program.reads_lifted(&source.atom));
            let Some(position)=coordinates.argument(source.column) else {return Some(None)};
            let argument=atom.arguments.0.iter().find(|(i,_)|i.0==position).map(|(_,a)|a);
            let extent=match argument {
                Some(Argument::Variable(v))=>key.extent(paths.labels[v.0 as usize],self.sub,row,ctx),
                _=>None,
            };
            if key.contains(self.sub,row,ctx) {found.merge(extent);}
        }
        owns.then(||found.extent())
    }

    pub(super) fn key_made_extent(&self,at:&NodePath,label:LabelId,row:&[TermId],ctx:&Ctx<'_>)->Option<Option<Extent>> {
        let mut owns=false;let mut found=Merged::Unset;
        for key in self.keys {
            // The shared native source lookup deliberately handles relation
            // atoms only. Makers are lib atoms, identified by their original
            // AST path within this compiled key scope.
            if frame_context::node_at_path(&key.view.clause,&key.view.paths,at).is_some() {
                owns=true;
                if key.contains(self.sub,row,ctx) {found.merge(key.extent(label,self.sub,row,ctx));}
            }
        }
        owns.then(||found.extent())
    }
}
