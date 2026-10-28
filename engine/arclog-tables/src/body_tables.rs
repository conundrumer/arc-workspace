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
    examples_with_context(decoder, checked, view, dets, work, AssignmentContext::Search)
}

pub(crate) fn examples_with_context(decoder:&Decoder<'_>,checked:&CheckedProgram,view:&BodyView,dets:&[Det],work:&TableWork,context:AssignmentContext<'_>)->Vec<ExampleRows> {
    match checked.program.nodes_of(&view.form).first().copied() {
        Some(root) => assignment_context::examples(decoder, checked, view.scope, root, dets, work, context,
            &mut |evaluation, example| models(evaluation, view, example)),
        None => decoder.examples_of(view.scope).into_iter().map(|example| ExampleRows {example, rows:Err(RunFault {message:"checked body owner has no dependency node".into(),form:view.form.clone()})}).collect(),
    }
}

pub fn contents(decoder:&Decoder<'_>,checked:&CheckedProgram,view:&BodyView,slot:u32,dets:&[Det],examples:Vec<ExampleRows>,work:&TableWork,earlier:&[&Table])->Outcome<Contents> {
    contents_with_context(decoder, checked, view, slot, dets, examples, work, earlier, AssignmentContext::Search)
}

pub(crate) fn contents_with_context(decoder:&Decoder<'_>,checked:&CheckedProgram,view:&BodyView,slot:u32,dets:&[Det],examples:Vec<ExampleRows>,work:&TableWork,earlier:&[&Table],context:AssignmentContext<'_>)->Outcome<Contents> {
    let mut contents = metadata(decoder, checked, view, slot, dets, examples, earlier)?;
    contents.assignment_layout=context.layout();
    super::add_projections(decoder, &mut contents, &view.form, work);
    contents.extents=crate::extents::body_extents_with_context(decoder,earlier,checked,view,&contents,context);
    Ok(contents)
}

/// The exact IR interface and provenance, without recursive annotation or
/// projection evaluation. Key evidence uses this adapter too.
pub(crate) fn metadata(decoder:&Decoder<'_>,checked:&CheckedProgram,view:&BodyView,slot:u32,dets:&[Det],examples:Vec<ExampleRows>,earlier:&[&Table])->Outcome<Contents> {
    let named=label_names(&checked.program.program,decoder.registry()).swap_remove(view.form.0[0].0 as usize);
    let columns=view.clause.columns.iter().enumerate().map(|(i,v)| {
        let label=view.paths.labels[v.0 as usize];
        TableColumn {name:format!("c{i}"),ty:view.clause.variables[v.0 as usize].ty.clone(),slot:Some(i as u32),label_id:Some(label),label:named.iter().find(|(id,_)|*id==label).map(|(_,name)|name.clone())}
    }).collect();
    let flows=crate::flows::body_column_flows(checked,&view.clause,&view.paths,decoder.registry()).into();
    let mut contents=super::metadata(checked,&view.form,TableRelation::Slot(slot),columns,dets,examples,flows)?;
    contents.depth=checked.program.nodes_of(&view.form).iter().map(|n|checked.program.depth(*n)).max().unwrap_or(0);
    contents.frames=column_frames(&names_of(decoder.registry(),earlier),&contents);
    Ok(contents)
}
