//! Native tables of checked IR queries, with the export's metadata and caps.
use super::*;
use arclog::eval::body_view::BodyView;

pub fn dets(checked:&CheckedProgram,view:&BodyView)->Vec<Det> {
    arclog::study::render_choices::body_dets(checked,view)
}

pub fn models(evaluation:&Evaluation<'_>,view:&BodyView,example:Option<Example>)->Result<Vec<RelationValue>,End> {
    let mut values=Vec::new();
    let end=evaluation.body_models(view,example,&mut |v|{values.push(v.clone());ControlFlow::Continue(())}).map_err(End::Fault)?;
    if let ModelsEnd::Stopped(stop)=end {values.push(RelationValue::Stopped(stop));}
    Ok(values)
}

pub fn examples(decoder:&Decoder<'_>,checked:&CheckedProgram,view:&BodyView,dets:&[Det],work:&TableWork)->Vec<ExampleRows> {
    let root=checked.program.nodes_of(&view.form).first().copied();
    decoder.examples_of(view.scope).into_iter().map(|example|ExampleRows {example,rows:match root {
        Some(root)=>decoder.assigned(checked,root,dets,Some(work),&mut |evaluation|models(evaluation,view,example)),
        None=>Err(RunFault {message:"checked body owner has no dependency node".into(),form:view.form.clone()}),
    }}).collect()
}

pub fn contents(decoder:&Decoder<'_>,checked:&CheckedProgram,view:&BodyView,slot:u32,dets:&[Det],examples:Vec<ExampleRows>,work:&TableWork,earlier:&[&Table])->Outcome<Contents> {
    let fault=|message:&str|RunFault {message:message.into(),form:view.form.clone()};
    let named=label_names(&checked.program.program,decoder.registry()).swap_remove(view.form.0[0].0 as usize);
    let columns=view.clause.columns.iter().enumerate().map(|(i,v)| {
        let label=view.paths.labels[v.0 as usize];
        TableColumn {name:format!("c{i}"),ty:view.clause.variables[v.0 as usize].ty.clone(),slot:Some(i as u32),label_id:Some(label),label:named.iter().find(|(id,_)|*id==label).map(|(_,name)|name.clone())}
    }).collect();
    let dets=dets.iter().map(|d| {
        let ty=checked.types.columns(&GraphRelation {node:d.node,output:None}).ok_or_else(||fault("DET has no column types"))?;
        Ok(TableDet {relation:d.relation.clone(),types:ty.into(),columns:checked.program.row_paths(d.node).filter(|p|p.len()==ty.len()).map(Vec::into_boxed_slice)})
    }).collect::<Outcome<Box<[_]>>>()?;
    // Even an unused held dependency must keep its original schema. Reject
    // incompatible assignment evidence before it reaches the packed writer;
    // do not attach original cells to a mutant's shorter DET column list.
    for example in &examples {
        if let Ok(assigned) = &example.rows {
            for (values, _) in &assigned.at {
                if values.len() != dets.len() {
                    return Err(fault("body assignment DET count differs from its checked schema"));
                }
                for ((name, rows), det) in values.iter().zip(dets.iter()) {
                    if name != &det.relation || usize::from(rows.arity()) != det.types.len() {
                        return Err(fault(&format!("body assignment DET {name:?} has native arity {}, incompatible with checked DET {:?} ({} columns)", rows.arity(), det.relation, det.types.len())));
                    }
                }
            }
        }
    }
    let over=examples.iter().any(|e|e.rows.as_ref().is_ok_and(|a|a.at.iter().flat_map(|(_,m)|m).any(|v|matches!(v,RelationValue::Rows(r) if r.len()>decoder.settings().projection_cap))));
    let projections=if over {super::projections_of(decoder,&examples,&view.form,work)} else {None};
    let flows=crate::flows::body_column_flows(checked,&view.clause,&view.paths,decoder.registry()).into();
    let mut contents=Contents {relation:TableRelation::Slot(slot),columns,dets,examples:examples.into(),projections,name:String::new(),flows,rows:None,depth:checked.program.nodes_of(&view.form).iter().map(|n|checked.program.depth(*n)).max().unwrap_or(0),keys:Vec::new(),selected:SelectedColumns::default(),frames:Vec::new(),extents:None};
    contents.frames=column_frames(&names_of(decoder.registry(),earlier),&contents);
    contents.extents=crate::extents::body_extents(decoder,earlier,checked,view,&contents);
    Ok(contents)
}
