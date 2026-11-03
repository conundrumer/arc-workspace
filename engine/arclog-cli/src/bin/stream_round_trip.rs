//! `stream_round_trip <corpus-dir> <tasks-dir> [--cases concept|all] [--no-mask] [--variants] <task_id> ...`:
//! a check of the token stream of each case program of the solvers given,
//! which tracks the stream's `DEMONSTRATED` form while it is in progress
//! and gates nothing.
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
//!
//! With `--variants`, each case whose text holds a `DEMONSTRATED` form
//! also prints a line per variant of that form, a copy of the case's text
//! that differs from it in one kind of content alone:
//!
//! `<task_id> <case> DEMONSTRATED <variant>: tables <same|differ ...>; query hash <same|differs>`
//!
//! The tables are the form's relation on each example, at each model, at
//! the solver's stored `param` records, each evaluation in a session of its
//! own that shares the terms of the others. The query hash is the form's.
//! The variants are: `rule names`, each rule named apart from its name;
//! `rule texts`, each rule with a text other than its own; `value head
//! names`, each label name and field name of the `value` head renamed, and
//! each column and field of a rule of that name with it; and `value head
//! names alone`, the head's names renamed with no column or field of a rule.

use std::ops::ControlFlow;
use std::path::Path;
use std::process::ExitCode;

use arclog::check::{check_program, CheckCache, CheckedProgram, SolverClauses};
use arclog::decode::corpus::CorpusTask;
use arclog::eval::examples::{scope_of, ExampleScope};
use arclog::eval::{relation_of, Cancellation, Evaluation, Limits, ParameterValues, RelationValue};
use arclog::program::{Clause, ColumnName, DeclaredName, RelationName, DemoRule, DemoRuleName, Demonstrated, InstanceInput, KeyClause, ProgramRelation, Site, SiteArg, SiteValue, Text};
use arclog::session::TaskSession;
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
    let mut variants = false;
    let mut ids = Vec::new();
    let mut rest = args[2..].iter();
    while let Some(arg) = rest.next() {
        match arg.as_str() {
            "--cases" => all = rest.next().map(String::as_str) == Some("all"),
            "--no-mask" => masked = false,
            "--variants" => variants = true,
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
        if let Err(fault) = solver_lines(Path::new(corpus), Path::new(tasks), id, all, masked, variants, &mut print) {
            println!("{id}: {fault}");
        }
    }
    println!("{same} of {cases} cases give the same stream again");
    ExitCode::SUCCESS
}

/// Gives `print` the line of each wanted case of the solver `id`, as the
/// case ends, with whether its round trip gives the same stream, and each
/// line of its variants, with none; or the fault that stops the solver.
fn solver_lines(corpus: &Path, tasks: &Path, id: &str, all: bool, masked: bool, variants: bool, print: &mut dyn FnMut(String, Option<bool>)) -> Result<(), String> {
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
        if variants {
            for line in variant_lines(&read, &text, constructions) {
                print(format!("{id} {spelled} DEMONSTRATED {line}"), None);
            }
        }
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

/// The line of each variant of the `DEMONSTRATED` form of `text`, as the
/// module's text gives them, after the variant's name; none where `text`
/// holds no `DEMONSTRATED` form.
fn variant_lines(read: &CorpusTask, text: &Node<Program>, constructions: &arclog::eval::instance::Constructions) -> Vec<String> {
    let mut leaves = Vec::new();
    leaf_forms(&text.value().forms, &NodePath::default(), &mut leaves);
    let forms: Vec<Form> = leaves.into_iter().map(|(_, form)| form).collect();
    let Some(at) = forms.iter().position(|form| matches!(form, Form::Demonstrated(_))) else { return Vec::new() };
    let Form::Demonstrated(original) = &forms[at] else { unreachable!("the position of a `DEMONSTRATED` form") };
    let original = original.value();
    let session = arclog::decode::corpus::corpus_session();
    let base = match outcome(read, &forms, at, &original.name, &session, constructions) {
        (Ok(tables), hash) => (tables, hash),
        (Err(fault), _) => return vec![format!("not compared: the text: {fault}")],
    };
    let renamed = head_renames(original);
    let variants: [(&str, Demonstrated); 4] = [
        ("rule names", with_rules(original, |index, rule| DemoRule { name: DemoRuleName(format!("$Variant{index}").into()), ..rule.clone() })),
        ("rule texts", with_rules(original, |index, rule| DemoRule { text: Some(Text(format!("variant text {index}").into())), ..rule.clone() })),
        ("value head names", with_rules(&with_value_head(original, &renamed), |_, rule| renamed_rule(rule, &renamed))),
        ("value head names alone", with_value_head(original, &renamed)),
    ];
    let mut lines = Vec::new();
    for (name, variant) in variants {
        let mut changed = forms.clone();
        changed[at] = Form::Demonstrated(Node::new(variant));
        let (tables, hash) = outcome(read, &changed, at, &original.name, &session, constructions);
        let tables = match tables {
            Ok(tables) if tables == base.0 => "same".to_owned(),
            Ok(tables) => format!("differ ({} in place of {})", tables.join(" "), base.0.join(" ")),
            Err(fault) => format!("differ (the variant faults: {fault})"),
        };
        let hash = if hash == base.1 { "same" } else { "differs" };
        let line = format!("{name}: tables {tables}; query hash {hash}");
        lines.push(line);
    }
    lines
}

/// The tables of the relation `name` of the program of `forms`, checked,
/// on each example at each model, or the fault that gives none, and the
/// query hash of the form at `at`.
fn outcome(read: &CorpusTask, forms: &[Form], at: usize, name: &arclog::program::RelationName, session: &TaskSession, constructions: &arclog::eval::instance::Constructions) -> (Result<Vec<String>, String>, Option<arclog::hash::StableHash>) {
    let registry = Registry::get();
    let program = Node::new(Program { forms: forms.into() });
    let hash = resolve(&program, None, &SolverScope::default(), registry).value.query_content(at, registry).map(|content| content.content_hash());
    (tables(read, &program, name, session, constructions), hash)
}

/// The tables of the relation `name` of `program`, checked, on each
/// example at each model, or the fault that gives none.
fn tables(read: &CorpusTask, program: &Node<Program>, name: &arclog::program::RelationName, session: &TaskSession, constructions: &arclog::eval::instance::Constructions) -> Result<Vec<String>, String> {
    let registry = Registry::get();
    let checked = checked(program)?;
    let relation = relation_of(&checked, &ProgramRelation::Declared(name.clone())).ok_or("the program has no relation of the form")?;
    let parameters = ParameterValues::stored(read.solver.arcdata.value());
    let limits = Limits::new(None, Cancellation::default());
    let session = session.sharing_terms();
    let evaluation = Evaluation { program: &checked, concept: None, task: &read.task, parameters: &parameters, session: &session, registry, constructions, limits: &limits };
    let examples: Vec<_> = match scope_of(&checked, &relation) {
        ExampleScope::PerExample => read.task.examples().map(Some).collect(),
        _ => vec![None],
    };
    let mut tables = Vec::new();
    for example in examples {
        let mut models = Vec::new();
        let ended = evaluation.models(&relation, example, &mut |value| {
            models.push(match value {
                RelationValue::Rows(rows) => format!("{}:{:?}", rows.len(), rows.rows_hash()),
                RelationValue::Undefined => "undefined".to_owned(),
                RelationValue::Stopped(_) => "stopped".to_owned(),
            });
            ControlFlow::Continue(())
        });
        match ended {
            Ok(_) => tables.push(models.join(",")),
            Err(fault) => tables.push(format!("fault:{}", fault.message)),
        }
    }
    Ok(tables)
}

/// `demonstrated` with each rule as `change` gives it from its index and
/// the rule.
fn with_rules(demonstrated: &Demonstrated, change: impl Fn(usize, &DemoRule) -> DemoRule) -> Demonstrated {
    let rules = demonstrated.rules.iter().enumerate().map(|(index, rule)| Node::new(change(index, rule.value()))).collect();
    Demonstrated { rules, ..demonstrated.clone() }
}

/// The new name of each label name and field name of the head of the
/// `value` input of `demonstrated`.
fn head_renames(demonstrated: &Demonstrated) -> Vec<(ColumnName, ColumnName)> {
    let mut renames = Vec::new();
    let rename = |name: &ColumnName| match name {
        ColumnName::Written(text) => Some((name.clone(), ColumnName::Written(format!("{text}_variant").into()))),
        ColumnName::Slot(_) => None,
    };
    for input in value_inputs(demonstrated) {
        for site in input.head.iter() {
            for arg in site.value.args.iter() {
                match arg {
                    SiteArg::NamedLabel { name, .. } => renames.extend(rename(name)),
                    SiteArg::Field(field) => renames.extend(rename(&field.column)),
                    SiteArg::Label(_) => {}
                }
            }
        }
    }
    renames
}

/// The `value` inputs of `demonstrated`, in its key clause and after it.
fn value_inputs(demonstrated: &Demonstrated) -> impl Iterator<Item = &InstanceInput> {
    let keyed = demonstrated.key.iter().flat_map(|key| key.value().inputs.iter());
    keyed.chain(demonstrated.inputs.iter()).map(|input| input.value()).filter(|input| &*input.name.0 == "value")
}

/// `demonstrated` with the names of the head of its `value` input renamed
/// as `renames` gives.
fn with_value_head(demonstrated: &Demonstrated, renames: &[(ColumnName, ColumnName)]) -> Demonstrated {
    let new = |name: &ColumnName| renames.iter().find(|(old, _)| old == name).map_or_else(|| name.clone(), |(_, new)| new.clone());
    let input = |input: &Node<InstanceInput>| -> Node<InstanceInput> {
        let value = input.value();
        if &*value.name.0 != "value" {
            return input.clone();
        }
        let head = value
            .head
            .iter()
            .map(|site| {
                let args = site
                    .value
                    .args
                    .iter()
                    .map(|arg| match arg {
                        SiteArg::NamedLabel { name, label } => SiteArg::NamedLabel { name: new(name), label: *label },
                        SiteArg::Field(field) => SiteArg::Field(Site { column: new(&field.column), ..field.clone() }),
                        arg => arg.clone(),
                    })
                    .collect();
                Site { column: site.column.clone(), value: SiteValue { args } }
            })
            .collect();
        Node::new(InstanceInput { head, ..value.clone() })
    };
    let key = demonstrated.key.as_ref().map(|key| Node::new(KeyClause { inputs: key.value().inputs.iter().map(input).collect(), ..key.value().clone() }));
    Demonstrated { key, inputs: demonstrated.inputs.iter().map(input).collect(), ..demonstrated.clone() }
}

/// `rule` with each column of its `&prediction` clauses and each of its
/// fields renamed as `renames` gives.
fn renamed_rule(rule: &DemoRule, renames: &[(ColumnName, ColumnName)]) -> DemoRule {
    let new = |column: &arclog::program::RelationColumn| arclog::program::RelationColumn {
        name: renames.iter().find(|(old, _)| *old == column.name).map_or_else(|| column.name.clone(), |(_, new)| new.clone()),
        label: column.label,
    };
    let forms = rule
        .forms
        .iter()
        .enumerate()
        .map(|(index, form)| {
            let form = match form {
                Form::Clause(clause) if is_prediction(clause.value()) => {
                    Form::Clause(Node::new(Clause { columns: clause.value().columns.iter().map(new).collect(), ..clause.value().clone() }))
                }
                form => form.clone(),
            };
            (form, rule.forms.from_alt(index))
        })
        .collect();
    DemoRule { fields: rule.fields.iter().map(new).collect(), forms, ..rule.clone() }
}

/// Whether `clause` is a `&prediction` clause.
fn is_prediction(clause: &Clause) -> bool {
    matches!(&clause.derives, ProgramRelation::Declared(RelationName(DeclaredName::Written(name))) if &**name == "&prediction")
}
