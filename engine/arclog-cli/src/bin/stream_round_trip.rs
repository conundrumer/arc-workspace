//! `stream_round_trip <corpus-dir> <tasks-dir> [--cases concept|all] [--no-mask] <task_id> ...`:
//! a check of the token stream of each case program of the solvers given.
//!
//! For each case, the concept case alone or, with `--cases all`, every case,
//! it writes the case's stream as `arclog::stream::corpus::corpus_case_stream`
//! does, steps a decoder through it, with the mask at each token the model
//! emits unless `--no-mask` is given, checks the program that the decode
//! gives, and writes that program's stream. It prints one line per case, as
//! each case ends:
//!
//! `<task_id> <case>: <n> tokens; round trip <verdict>; query hashes <s> of <q> the same[, first differs at form <i> (<kind>)]`
//!
//! The round trip's verdict is `same` where the two streams are equal, and
//! otherwise the fault: the writer's, the decoder's refusal, the checker's
//! refusal of the decoded program, or the first token at which the streams
//! differ. The query hash of each form is that of
//! `arclog::decode::Decoder::query_hash` against that of the program the
//! writer wrote, its forms in the stream's order: the program of the case's
//! files where the corpus holds them, as
//! `arclog::stream::corpus::corpus_case_stream_of_files` gives it, and
//! otherwise the case's program. The last line counts the cases of each
//! verdict.

use std::ops::ControlFlow;
use std::path::Path;
use std::process::ExitCode;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::corpus::{corpus_session, read_corpus_task};
use arclog::decode::replay::replay;
use arclog::decode::Decoder;
use arclog::program::path::NodePath;
use arclog::program::{Form, Node, Program};
use arclog::registry::Registry;
use arclog::resolver::{resolve, resolve_cases, SolverScope};
use arclog::stream::corpus::{case_spelled, check_cases, corpus_case_stream_of_files, decoded_cases};
use arclog::stream::{token_stream, DecodeSettings, WrittenStream};

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (Some(corpus), Some(tasks)) = (args.first(), args.get(1)) else {
        eprintln!("usage: stream_round_trip <corpus-dir> <tasks-dir> [--cases concept|all] [--no-mask] <task_id> ...");
        return ExitCode::from(2);
    };
    let mut all = false;
    let mut masked = true;
    let mut ids = Vec::new();
    let mut rest = args[2..].iter();
    while let Some(arg) = rest.next() {
        match arg.as_str() {
            "--cases" => all = rest.next().map(String::as_str) == Some("all"),
            "--no-mask" => masked = false,
            id => ids.push(id.to_owned()),
        }
    }
    let (mut same, mut cases) = (0, 0);
    for id in &ids {
        let mut print = |line: String, round_trip: Option<bool>| {
            println!("{line}");
            if let Some(round_trip) = round_trip {
                cases += 1;
                same += usize::from(round_trip);
            }
        };
        if let Err(fault) = solver_lines(Path::new(corpus), Path::new(tasks), id, all, masked, &mut print) {
            println!("{id}: {fault}");
        }
    }
    println!("{same} of {cases} cases give the same stream again");
    ExitCode::SUCCESS
}

/// Gives `print` the line of each wanted case of the solver `id`, as the
/// case ends, with whether its round trip gives the same stream; or the
/// fault that stops the solver.
fn solver_lines(corpus: &Path, tasks: &Path, id: &str, all: bool, masked: bool, print: &mut dyn FnMut(String, Option<bool>)) -> Result<(), String> {
    let read = read_corpus_task(corpus, tasks, id)?;
    let registry = Registry::get();
    let cases = resolve_cases(&read.solver, registry);
    let clauses = SolverClauses::of_cases(&cases);
    let mut cache = CheckCache::default();
    let wanted = decoded_cases(&cases, all);
    let programs = check_cases(&read.solver, &cases, &clauses, &mut cache, &|name| wanted.contains(name), false)?;
    let session = corpus_session();
    let constructions = arclog_constructions::shared()?;
    let settings = DecodeSettings::default();
    for (name, checked) in &programs {
        let case = cases.cases().find(|case| case.case.name == *name).expect("a checked case is a case of the solver");
        let mut decoder = Decoder::new(&read.task, &session, registry, constructions, &settings);
        let spelled = case_spelled(name);
        let (written, files) = match corpus_case_stream_of_files(corpus, id, case, checked, decoder.vocabulary(), false) {
            Ok(written) => written,
            Err(fault) => {
                print(format!("{id} {spelled}: no stream: {fault}"), Some(false));
                continue;
            }
        };
        let text = match files {
            Some(program) => program,
            None if case.case.reads_alone_as_it_stands() => checked.program.program.clone(),
            None => case.case.program_alone().clone(),
        };
        let (verdict, same) = round_trip(&mut decoder, &written, masked);
        let hashes = query_hashes(&decoder, &text, &written);
        print(format!("{id} {spelled}: {} tokens; round trip {verdict}; query hashes {hashes}", written.tokens.len()), Some(same));
    }
    Ok(())
}

/// The verdict of the round trip of `written` through `decoder`, and
/// whether it gives the same stream.
fn round_trip(decoder: &mut Decoder<'_>, written: &WrittenStream, masked: bool) -> (String, bool) {
    let replayed = replay(decoder, &written.tokens, masked, &mut |_, _| ControlFlow::Continue(()));
    match replayed {
        Ok(replayed) if replayed.end() < written.tokens.len() => return (format!("the decode ends at its `OUT` form at token {}", replayed.end()), false),
        Ok(replayed) => {
            if let Some(fault) = replayed.unfinished() {
                return (fault, false);
            }
        }
        Err(refusal) => return (format!("the decoder refuses: {refusal}"), false),
    }
    let decoded = match checked(decoder.program()) {
        Ok(decoded) => decoded,
        Err(fault) => return (format!("the checker refuses the decoded program: {fault}"), false),
    };
    let again = match token_stream(&decoded, decoder.vocabulary()) {
        Ok(again) => again,
        Err(fault) => return (format!("the decoded program has no stream: {}", fault.message), false),
    };
    match again.iter().zip(&written.tokens).position(|(a, b)| a != b) {
        Some(at) => (format!("differs at token {at}: {:?} in place of {:?}", again[at], written.tokens[at]), false),
        None if again.len() != written.tokens.len() => (format!("gives {} tokens in place of {}", again.len(), written.tokens.len()), false),
        None => ("same".to_owned(), true),
    }
}

/// `program`, a decoded program, checked.
fn checked(program: &Node<Program>) -> Result<CheckedProgram, String> {
    let registry = Registry::get();
    let resolved = resolve(program, None, &SolverScope::default(), registry).value;
    check_program(resolved.clone(), &SolverClauses::of_program(resolved), registry, &mut CheckCache::default())
        .map_err(|refusals| refusals.iter().map(|refusal| refusal.message.to_string()).collect::<Vec<_>>().join("; "))
}

/// The count of the forms of `written` whose query hash in `decoder` is
/// the one in `text`, the program the writer wrote, with its forms in the
/// order of the stream, of the forms the decode finished, and the first
/// form where the two differ.
fn query_hashes(decoder: &Decoder<'_>, text: &Node<Program>, written: &WrittenStream) -> String {
    let registry = Registry::get();
    let mut leaves = Vec::new();
    leaf_forms(&text.value().forms, &NodePath::default(), &mut leaves);
    let forms: Vec<Form> = written.forms.iter().filter_map(|form| leaves.iter().find(|(path, _)| *path == form.path).map(|(_, form)| form.clone())).collect();
    if forms.len() != written.forms.len() {
        return format!("not compared: {} of the {} forms of the stream stand in the text", forms.len(), written.forms.len());
    }
    let ordered = Node::new(Program { forms: forms.into() });
    let resolved = resolve(&ordered, None, &SolverScope::default(), registry).value;
    let finished = decoder.program().value().forms.len();
    let mut same = 0;
    let mut first = None;
    for index in 0..finished {
        if decoder.query_hash(index) == resolved.query_content(index, registry).map(|content| content.content_hash()) {
            same += 1;
        } else if first.is_none() {
            first = Some(format!(", first differs at form {index} ({})", kind(&decoder.program().value().forms[index])));
        }
    }
    format!("{same} of {finished} the same{}", first.unwrap_or_default())
}

/// Each form of `forms` that holds no form, with its path under `path`,
/// the forms of a claim in the claim's place.
fn leaf_forms(forms: &[Form], path: &NodePath, out: &mut Vec<(NodePath, Form)>) {
    for (index, form) in forms.iter().enumerate() {
        let at = path.child(index as u32);
        match form {
            Form::Claim(claim) => leaf_forms(&claim.value().forms, &at, out),
            _ => out.push((at, form.clone())),
        }
    }
}

/// The keyword of `form`.
fn kind(form: &Form) -> &'static str {
    match form {
        Form::Clause(_) => "a clause",
        Form::Instance(_) => "INIT",
        Form::Choose(_) => "CHOOSE",
        Form::RigidDet(_) => "RIGID_DET",
        Form::Out(_) => "OUT",
        Form::Demonstrated(_) => "DEMONSTRATED",
        Form::Claim(_) => "a claim",
        Form::Alts(_) => "ALTS",
    }
}
