//! Reader names from the same case-file pipeline and stream writer as lm/export.
use std::path::Path;
use serde_json::{Value,json};
use crate::check::CheckedProgram;
use crate::program::{DeclaredName,ProgramRelation,RelationRef};
use crate::registry::Registry;
use crate::stream::{DecodeSettings,Emitter,Vocabulary,written_stream};
use crate::stream::corpus::{solver_streams,WantedCases,token_ids};

fn identity(checked:&CheckedProgram,settings:&DecodeSettings)->Result<(Value,Vec<ProgramRelation>),String> {
    let vocabulary=Vocabulary::new(Registry::get(),settings);
    let stream=written_stream(checked,&vocabulary).map_err(|d|super::diagnostics_text(&[d]))?;
    let tokens=token_ids(&stream.tokens,&vocabulary);
    Ok((json!({"ids":tokens.iter().map(|(id,_)|id).collect::<Vec<_>>(),
        "model":tokens.iter().map(|(_,e)|u8::from(*e==Emitter::Model)).collect::<Vec<_>>()}),stream.relations))
}

/// A source map is accepted only for the exact stream made from these sources.
/// Source changes and wrong cases fail; no matching of printed programs occurs.
pub fn from_case(checked:&CheckedProgram,settings:&DecodeSettings,corpus:&Path,task:&str,case:&str)->Result<Value,String> {
    let vocabulary=Vocabulary::new(Registry::get(),settings);
    let mut cases=solver_streams(corpus,task,WantedCases::Named(case),&vocabulary,false)?;
    if cases.len()!=1 {return Err("expected exactly one named source case".into());}
    let source=cases.remove(0).stream?;
    let tokens=token_ids(&source.tokens,&vocabulary);
    let source_identity=json!({"ids":tokens.iter().map(|(id,_)|id).collect::<Vec<_>>(),
        "model":tokens.iter().map(|(_,e)|u8::from(*e==Emitter::Model)).collect::<Vec<_>>()});
    let (actual,relations)=identity(checked,settings)?;
    if actual!=source_identity || relations.len()!=source.relations.len() {
        return Err("source case stream differs from the checked gold stream; refusing relation-name attribution".into());
    }
    let names=source.relations.iter().zip(&relations).enumerate().map(|(slot,(source,native))| {
        let reference=match source {ProgramRelation::Declared(n)=>RelationRef::Declared(n.clone()),ProgramRelation::Output(n)=>RelationRef::Output(n.clone())};
        let display=crate::write::relation_ref(&reference,|n|match n {DeclaredName::Written(n)=>n.to_string(),DeclaredName::Slot(n)=>format!("&r{n}")});
        json!({"relation_slot":slot,"native_relation":super::render::program_relation(native),
            "source_relation":super::render::program_relation(source),"display_name":display})
    }).collect::<Vec<_>>();
    Ok(json!({"schema":"arclog-study-relation-names-v1","task":task,"case":case,"corpus":corpus.to_string_lossy(),
        "stream_identity":source_identity,"relations":names,
        "provenance":"stream::corpus::solver_streams Named, including case-file overrides and zero-column lowering; names captured from WrittenStream.relations in the same writer run"}))
}

/// Attach names to a structured export, guarded against the original gold
/// stream. Mutants retain native declaration identities, regardless of their
/// own writer's relation-slot order; display names never affect evaluation.
pub fn attach(export:&mut Value,gold:&CheckedProgram,settings:&DecodeSettings,names:&Value)->Result<(),String> {
    if names["schema"]!="arclog-study-relation-names-v1" {return Err("unknown relation source-name schema".into());}
    let (actual,relations)=identity(gold,settings)?;
    if actual!=names["stream_identity"] {return Err("relation source-name map belongs to another gold stream".into());}
    let rows=names["relations"].as_array().ok_or("relation source names must be an array")?;
    if rows.len()!=relations.len() {return Err("relation source-name count differs from gold writer slots".into());}
    for (slot,(row,relation)) in rows.iter().zip(&relations).enumerate() {
        if row["relation_slot"].as_u64()!=Some(slot as u64) || row["native_relation"]!=super::render::program_relation(relation) || !row["display_name"].is_string() {
            return Err("relation source-name map does not preserve native slot identity".into());
        }
    }
    if let Some(native)=export["definitions"]["native_relations"].as_array_mut() {
        for relation in native {
            if let Some(source)=rows.iter().find(|r|r["native_relation"]==relation["relation"]) {
                relation["display_name"]=source["display_name"].clone();
                relation["source_relation"]=source["source_relation"].clone();
            }
        }
    }
    export["relation_source_names"]=names.clone();
    Ok(())
}
