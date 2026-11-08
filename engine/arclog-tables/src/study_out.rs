//! Complete conditional OUT values at a held assignment. No FITS search.
use super::*;

fn grid_json(grid: &Grid) -> Value {
    json!(grid.rows().iter().map(|row| row.iter().map(|c|c.digit()).collect::<Vec<_>>()).collect::<Vec<_>>())
}

pub(super) fn train(e: &Evaluation<'_>, output: &GraphRelation, judge: &judgement::TrainJudge<'_>, budget: &mut Budget<'_>) -> Result<Value, End> {
    let mut out = Vec::new();
    for ((example, pair), candidates) in e.task.examples().zip(e.task.train.iter()).zip(&judge.pairs) {
        let mut models = Vec::new();
        let mut observed = judgement::ModelSet::default();
        let mut model_end = None;
        let end = e.models(output, Some(example), &mut |value| {
            let detail = match value {
                RelationValue::Stopped(stop) => { model_end = Some(End::Stop(stop.clone())); stopped(stop) }
                RelationValue::Undefined => {observed.observe(None);json!({"status":"complete","value_kind":"undefined","equals":false,
                    "grid_defined":false,"differing_cells":pair.output.rows().iter().map(|r|r.len()).sum::<usize>(),"reason":"undefined OUT"})},
                RelationValue::Rows(value) => {
                    let packed = match out_rows(value,budget,e.program.program.form_of(output.node)) {
                        Ok(rows) => rows,
                        Err(end) => {model_end=Some(end);return ControlFlow::Break(());}
                    };
                    let decoded = packed.iter().map(|row| row.iter().zip(["Position","Color"]).map(|(term,ty)|
                        arclog::study::render_terms::decode(ty,i64::from(*term),e.registry).map(|mut cell| {
                            if ty=="Position" {
                                // OUT positions retain their reference extent
                                // even when colors conflict or no whole grid
                                // can be read. Never substitute expected_grid.
                                let extent=crate::extents::position_extent(Term::encode_number(*term as i32),&arclog::types::ValueType::Position);
                                cell["extent_status"]=json!(if extent.is_some(){"resolved"}else{"unresolved"});
                                cell["extent"]=json!(extent.map(|x|[x.rows,x.columns]));
                            }
                            cell
                        })
                    ).collect::<Result<Vec<_>,String>>()).collect::<Result<Vec<_>,String>>();
                    let decoded = match decoded {
                        Ok(v) => v,
                        Err(message) => {model_end=Some(End::Fault(fault(message,e.program.program.form_of(output.node))));return ControlFlow::Break(());}
                    };
                    match read_grid(value,GridColumns::OUT) {
                        Some(grid) => {
                            let detail=json!({"status":"complete","value_kind":"rows","packed_rows":packed,"rows":decoded,
                            "grid_defined":true,"grid":grid_json(&grid),"equals":grid==pair.output,
                            "differing_cells":differences(&grid,&pair.output)});
                            observed.observe(Some(grid));detail
                        },
                        None => {observed.observe(None);json!({"status":"complete","value_kind":"rows","packed_rows":packed,"rows":decoded,
                            "grid_defined":false,"grid":null,"equals":false,
                            "differing_cells":invalid_differences(value,&pair.output),"reason":"OUT rows do not define a grid"})},
                    }
                }
            };
            models.push(detail);
            ControlFlow::Continue(())
        }).map_err(End::Fault)?;
        if let Some(end) = model_end {return Err(end);}
        if let ModelsEnd::Stopped(stop) = end {return Err(End::Stop(stop));}
        let mut comparison=observed.finish(candidates);
        comparison["example"]=json!(example.index());
        comparison["expected_grid"]=grid_json(&pair.output);
        comparison["models"]=json!(models);
        out.push(comparison);
    }
    Ok(json!(out))
}
