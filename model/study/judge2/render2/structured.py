"""Read engine AST export parts as they arrive, without any sexp parser."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[2]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import json
from collections import OrderedDict
from native import require


class Programs:
    def __init__(self, engine):
        self.engine = engine
        self.cache = OrderedDict()
        from assignments import Assignments
        self.assignments = Assignments(engine)
        self.frames=OrderedDict()
        self.settings=None
        self.evaluator=None
        self.task=None
        self.names=OrderedDict()

    def source_names(self, program, text, record):
        """One exact native writer map for gold and its identity mutant."""
        if record is None:
            return None, dict(status='unavailable', reason='no original task/case for source-name recovery')
        supplied=record.get('relation_source_names')
        if supplied is not None:
            require(supplied.get('schema')=='arclog-study-relation-names-v1', 'unknown source-name schema')
            require((supplied.get('task'),supplied.get('case'))==(record['task'],record['case']), 'source-name task/case differs from record')
            return json.dumps(supplied), dict(status='complete', origin='record')
        key=(text,record['task'],record['case'])
        if key in self.names:
            self.names.move_to_end(key)
            return self.names[key]
        if not hasattr(program,'relation_source_names_json'):
            result=None, dict(status='unavailable',reason='runtime has no native source-name recovery API')
        else:
            try:
                names=program.relation_source_names_json(str(MAIN_ROOT / 'programs/arclog'),record['task'],record['case'])
                result=names, dict(status='complete',origin='native exact source-case recovery')
            except self.engine.Refusal as error:
                result=None, dict(status='unavailable',reason=str(error))
        self.names[key]=result
        while len(self.names)>16:self.names.popitem(last=False)
        return result

    def frame_sources(self, program, text, export=None):
        if export is not None and export.get("frame_sources") is not None:
            return export["frame_sources"]
        if not hasattr(self.engine,'study_frame_sources_json'):return None
        if text in self.frames:return self.frames[text]
        try:
            data=json.loads(self.engine.study_frame_sources_json(program))
        except (self.engine.Refusal, ValueError) as error:
            # Preserve this native evidence failure independently of the
            # successfully exported AST/definitions. It is a fault, not a
            # missing-part placeholder, and cannot pass the READY barrier.
            data=dict(schema='arclog-study-frame-sources-v1',complete=False,status='fault',reason=str(error))
            self.frames[text]=data
            return data
        require(data['schema']=='arclog-study-frame-sources-v1' and data['complete'] is True,'native frame provenance incomplete')
        self.frames[text]=data
        while len(self.frames)>16:self.frames.popitem(last=False)
        return data

    def load(self, text, record=None, *, mutant_record=None, current_native_names=False):
        # A stored map must be authenticated even if the same program was
        # previously exported for another record. Never reuse an unnamed export.
        mutation_key = (mutant_record['programs']['gold'],
                        json.dumps(mutant_record['identity'],sort_keys=True),
                        json.dumps(mutant_record.get('relation_source_names'),sort_keys=True),
                        mutant_record['task'],mutant_record['case']) if mutant_record is not None else None
        require(type(current_native_names) is bool, 'current_native_names must be boolean')
        require(not current_native_names or mutant_record is not None, 'CURRENT names require a certified mutant')
        key=(current_native_names,text,json.dumps(record.get('relation_source_names'),sort_keys=True) if record else None,
             (record['task'],record['case']) if record else None,mutation_key)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        if mutant_record is not None:
            # Reparse/decode can normalize nested sites and allocate different
            # label spellings. Reconstruct the logged mutation from its exact
            # gold source, as pair() does, retaining native label identities.
            require(text == mutant_record['programs']['mutant'], 'requested mutant differs from record')
            gold,gexport,naming=self.load(mutant_record['programs']['gold'],mutant_record)
            require(hasattr(gold,'construct_identity'),'runtime cannot reconstruct native mutation identity')
            from native_correspondence import rehydrate_stored_mutation, stored_metadata_program
            stored=stored_metadata_program(self.engine,text,self.settings)
            program,native_admission=rehydrate_stored_mutation(self.engine,gold,mutant_record['identity'],stored)
            names=json.dumps(gexport['relation_source_names']) if gexport.get('relation_source_names') is not None else None
            require(names is None or hasattr(self.engine,'study_mutant_export_json'),'runtime cannot authenticate mutant source-name map')
            export=json.loads(self.engine.study_mutant_export_json(program,names) if hasattr(self.engine,'study_mutant_export_json') else program.render_json())
            require(export['mutation_identity']==mutant_record['identity'],'native mutation identity differs from record')
            from native_correspondence import certify_stored_representation
            stored_export = json.loads(self.engine.study_program_export_json(stored,source_program=stored))
            certificate = certify_stored_representation(program,stored,
                requested_text=text,rehydrated_export=export,
                stored_export=stored_export,mutation_identity=mutant_record['identity'],native_admission=native_admission)
            # Execution retains the certified ValidMutant. Presentation uses
            # the stored handle's own native nodes and source correspondence.
            naming = dict(status='unavailable',
                reason='stored representation has no authenticated original-gold name map',
                constructed_source_names=naming,
                stored_representation=certificate)
            export = dict(stored_export,stored_representation=certificate)
            if current_native_names:
                from native_correspondence import Correspondence
                current=program.as_program()
                current_export=json.loads(self.engine.study_program_export_json(current,source_program=current))
                bridge=json.loads(self.engine.study_program_export_json(current,source_program=stored))
                Correspondence(bridge,program_sexp=current.sexp(),source_program_sexp=text)
                require(current_export['program_sexp']==current.sexp(), 'CURRENT SELF metadata writer differs')
                export=dict(current_export,current_native_names=dict(current_export=current_export,
                    stored_export=stored_export,namespace_correspondence=bridge,
                    identity=mutant_record['identity'],identity_certificate=certificate))

        else:
            program = self.engine.StudyProgram.from_sexp(text,self.settings) if self.settings is not None else self.engine.StudyProgram.from_sexp(text)
            if hasattr(program,'decode_source'):
                program=program.decode_source()
            names,naming=self.source_names(program,text,record)
            require(names is None or hasattr(self.engine,'study_program_export_json'),'runtime cannot authenticate source-name map')
            export = json.loads(self.engine.study_program_export_json(program,names) if hasattr(self.engine,"study_program_export_json") else program.render_json())
        require(export['schema'] == 'arclog-study-render-v1', 'unknown engine render schema')
        require(export['parts']['nodes'] == 'complete', 'engine AST export incomplete')
        require(export['program_sexp'] == (program.sexp() if current_native_names else text), 'engine AST export program differs from record')
        nodes = {tuple(n['path']): n for n in export['nodes']}
        require(len(nodes) == len(export['nodes']), 'duplicate engine node paths')
        for path, node in nodes.items():
            for child in node['children']:
                require(tuple(child) in nodes, 'missing engine child path')
            require(isinstance(node['sexp'], str), 'missing engine node presentation')
        self.cache[key] = (program, export, naming)
        # Keep handles and their authenticated exports together. Avoid sharing
        # arbitrary native identifiers across program/task sessions.
        while len(self.cache) > 16:
            self.cache.popitem(last=False)
        return program, export, naming

    def pair(self, record, source=None):
        if not hasattr(self.engine.StudyProgram, 'render_json'):
            return None
        if hasattr(self.engine,'study_component_tables') and self.settings is None:
            from pathlib import Path
            config=json.loads((source.parent.parent/'run.json').read_text())
            self.settings=self.engine.DecodeSettings(table_work_cap=config['work_cap'],rule_tests=False)
            self.evaluator=self.engine.StudyTaskEvaluator(record['task'],config['tasks'],self.settings,session_bytes=config.get('session_mib',64)*1024*1024,compact=True)
            self.task=record['task']
        if self.task is not None:require(self.task==record['task'],'task evaluator cannot cross task namespaces')
        gp, gold, naming = self.load(record['programs']['gold'],record)
        names=json.dumps(gold['relation_source_names']) if gold.get('relation_source_names') is not None else None
        mutant=None
        valid=None
        if hasattr(gp,'decode_source') and hasattr(gp,'construct_identity'):
            valid=gp.construct_identity(json.dumps(record['identity']))
            mutant=json.loads(self.engine.study_mutant_export_json(valid,names) if hasattr(self.engine,"study_mutant_export_json") else valid.render_json())
            require(mutant['program_sexp']==record['programs']['mutant'],'identity mutant differs')
            require(mutant['mutation_identity']==record['identity'],'identity replay metadata differs')
        elif hasattr(gp, 'render_pair_json'):
            pair = json.loads(gp.render_pair_json(json.dumps(record['identity'])))
            require(pair['schema'] == 'arclog-study-render-pair-v1', 'unknown pair export schema')
            gold, mutant = pair['gold'], pair['mutant']
            require(gold['program_sexp'] == record['programs']['gold'], 'rehydrated gold differs')
            require(mutant['program_sexp'] == record['programs']['mutant'], 'rehydrated mutant differs')
        elif hasattr(gp, 'construct_identity'):
            valid = gp.construct_identity(json.dumps(record['identity']))
            require(valid.sexp() == record['programs']['mutant'], 'identity replay differs from stored mutant')
            mutant = json.loads(valid.render_json())
            require(mutant['mutation_identity'] == record['identity'], 'engine mutation identity differs')
        else:
            _,mutant,_=self.load(record['programs']['mutant'])
        correspondence = mutant.get('source_path_correspondence')
        mapped = {tuple(c['before_path']):c for c in correspondence} if isinstance(correspondence,list) else {}
        after_nodes = {tuple(n['path']):n for n in mutant['nodes']}
        changes = []
        nodes = {tuple(n['path']): n for n in gold['nodes']}
        for edit in record['identity']['edits']:
            path = tuple(edit['at'])
            require(path in nodes, 'changed original AST atom not exported')
            node = nodes[path]
            require(node['kind'] in ('atom', 'not', 'comparison'), 'edit does not address an atom')
            after = None
            if path in mapped:
                item = mapped[path]
                if edit['replacement'] is None:
                    require(item['status'] == 'deleted' and item['after_path'] is None, 'deleted atom still mapped')
                else:
                    require(item['status'] == 'replaced' and item['after_path'] is not None, 'changed atom not mapped as replaced')
                    after = after_nodes[tuple(item['after_path'])]
            changes.append(dict(path=edit['at'], before=node, after=after,
                                deleted=edit['replacement'] is None,
                                after_status=mapped[path]['status'] if path in mapped else 'pending correspondence'))
        clause = nodes[tuple(record['identity']['clause'])]
        owner = nodes[tuple(record['identity']['clause'][:1])]
        mapped_clause=mapped.get(tuple(record['identity']['clause']))
        mutant_clause=after_nodes[tuple(mapped_clause['after_path'])] if mapped_clause and mapped_clause['after_path'] is not None else None
        body_views = {}
        if gold['parts'].get('body_views') == mutant['parts'].get('body_views') == 'complete':
            body = record['identity']['body']
            source_body = mapped.get(tuple(body))
            if source_body:
                require(source_body['after_path'] is not None, 'mutation body deleted')
                after_body = source_body['after_path']
                body_views['gold'] = next(b for b in gold['body_views'] if b['body_path'] == body)
                body_views['mutant'] = next(b for b in mutant['body_views'] if b['body_path'] == after_body)
        from definitions import context
        contexts = {side:context(e,record['identity']['clause'][:1],downstream_only=True) for side,e in (('gold',gold),('mutant',mutant))}
        from sites import collect
        sites={side:collect(e,record['identity']['clause'],contexts[side]) for side,e in (('gold',gold),('mutant',mutant))}
        choices=None
        if hasattr(gp,'choice_evidence_json'):
            kept,gold_choices=self.assignments.compiled(record,gp,gold)
            # Mutant dependency schemas may widen when a held DET is unused.
            # Its native static layout needs no decoding of full gold choices.
            mutant_choices=self.assignments.evidence(valid.as_program())
            choices=dict(gold=gold_choices,mutant=mutant_choices)
            full_observation=record.get('full_replay',{}).get('evaluation')
        else:
            kept=self.assignments.decode(record,source,gold) if source is not None else None
            full_observation=self.assignments.schemas(record,source)['evaluation'] if source is not None and record.get('full_replay',{}).get('gold') else None
        frames={'gold':self.frame_sources(gp,record['programs']['gold'],gold),
                'mutant':self.frame_sources(valid.as_program(),record['programs']['mutant'],mutant) if valid is not None else None}
        components=None
        if hasattr(self.engine,'study_component_tables'):
            from components import collect
            components=collect(self.engine,self.evaluator,gp,valid,record,contexts,{'gold':gold,'mutant':mutant})
        return dict(relation_names=naming,components=components,gold=gold, mutant=mutant, changes=changes, clause=clause, mutant_clause=mutant_clause,owner=owner,
                    choice_evidence=choices,body_views=body_views,contexts=contexts,sites=sites,kept_decoded=kept,frame_sources=frames,
                    full_gold_evaluation=full_observation,full_gold_scope=record.get('full_replay',{}).get('scope'))
