"""Check real stored render records; one process per task, streaming each pair.

The export/identity checks work on v8. --continuation requires the new binding
and checks the historical kept assignment before accepting new evidence.
"""
import argparse
from collections import Counter, OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import gzip
import json
from pathlib import Path
import signal
import subprocess
import sys
from threading import Lock
import time


def read(path):
    with (gzip.open(path, "rt") if path.suffix == ".gz" else path.open()) as stream:
        return json.load(stream)


def require(value, reason):
    if not value:
        raise ValueError(reason)


def worker(args):
    import arclog
    job=json.load(sys.stdin)
    handles=OrderedDict()
    evaluator=None
    if args.continuation or args.component_tables:
        require(hasattr(arclog,"study_component_tables"), "rebuild required: study_component_tables")
        if args.continuation:require(hasattr(arclog,"study_continuation"), "rebuild required: study_continuation")
        settings=arclog.DecodeSettings(rule_tests=False)
        evaluator=arclog.StudyTaskEvaluator(job["task"],str(args.tasks),settings,compact=False)
    def alarm(*_):
        raise TimeoutError("per-pair deadline")
    signal.signal(signal.SIGALRM,alarm)
    for filename in job["paths"]:
        started=time.monotonic()
        result=dict(event="pair",task=job["task"],source=filename)
        phase="read"
        signal.setitimer(signal.ITIMER_REAL,args.pair_seconds)
        try:
            record=read(Path(filename))
            result["case"]=record["case"]
            text=record["programs"]["gold"]
            phase="gold_export"
            if text not in handles:
                gold=arclog.StudyProgram.from_sexp(text,settings if evaluator else None).decode_source()
                handles[text]=(gold,json.loads(arclog.study_program_export_json(gold) if hasattr(arclog,"study_program_export_json") else gold.render_json()))
                while len(handles)>4:handles.popitem(last=False)
            gold,g=handles[text]
            phase="identity_replay"
            mutant=gold.construct_identity(json.dumps(record["identity"]))
            m=json.loads(arclog.study_mutant_export_json(mutant) if hasattr(arclog,"study_mutant_export_json") else mutant.render_json())
            require(m["program_sexp"]==record["programs"]["mutant"],"stored mutant sexp differs")
            require(m["mutation_identity"]==record["identity"],"stored identity differs")
            phase="change"
            old={tuple(n["path"]):n for n in g["nodes"]}
            new={tuple(n["path"]):n for n in m["nodes"]}
            mapped={tuple(p["before_path"]):p for p in m["source_path_correspondence"]}
            for edit in record["identity"]["edits"]:
                path=tuple(edit["at"])
                require(path in old and bool(old[path]["sexp"]),"missing exact original atom")
                p=mapped[path]
                if edit["replacement"] is None:
                    require(p["status"]=="deleted" and p["after_path"] is None,"deleted atom correspondence")
                else:
                    require(p["status"]=="replaced" and tuple(p["after_path"]) in new,"replacement correspondence")
                    require(bool(new[tuple(p["after_path"])]["sexp"]),"missing exact replacement atom")
            for side,program,export in (("gold",gold,g),("mutant",mutant.as_program(),m)):
                phase=side+"_definitions"
                definitions=export["definitions"]
                graph={n["node"]:n for n in definitions["graph_nodes"]}
                registry={entry["id"]:entry for entry in definitions["registry"]["entries"]}
                for node in graph.values():
                    require(all(r in graph for r in node["reads"]),"unresolved graph definition")
                for reader in definitions["readers"]:
                    resolution=reader["resolution"]
                    require(resolution["kind"] in ("library","graph_node"),"unsupported reader resolution")
                    if resolution["kind"]=="library":
                        require(resolution["id"] in registry,"missing library definition")
                        require(registry[resolution["id"]]["semantics"]["status"]=="authored_contract","missing authored semantics")
                require(all(r.get("source_name") and r.get("display_name") for r in definitions["native_relations"]),"missing relation writer spelling")
                phase=side+"_frames"
                frames=export.get("frame_sources") or json.loads(arclog.study_frame_sources_json(program))
                require(frames["complete"] is True,"incomplete native frame source export")
                phase=side+"_body_columns"
                for body in export["body_views"]:
                    columns={c["body_column"]:c for c in body["columns"]}
                    require(len(columns)==len(body["columns"]),"duplicate native body column")
                    for p in body["input_port_projection"]:
                        if p["body_column"] is not None:
                            require(columns[p["body_column"]]["label_id"]==p["label_id"],"port projection loses native label identity")
            result["export"]="complete"
            if evaluator:
                phase="observe_gold"
                point=next(p for p in gold.points() if p.body_path==record["identity"]["body"])
                evaluator.evaluate_pair(gold,point,mutant)
                phase="component_tables"
                components,gt,mt=arclog.study_component_tables(evaluator,gold,mutant,
                    json.dumps(record["evaluation"]["kept_assignments"]))
                components=json.loads(components)
                require(components["gold_status"]["status"]=="complete","gold component tables "+str(components["gold_status"]))
                require(components["mutant_status"]["status"]=="complete","mutant component tables "+str(components["mutant_status"]))
                require(components["gold_observation_stop"] is None,"gold FITS observation incomplete")
                for side,native in (("gold",gt),("mutant",mt)):
                    axes={name:list(memoryview(native.entries[name]).cast("B" if name=="example_kind" else "I"))
                        for name in ("table","example_kind","example_index","model")}
                    for table in components[side+"_assignment_map"]:
                        require([e["table_entry"] for e in table["entries"]]==list(range(len(table["entries"]))),"noncontiguous native entry indices")
                        require(all(e["kept_assignment"] is None or 0<=e["kept_assignment"]<len(components["kept_assignments"]) for e in table["entries"]),"component entry has invalid full choice index")
                        native_entries=[i for i,t in enumerate(axes["table"]) if t==table["table"]]
                        require(len(native_entries)==len(table["entries"]),"assignment map length differs from actual native entries")
                        for index,entry in zip(native_entries,table["entries"]):
                            require(axes["example_kind"][index]=={"task":0,"train":1,"test":2}[entry["example_kind"]]
                                and axes["example_index"][index]==entry["example_index"] and axes["model"][index]==entry["model"],
                                "assignment map axes differ from actual native entries")
                result["component_tables"]="complete"
            if args.continuation:
                phase="continuation"
                report,gt,mt=arclog.study_continuation(evaluator,gold,mutant,
                    json.dumps(record["evaluation"]["kept_assignments"]))
                report=json.loads(report)
                require(report["gold_tables"]["status"]=="complete","gold continuation "+str(report["gold_tables"]))
                require(report["mutant_tables"]["status"]=="complete","mutant continuation "+str(report["mutant_tables"]))
                require(report["gold_observation_stop"] is None,"gold FITS observation incomplete")
                for choice in report["choices"]:
                    require(choice["out"]["status"]=="complete","OUT stopped or faulted")
                    require(all(d["status"]=="complete" for d in choice["admissibility"]),"DET admissibility stopped or faulted")
                result["continuation"]=dict(choices=len(report["choices"]),
                    inadmissible=sum(d.get("admissible") is False for c in report["choices"] for d in c["admissibility"]))
            result["status"]="pass"
        except Exception as error:
            result.update(status="failure",failure_class=phase+"/"+type(error).__name__,reason=str(error))
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
        result["seconds"]=round(time.monotonic()-started,6)
        print(json.dumps(result),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool",type=Path)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--workers",type=int,default=8)
    parser.add_argument("--only",nargs="*")
    parser.add_argument("--limit",type=int,default=0)
    parser.add_argument("--tasks",type=Path,default=Path(__file__).resolve().parents[2]/"data/tasks")
    parser.add_argument("--pair-seconds",type=float,default=10)
    parser.add_argument("--continuation",action="store_true")
    parser.add_argument("--component-tables",action="store_true",help="check native component output tables independently of OUT")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker:
        worker(args)
        return
    if not args.pool or not args.output:parser.error("--pool and --output required")
    paths=sorted((args.pool/"pairs").glob("*/source.json.gz"))
    groups=defaultdict(list)
    for path in paths:
        metadata=read(path.parent/"POOL.json")
        if not args.only or metadata["task"] in args.only:groups[metadata["task"]].append(str(path.resolve()))
    if args.limit:
        remaining=args.limit
        for task in list(groups):
            groups[task]=groups[task][:remaining];remaining-=len(groups[task])
            if not groups[task]:del groups[task]
    total=sum(map(len,groups.values()))
    args.output.mkdir(parents=True,exist_ok=False)
    counts=Counter();examples=defaultdict(list);done=0;started=time.monotonic();lock=Lock()
    def progress():
        elapsed=time.monotonic()-started;rate=done/elapsed if elapsed else 0
        print(json.dumps(dict(event="progress",done=done,total=total,elapsed=round(elapsed,2),
            rate=round(rate,3),eta=round((total-done)/rate,1) if rate else None)),flush=True)
    with (args.output/"cases.jsonl").open("w") as outgoing:
        def task_worker(task,files):
            nonlocal done
            command=[sys.executable,"-B",str(Path(__file__).resolve()),"--worker","--tasks",str(args.tasks),
                "--pair-seconds",str(args.pair_seconds)]
            if args.continuation:command.append("--continuation")
            if args.component_tables:command.append("--component-tables")
            with subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1) as process:
                process.stdin.write(json.dumps(dict(task=task,paths=files)));process.stdin.close()
                received=0
                for line in process.stdout:
                    record=json.loads(line);received+=1
                    with lock:
                        outgoing.write(json.dumps(record)+"\n");outgoing.flush();done+=1
                        key=record.get("failure_class",record["status"]);counts[key]+=1
                        if key!="pass" and len(examples[key])<5:examples[key].append(record)
                        print(json.dumps(record),flush=True)
                code=process.wait()
                if code or received!=len(files):
                    with lock:
                        fault=dict(event="worker_failure",task=task,code=code,received=received,expected=len(files))
                        outgoing.write(json.dumps(fault)+"\n");outgoing.flush()
                        counts["worker_exit"]+=1;examples["worker_exit"].append(fault)
        progress()
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(task_worker,task,files) for task,files in groups.items()}
            while futures:
                finished,futures=wait(futures,timeout=2,return_when=FIRST_COMPLETED)
                for future in finished:future.result()
                with lock:progress()
    summary=dict(done=done,total=total,seconds=time.monotonic()-started,counts=dict(counts),examples=dict(examples))
    (args.output/"summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(dict(event="summary",**summary)),flush=True)
    return int(counts.get("pass",0)!=total or counts.get("worker_exit",0)>0)


if __name__=="__main__":sys.exit(main())
