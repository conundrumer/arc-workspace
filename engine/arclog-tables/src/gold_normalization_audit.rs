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
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use arclog::clock::Stopwatch;

/// Only the shared Python JsonlWriter owns persistent records. Native stdout
/// pipes are a transport; acquisition keys and comparison policy stay native.
struct FramedJournal {
    child: Child,
    input: Option<ChildStdin>,
    replies: BufReader<ChildStdout>,
    committed: u64,
}
impl FramedJournal {
    fn reply(&mut self) -> Result<Value, String> {
        let mut line = String::new();
        if self.replies.read_line(&mut line).map_err(|e| e.to_string())? == 0 {
            return Err("framed normalization journal closed unexpectedly".into());
        }
        serde_json::from_str(&line).map_err(|e| e.to_string())
    }
    fn open(output: &str) -> Result<(Self, Vec<Value>), String> {
        if !output.ends_with(".jsonl.zst") {
            return Err("next normalization audit requires a NEW .jsonl.zst output; do not change an existing run's format".into());
        }
        let python = std::env::var("GOLD_PRUNE_PYTHON")
            .map_err(|_| "set GOLD_PRUNE_PYTHON to the interpreter with study's framed-JSONL dependency")?;
        let helper = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../model/study/ast/run/mech/gold_normalization_journal.py");
        let mut child = Command::new(python).args(["-B"])
            .arg(helper).arg(output).stdin(Stdio::piped()).stdout(Stdio::piped())
            .stderr(Stdio::inherit()).spawn().map_err(|e| e.to_string())?;
        let input = child.stdin.take();
        let replies = BufReader::new(child.stdout.take().ok_or("journal stdout missing")?);
        let mut journal = Self { child, input, replies, committed: 0 };
        let opened = journal.reply()?;
        if opened["event"] != "opened" { return Err("journal open protocol differs".into()); }
        journal.committed = opened["committed_lines"].as_u64().ok_or("journal committed count missing")?;
        let mut previous = Vec::new();
        let mut own_rows = 0u64;
        loop {
            let message = journal.reply()?;
            match message["event"].as_str() {
                Some("previous") => { own_rows += 1; previous.push(message["row"].clone()); },
                Some("previous_external") => previous.push(message["row"].clone()),
                Some("ready") => break,
                _ => return Err("journal resume protocol differs".into()),
            }
        }
        if own_rows != journal.committed {
            return Err("journal resume count differs from committed_lines".into());
        }
        Ok((journal, previous))
    }
    fn append(&mut self, row: &Value) -> Result<(), String> {
        let input = self.input.as_mut().ok_or("closed journal")?;
        writeln!(input, "{row}").map_err(|e| e.to_string())?;
        input.flush().map_err(|e| e.to_string())?;
        let message = self.reply()?;
        if message["event"] != "committed" || message["committed_lines"].as_u64() != Some(self.committed + 1) {
            return Err("journal commit acknowledgement differs".into());
        }
        self.committed += 1;
        Ok(())
    }
    fn close(mut self) -> Result<(), String> {
        drop(self.input.take());
        let status = self.child.wait().map_err(|e| e.to_string())?;
        if !status.success() { return Err(format!("framed normalization journal failed: {status}")); }
        Ok(())
    }
}

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
        let stopped = |v: &Assigned<Vec<RelationValue>>| {
            v.stop.is_some() || v.at.iter().any(|(_, models)| models.iter().any(|m| matches!(m,RelationValue::Stopped(_))))
        };
        if stopped(av) || stopped(bv) {
            let detail = |v: &Assigned<Vec<RelationValue>>| json!({
                "walk_stop":format!("{:?}",v.stop),
                "model_stops":v.at.iter().flat_map(|(_,m)|m.iter()).filter_map(|m|match m {
                    RelationValue::Stopped(stop)=>Some(format!("{stop:?}")),_=>None
                }).collect::<Vec<_>>()});
            return Err(format!("stopped comparison at {:?}: original={} normalized={}",a.example,detail(av),detail(bv)));
        }
        if a.example != b.example || !assigned_same(av, bv) {
            return Err(format!(
                "rows or model/assignment coverage differ at {:?}",
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
fn audit(item: &Value) -> (Value, Result<Value, String>) {
    let mut progress=json!({"stage":"normalize"});
    let result=(|| -> Result<Value,String> {
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
    progress=json!({"stage":"prefix_check","removed":edits.len(),"removed_atom_paths":report["removed_atom_paths"],
        "normalized_program_sexp":report["normalized_program_sexp"]});
    let prefix_count = check_prefixes(&normalized, registry)?;
    progress["prefixes"]=json!(prefix_count);
    if edits.is_empty() {
        return Ok(json!({"removed":0,"prefixes":prefix_count,"queries":0,"examples":0,
            "normalized_program_sexp":report["normalized_program_sexp"],
            "row_equivalence":"identical checked program; reflexivity, no evaluation required"}));
    }
    let output_only=std::env::var("GOLD_PRUNE_SCOPE").as_deref()==Ok("output");
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
    if !output_only {
    for (af, bf) in a.forms.iter().zip(&b.forms) {
        if af.readable != bf.readable || af.path != bf.path {
            return Err("readable relation inventory differs".into());
        }
        for &slot in &af.readable {
            let ar = graph_relation(original.checked(), registry, &af.path, &a.relations[slot])
                .ok_or("original relation absent")?;
            let br = graph_relation(normalized.checked(), registry, &bf.path, &b.relations[slot])
                .ok_or("normalized relation absent")?;
            progress["stage"]=json!(format!("relation {:?} slot {slot}",af.path));
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
    }
    // Include OUT even though it declares no relation slot.
    progress["stage"]=json!("OUT");
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
    if !output_only {
    for path in bodies {
        progress["stage"]=json!(format!("body {path:?}"));
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
    }
    Ok(
        json!({"removed":edits.len(),"prefixes":prefix_count,"queries":queries,"examples":examples,
        "normalized_program_sexp":report["normalized_program_sexp"],"scope":if output_only{"OUT task examples"}else{"all readable relations, OUT, changed BODY"}}),
    )
    })();
    (progress,result)
}

#[test]
#[ignore = "explicit all-gold qualification; requires manifest and output paths"]
fn gold_normalization_audit() {
    let manifest = std::env::var("GOLD_PRUNE_MANIFEST").expect("GOLD_PRUNE_MANIFEST");
    let output = std::env::var("GOLD_PRUNE_OUTPUT").expect("GOLD_PRUNE_OUTPUT");
    let items: Value = serde_json::from_slice(&std::fs::read(manifest).unwrap()).unwrap();
    let items = items.as_array().unwrap();
    assert!(!items.is_empty());
    let expected_removed:usize=items.iter().map(|v|v["expected_matches"].as_array().unwrap().len()).sum();
    let expected_changed=items.iter().filter(|v|!v["expected_matches"].as_array().unwrap().is_empty()).count();
    let acquisition_code=std::env::var("GOLD_PRUNE_ACQUISITION_KEY").ok();
    let scope=std::env::var("GOLD_PRUNE_SCOPE").unwrap_or_else(|_|"all".into());
    let (mut writer, committed_rows) = FramedJournal::open(&output).expect("open framed normalization audit");
    let mut previous=std::collections::BTreeMap::new();
    if acquisition_code.is_some() {
        for row in committed_rows {
            if let Some(key)=row.get("acquisition_key") {previous.insert(key.to_string(),row);}
        }
    }
    let start = Stopwatch::start();
    let mut errors = 0;
    let mut removed = 0;
    let mut changed = 0;
    for (i, item) in items.iter().enumerate() {
        let now = Stopwatch::start();
        let key=json!({"request":item,"scope":scope,"code":acquisition_code});
        let row=if let Some(row)=previous.get(&key.to_string()) {
            row.clone()
        } else {
            let (normalization,evaluated)=audit(item);
            let result = match evaluated {
                Ok(value)=>json!({"status":"complete","result":value}),
                Err(e)=>json!({"status":if e.starts_with("stopped comparison"){"unavailable_bound"}else{"unavailable_or_different"},"reason":e}),
            };
            let row=json!({"task":item["task"],"case":item["case"],"program_sha256":item["program_sha256"],
                "seconds":now.elapsed().seconds(),"outcome":result,"normalization":normalization,"acquisition_key":key});
            writer.append(&row).expect("commit framed normalization result");row
        };
        if let Some(n)=row["normalization"]["removed"].as_u64() {removed+=n;changed+=usize::from(n>0);}
        if row["outcome"]["status"]!="complete" {errors+=1;}
        eprintln!(
            "gold-normalization {}/{} elapsed {:.1}s ETA {:.1}s errors {}",
            i + 1,
            items.len(),
            start.elapsed().seconds(),
            start.elapsed().seconds() * (items.len() - i - 1) as f64 / (i + 1) as f64,
            errors
        );
    }
    writer.close().expect("close framed normalization journal");
    assert_eq!((errors, removed, changed), (0, expected_removed as u64, expected_changed));
}
