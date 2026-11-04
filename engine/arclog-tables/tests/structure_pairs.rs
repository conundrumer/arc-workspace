//! The structure of the bodies of the tables of a program (`arclog_tables::structure`) is the same
//! under an edit of the program that changes no name or order the author chose.

use std::collections::BTreeMap;
use std::path::Path;

use arclog::decode::corpus::read_task_files;
use arclog::eval::join::Materializer;
use arclog::registry::Registry;
use arclog::session::{SessionBound, TaskSession};
use arclog::stream::DecodeSettings;
use arclog::study::StudyProgram;
use arclog_tables::identity::{identify, Identities};
use arclog_tables::tables::{evidence_tables, study_pair};
use serde_json::Value;

/// The tables of `text` on `task`, as the identities and the structure give them, with each table number replaced by the
/// identity of the table it names: `ident -> sorted list of (columns, bodies, instance, column symmetries)`.
fn signature(task: &str, tasks: &Path, text: &str, cap: u64) -> Result<BTreeMap<String, Vec<String>>, String> {
    let registry = Registry::get();
    let (read, _judged) = read_task_files(tasks, task)?;
    let settings = DecodeSettings { table_work_cap: cap, ..DecodeSettings::default() };
    let session = TaskSession::new(SessionBound { bytes: study_pair::STUDY_SESSION_BYTES }, settings.caps);
    let constructions = arclog_constructions::shared()?;
    let evidence = evidence_tables(&read, registry);
    let mut cache = study_pair::PairCache::with_byte_bound(true, study_pair::STUDY_SESSION_BYTES);
    let program = StudyProgram::from_sexp(text, registry)?;
    cache.activate(&program);
    let limits = settings.operation_limits();
    let (_, tables) = study_pair::gold_tables_cached_in(&program, &read, &session, constructions, &settings, &mut cache, &limits);
    let _ = Materializer::new(&session, &limits);
    let written = program.written_stream(registry, &settings).map_err(|d| d.message.to_string())?;
    let ids = identify(program.checked(), registry, &written.relations, &evidence, &tables);
    Ok(signature_of(&ids))
}

/// `value` with each table number replaced by that table's identity.
fn renumbered(value: &mut Value, ids: &Identities) {
    let name = |number: i64| usize::try_from(number).ok().and_then(|at| ids.tables.get(at)).cloned().unwrap_or_else(|| "-".into());
    match value {
        Value::Object(map) => {
            for (key, inner) in map.iter_mut() {
                if key == "table" {
                    if let Some(number) = inner.as_i64() {
                        *inner = Value::String(name(number));
                        continue;
                    }
                }
                renumbered(inner, ids);
            }
        }
        Value::Array(items) => {
            for item in items.iter_mut() {
                renumbered(item, ids);
            }
        }
        _ => {}
    }
}

fn signature_of(ids: &Identities) -> BTreeMap<String, Vec<String>> {
    let mut out: BTreeMap<String, Vec<String>> = BTreeMap::new();
    for (at, ident) in ids.tables.iter().enumerate() {
        let mut bodies: Value = serde_json::from_str(&ids.structure.bodies[at]).expect("bodies are JSON");
        renumbered(&mut bodies, ids);
        let mut instance: Value = if ids.structure.instances[at].is_empty() { Value::Null } else { serde_json::from_str(&ids.structure.instances[at]).expect("an instance is JSON") };
        if let Some(inputs) = instance.get_mut("inputs").and_then(Value::as_array_mut) {
            for input in inputs {
                if let Some(number) = input[1].as_i64() {
                    input[1] = Value::String(usize::try_from(number).ok().and_then(|at| ids.tables.get(at)).cloned().unwrap_or_else(|| "-".into()));
                }
            }
        }
        let mut columns = ids.columns[at].clone();
        columns.sort();
        let entry = format!("columns={columns:?}\nbodies={bodies}\ninstance={instance}\nsymmetries={}", ids.structure.column_symmetries[at]);
        out.entry(ident.clone()).or_default().push(entry);
    }
    for entries in out.values_mut() {
        entries.sort();
    }
    out
}

/// The pairs of programs in the directory of `ARCLOG_IDENTITY_PAIRS` (`<task>.<kind>.<seed>.a.arclog`
/// and `.b.arclog`, the second an edit of the first) have the same structure. `ARCLOG_PAIR_FILTER`
/// keeps the pairs whose name contains it.
#[test]
#[ignore = "reads the pairs of programs in the directory that ARCLOG_IDENTITY_PAIRS names"]
fn edited_programs_have_the_structure_of_their_originals() {
    let Ok(dir) = std::env::var("ARCLOG_IDENTITY_PAIRS") else { return };
    let tasks = std::env::var("ARCLOG_TASKS").unwrap_or_else(|_| "../../data/tasks".into());
    let filter = std::env::var("ARCLOG_PAIR_FILTER").unwrap_or_default();
    let cap: u64 = std::env::var("ARCLOG_TABLE_WORK_CAP").ok().and_then(|cap| cap.parse().ok()).unwrap_or(50_000);
    let mut names: Vec<_> = std::fs::read_dir(&dir)
        .expect("the directory")
        .filter_map(|entry| entry.ok()?.file_name().into_string().ok()?.strip_suffix(".a.arclog").map(str::to_owned))
        .filter(|name| name.contains(&filter))
        .collect();
    names.sort();
    let started = std::time::Instant::now();
    let mut differing = 0;
    for (done, name) in names.iter().enumerate() {
        let task = name.split('.').next().expect("a task name");
        let at = |side: &str| std::fs::read_to_string(format!("{dir}/{name}.{side}.arclog")).expect("a program");
        let (a, b) = (signature(task, Path::new(&tasks), &at("a"), cap), signature(task, Path::new(&tasks), &at("b"), cap));
        match (a, b) {
            (Ok(a), Ok(b)) if a == b => {}
            (Ok(a), Ok(b)) => {
                differing += 1;
                eprintln!("{name}: the structure differs");
                for ident in a.keys().chain(b.keys()).collect::<std::collections::BTreeSet<_>>() {
                    if a.get(ident) != b.get(ident) {
                        let (sa, sb) = (a.get(ident).cloned().unwrap_or_default(), b.get(ident).cloned().unwrap_or_default());
                        let only_a: Vec<_> = sa.iter().filter(|entry| !sb.contains(entry)).collect();
                        let only_b: Vec<_> = sb.iter().filter(|entry| !sa.contains(entry)).collect();
                        eprintln!("  table {ident}\n  BEFORE {}\n  AFTER  {}", only_a.first().map_or("-", |e| e.as_str()), only_b.first().map_or("-", |e| e.as_str()));
                    }
                }
            }
            (a, b) => {
                differing += 1;
                eprintln!("{name}: {:?} / {:?}", a.err(), b.err());
            }
        }
        let rate = (done + 1) as f64 / started.elapsed().as_secs_f64();
        eprintln!("[{}/{} {rate:.2}/s eta {:.0}s] {name}", done + 1, names.len(), (names.len() - done - 1) as f64 / rate);
    }
    eprintln!("{differing} of {} pairs differ", names.len());
    assert_eq!(differing, 0);
}

/// One program's structure printed, to read it.
#[test]
#[ignore = "reads the program in the file that ARCLOG_SHOW names, on the task ARCLOG_SHOW_TASK"]
fn show_structure() {
    let (Ok(file), Ok(task)) = (std::env::var("ARCLOG_SHOW"), std::env::var("ARCLOG_SHOW_TASK")) else { return };
    let tasks = std::env::var("ARCLOG_TASKS").unwrap_or_else(|_| "../../data/tasks".into());
    let registry = Registry::get();
    let (read, _) = read_task_files(Path::new(&tasks), &task).expect("a task");
    let settings = DecodeSettings { table_work_cap: 50_000, ..DecodeSettings::default() };
    let session = TaskSession::new(SessionBound { bytes: study_pair::STUDY_SESSION_BYTES }, settings.caps);
    let constructions = arclog_constructions::shared().expect("constructions");
    let evidence = evidence_tables(&read, registry);
    let mut cache = study_pair::PairCache::with_byte_bound(true, study_pair::STUDY_SESSION_BYTES);
    let program = StudyProgram::from_sexp(&std::fs::read_to_string(file).expect("a file"), registry).expect("a program");
    cache.activate(&program);
    let limits = settings.operation_limits();
    let (_, tables) = study_pair::gold_tables_cached_in(&program, &read, &session, constructions, &settings, &mut cache, &limits);
    let written = program.written_stream(registry, &settings).expect("a stream");
    let ids = identify(program.checked(), registry, &written.relations, &evidence, &tables);
    for at in 0..ids.tables.len() {
        eprintln!("== table {at} {} columns {:?}", ids.tables[at], ids.columns[at]);
        eprintln!("instance {}", ids.structure.instances[at]);
        eprintln!("column symmetries {}", ids.structure.column_symmetries[at]);
        let bodies: Value = serde_json::from_str(&ids.structure.bodies[at]).expect("JSON");
        for body in bodies.as_array().expect("a list") {
            eprintln!("BODY {body}");
        }
    }
}
