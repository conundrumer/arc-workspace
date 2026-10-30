//! Explicit corpus qualification, invoked only by the ignored audit test.
//! Compares native relations in one task intern namespace, never decoded cells.
use super::*;
use arclog::check::{
    PrefixResult, SolverClauses,
    prefix::{check_prefix, prefixes},
};
use arclog::program::{Node, Program};
use arclog::resolver::{SolverScope, resolve};
use arclog::session::{SessionBound, TaskSession, same_rows};
use arclog::stream::{DecodeSettings, Vocabulary, written_stream};
use arclog::study::StudyProgram;
use serde_json::{Value, json};
use std::io::Write;
use std::time::Instant;

fn models_same(a: &[RelationValue], b: &[RelationValue]) -> bool {
    let mut used = vec![false; b.len()];
    a.len() == b.len()
        && a.iter().all(|a| {
            let found = b.iter().enumerate().position(|(i, b)| {
                !used[i]
                    && match (a, b) {
                        (RelationValue::Rows(a), RelationValue::Rows(b)) => same_rows(a, b),
                        (RelationValue::Undefined, RelationValue::Undefined) => true,
                        _ => false, // A stop is not evidence of equality.
                    }
            });
            if let Some(i) = found {
                used[i] = true;
                true
            } else {
                false
            }
        })
}
fn assigned_same(a: &Assigned<Vec<RelationValue>>, b: &Assigned<Vec<RelationValue>>) -> bool {
    let mut used = vec![false; b.at.len()];
    a.stop.is_none()
        && b.stop.is_none()
        && a.at.len() == b.at.len()
        && a.at.iter().all(|(aa, av)| {
            let found = b.at.iter().enumerate().position(|(i, (ba, bv))| {
                !used[i]
                    && aa.len() == ba.len()
                    && aa.iter().all(|(name, value)| {
                        ba.iter()
                            .any(|(other, v)| name == other && same_rows(value, v))
                    })
                    && models_same(av, bv)
            });
            if let Some(i) = found {
                used[i] = true;
                true
            } else {
                false
            }
        })
}
fn compare_examples(a: &[ExampleRows], b: &[ExampleRows]) -> Result<usize, String> {
    if a.len() != b.len() {
        return Err("example coverage differs".into());
    }
    for (a, b) in a.iter().zip(b) {
        let (Ok(av), Ok(bv)) = (&a.rows, &b.rows) else {
            return Err(format!("query fault: {:?} / {:?}", a.rows, b.rows));
        };
        if a.example != b.example || !assigned_same(av, bv) {
            return Err(format!(
                "rows, model/assignment coverage differ or are stopped at {:?}",
                a.example
            ));
        }
    }
    Ok(a.len())
}
fn check_prefixes(program: &StudyProgram, registry: &Registry) -> Result<usize, String> {
    let forms = &program.program().value().forms;
    let mut count = 0;
    for (i, form) in forms.iter().enumerate() {
        for prefix in prefixes(form) {
            let mut partial = forms[..i].to_vec();
            partial.push(prefix.partial.clone());
            let ast = Node::new(Program {
                forms: partial.into(),
            });
            let resolved = Arc::new(resolve(&ast, None, &SolverScope::default(), registry).value);
            let clauses = SolverClauses::of_shared_program(Arc::clone(&resolved));
            for (id, result) in check_prefix(&resolved, &clauses, registry, prefix.open().as_ref())
            {
                if let PrefixResult::Refuse(refusals) = result {
                    return Err(format!("prefix {i} {:?} {id:?}: {refusals:?}", prefix.end));
                }
            }
            count += 1;
        }
    }
    Ok(count)
}
fn audit(item: &Value) -> Result<Value, String> {
    let registry = Registry::get();
    let settings = DecodeSettings::default();
    let text = item["program"].as_str().ok_or("missing program")?;
    let original = StudyProgram::from_sexp(text, registry)?;
    let report = original.static_prune_report(registry, true)?;
    if report["matches"] != item["expected_matches"] {
        return Err("matches differ from gold-matches.md population".into());
    }
    let edits = report["removed_atom_paths"]
        .as_array()
        .ok_or("missing removed paths")?
        .iter()
        .map(|path| {
            let steps = path
                .as_array()
                .ok_or("invalid atom path")?
                .iter()
                .map(|v| {
                    v.as_u64()
                        .and_then(|n| u32::try_from(n).ok())
                        .map(arclog::program::path::PathStep)
                        .ok_or("invalid path step")
                })
                .collect::<Result<Vec<_>, _>>()?;
            Ok::<_, &str>(arclog::mutation::edit::AtomEdit {
                at: NodePath(steps.into()),
                replacement: None,
                kind: "delete",
                choice_kind: "static_valid",
            })
        })
        .collect::<Result<Vec<_>, _>>()?;
    let normalized = if edits.is_empty() {
        original.clone()
    } else {
        StudyProgram::from_sexp(
            report["normalized_program_sexp"]
                .as_str()
                .ok_or("missing normalized text")?,
            registry,
        )?
    };
    let prefix_count = check_prefixes(&normalized, registry)?;
    let task = arclog::task::read_task(std::path::Path::new(
        item["task_file"].as_str().ok_or("missing task")?,
    ))
    .map_err(|e| format!("{e:?}"))?;
    let session = TaskSession::new(
        SessionBound {
            bytes: study_pair::STUDY_SESSION_BYTES,
        },
        settings.caps,
    );
    let constructions = arclog_constructions::shared()?;
    let decoder = Decoder::new(&task, &session, registry, constructions, &settings);
    let vocabulary = Vocabulary::new(registry, &settings);
    let a = written_stream(original.checked(), &vocabulary).map_err(|d| d.message.to_string())?;
    let b = written_stream(normalized.checked(), &vocabulary).map_err(|d| d.message.to_string())?;
    if a.relations != b.relations {
        return Err("normalization changed declared relations".into());
    }
    let mut queries = 0;
    let mut examples = 0;
    for (af, bf) in a.forms.iter().zip(&b.forms) {
        if af.readable != bf.readable || af.path != bf.path {
            return Err("readable relation inventory differs".into());
        }
        for &slot in &af.readable {
            let ar = graph_relation(original.checked(), registry, &af.path, &a.relations[slot])
                .ok_or("original relation absent")?;
            let br = graph_relation(normalized.checked(), registry, &bf.path, &b.relations[slot])
                .ok_or("normalized relation absent")?;
            let work = decoder.table_work();
            let av = relation_examples(
                &decoder,
                original.checked(),
                &ar,
                &relation_dets(original.checked(), ar.node),
                &work,
            );
            let work = decoder.table_work();
            let bv = relation_examples(
                &decoder,
                normalized.checked(),
                &br,
                &relation_dets(normalized.checked(), br.node),
                &work,
            );
            examples += compare_examples(&av, &bv)?;
            queries += 1;
        }
    }
    // Include OUT even though it declares no relation slot.
    let ar = arclog::eval::output_relation(original.checked()).ok_or("original OUT absent")?;
    let br = arclog::eval::output_relation(normalized.checked()).ok_or("normalized OUT absent")?;
    let work = decoder.table_work();
    let av = relation_examples(
        &decoder,
        original.checked(),
        &ar,
        &relation_dets(original.checked(), ar.node),
        &work,
    );
    let work = decoder.table_work();
    let bv = relation_examples(
        &decoder,
        normalized.checked(),
        &br,
        &relation_dets(normalized.checked(), br.node),
        &work,
    );
    examples += compare_examples(&av, &bv)?;
    queries += 1;
    let mut bodies = std::collections::BTreeSet::new();
    for edit in &edits {
        let path = NodePath(edit.at.0[..edit.at.0.len() - 1].into());
        bodies.insert(path);
    }
    for path in bodies {
        let mapped = arclog::mutation::edit::mapped(&path, &edits).ok_or("deleted body owner")?;
        let av = arclog::eval::body_view::BodyView::at(original.checked(), &path)
            .map_err(|e| format!("{e:?}"))?;
        let bv = arclog::eval::body_view::BodyView::at(normalized.checked(), &mapped)
            .map_err(|e| format!("{e:?}"))?;
        let work = decoder.table_work();
        let aa = body_tables::examples(
            &decoder,
            original.checked(),
            &av,
            &body_tables::dets(original.checked(), &av),
            &work,
        );
        let work = decoder.table_work();
        let bb = body_tables::examples(
            &decoder,
            normalized.checked(),
            &bv,
            &body_tables::dets(normalized.checked(), &bv),
            &work,
        );
        examples += compare_examples(&aa, &bb)?;
        queries += 1;
    }
    Ok(
        json!({"removed":edits.len(),"prefixes":prefix_count,"queries":queries,"examples":examples,
        "normalized_program_sexp":report["normalized_program_sexp"]}),
    )
}

#[test]
#[ignore = "explicit all-gold qualification; requires manifest and output paths"]
fn gold_normalization_audit() {
    let manifest = std::env::var("GOLD_PRUNE_MANIFEST").expect("GOLD_PRUNE_MANIFEST");
    let output = std::env::var("GOLD_PRUNE_OUTPUT").expect("GOLD_PRUNE_OUTPUT");
    let items: Value = serde_json::from_slice(&std::fs::read(manifest).unwrap()).unwrap();
    let items = items.as_array().unwrap();
    assert_eq!(items.len(), 1638);
    let mut writer = std::fs::File::create(output).unwrap();
    let start = Instant::now();
    let mut errors = 0;
    let mut removed = 0;
    let mut changed = 0;
    for (i, item) in items.iter().enumerate() {
        let now = Instant::now();
        let result = match audit(item) {
            Ok(value) => {
                let n = value["removed"].as_u64().unwrap();
                removed += n;
                changed += usize::from(n > 0);
                json!({"status":"complete","result":value})
            }
            Err(e) => {
                errors += 1;
                json!({"status":"unavailable_or_different","reason":e})
            }
        };
        writeln!(writer,"{}",json!({"task":item["task"],"case":item["case"],"program_sha256":item["program_sha256"],"seconds":now.elapsed().as_secs_f64(),"outcome":result})).unwrap();
        writer.flush().unwrap();
        eprintln!(
            "gold-normalization {}/{} elapsed {:.1}s ETA {:.1}s errors {}",
            i + 1,
            items.len(),
            start.elapsed().as_secs_f64(),
            start.elapsed().as_secs_f64() * (items.len() - i - 1) as f64 / (i + 1) as f64,
            errors
        );
    }
    assert_eq!((errors, removed, changed), (0, 41, 35));
}
