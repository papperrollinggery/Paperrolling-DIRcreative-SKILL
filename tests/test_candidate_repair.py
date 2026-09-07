from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import dircreative_visual_asset_jingzao_handoff as handoff
import dircreative_visual_asset_plan as planmod
from tests import test_visual_asset_jingzao_handoff as fixtures


class CandidateRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.project=self.root/'project';self.project.mkdir()
        self.provider=self.root/'provider/jingzao-image-forge'
        self.document,_=fixtures.VisualAssetJingzaoHandoffTests().fixture(self.project,self.provider,first_image=True)
        self.plan=json.loads((self.project/'visual-plan.json').read_text())
        self.asset=next(a for a in self.plan['assets'] if a['role']=='character_identity_reference')
        image=self.project/'candidate-v01.png';image.write_bytes(planmod.test_png_bytes(1920,1080))
        self.plan=planmod.record_candidate_output(self.plan,base_dir=self.project,asset_id=self.asset['asset_id'],image_path=image,execution_task_id='test-executor')
        self.asset=next(a for a in self.plan['assets'] if a['asset_id']==self.asset['asset_id'])
        self.review=planmod.candidate_self_check_template(self.plan,self.asset['asset_id'])
        self.review.update(reviewed_at=self.asset['technical_receipt']['checked_at'],reviewer_id='test-reviewer',review_task_id='test-review')
        self.review['assets'][0]['decision']='retry'
        for item in self.review['assets'][0]['observations']:
            item.update(result='fail' if item['check_id']=='frontal_portrait' else 'pass',observed='Unit fixture observation only for '+item['check_id'])
        self.asset['candidate_self_check']=fixtures.write_json(self.project/'retry-review.json',self.review)
        self.plan_binding=fixtures.write_json(self.project/'retry-plan.json',self.plan)
        self.changes=[{'check_id':'frontal_portrait','instruction':'Crop the left portrait from crown to neck with only minimal shoulder context.'}]
        self.binding={
            'contract_id':'candidate_repair_source_v1','project_id':self.plan['project_id'],
            'asset_id':self.asset['asset_id'],'truth_sha256':self.asset['truth_sha256'],
            'source_plan':self.plan_binding,
            'source_image':{'relative_path':self.asset['generated_file'],'sha256':self.asset['generated_sha256'],'pixel_sha256':self.asset['generated_pixel_sha256']},
            'self_check':self.asset['candidate_self_check'],'changes':self.changes,
        }

    def repair_document(self):
        doc=copy.deepcopy(self.document)
        doc['visual_plan']=self.plan_binding
        doc['active_asset'].update(operation='edit',visual_plan_sha256=self.plan_binding['sha256'])
        doc['candidate_repair']=self.binding
        request=json.loads((self.project/'request.json').read_text())
        request.update(operation='edit',visual_plan_sha256=self.plan_binding['sha256'],reference_assets=[{
            'input_id':'candidate-repair-base','asset_id':self.asset['asset_id'],'role':'base_edit_source',
            'relative_path':self.asset['generated_file'],'sha256':self.asset['generated_sha256'],
            'rights_status':'project_owned','approval_status':'candidate_repair_only'}])
        doc['input_spec']=fixtures.write_json(self.project/'repair-request.json',request)
        spec=json.loads((self.project/'visual-spec.json').read_text())
        spec=handoff.prepare_candidate_repair_spec(spec,self.binding,project_root=self.project,output_spec=self.project/'repair-spec.json')
        doc['output_spec']['visual_generation_spec']=fixtures.write_json(self.project/'repair-spec.json',spec)
        run=subprocess.run([sys.executable,str(self.provider/'scripts/compile_prompt.py'),str(self.project/'repair-spec.json')],capture_output=True,text=True)
        self.assertEqual(run.returncode,0,run.stderr)
        compiled=json.loads(run.stdout)
        doc['output_spec']['compiled_prompt_manifest']=fixtures.write_json(self.project/'repair-compiled.json',compiled)
        sha=hashlib.sha256(compiled['prompt'].encode()).hexdigest()
        doc['output_spec']['prompt_sha256']=sha;doc['delivery_consumption']['consumed_prompt_sha256']=sha
        return doc,compiled

    def validate(self,doc):
        return handoff.validate(doc,project_root=self.project,provider_root=self.provider,trusted_provider_roots=(self.provider,),allow_unsandboxed_test_replay=True)

    def test_retry_candidate_can_enter_formal_edit_without_becoming_approved_source(self):
        doc,compiled=self.repair_document()
        errors,prompt=self.validate(doc)
        self.assertEqual(errors,[])
        self.assertEqual(prompt,compiled['prompt'])
        self.assertIsNone(self.asset['visual_qa_receipt'])
        self.assertEqual(self.asset['character_mode'],'headed_master')
        self.assertEqual(self.asset['inherits_from'],[])


    def test_builder_reads_the_current_retry_and_rejects_pass_items_or_foreign_identity(self):
        actual=planmod.build_candidate_repair_source(project_root=self.project,visual_plan_binding=self.plan_binding,asset_id=self.asset['asset_id'],changes=self.changes)
        self.assertEqual(actual,self.binding)
        for changes in ([],[{'check_id':'left_profile','instruction':'Change a previously passing unrelated feature.'}],self.changes+self.changes):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError,'observed_failures'):
                    planmod.build_candidate_repair_source(project_root=self.project,visual_plan_binding=self.plan_binding,asset_id=self.asset['asset_id'],changes=changes)
        with self.assertRaisesRegex(ValueError,'unapproved_current_asset'):
            planmod.build_candidate_repair_source(project_root=self.project,visual_plan_binding=self.plan_binding,asset_id='identity-product-coldbrew-bottle',changes=self.changes)
        spec=json.loads((self.project/'visual-spec.json').read_text())
        for key,value in [('project_id','another-project'),('asset_id','another-asset'),('truth_sha256','0'*64)]:
            bad=copy.deepcopy(self.binding);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                handoff.prepare_candidate_repair_spec(spec,bad,project_root=self.project,output_spec=self.project/'new.json')

    def test_empty_review_stale_review_and_stale_plan_are_not_repair_authority(self):
        for mutation in ('empty','checked','rehashed_empty','stale_plan'):
            with self.subTest(mutation=mutation):
                review=copy.deepcopy(self.review);plan=copy.deepcopy(self.plan);binding=copy.deepcopy(self.plan_binding)
                if mutation=='empty':review['assets'][0]['observations']=[]
                if mutation=='checked':review['assets'][0]['decision']='checked'
                if mutation=='rehashed_empty':
                    review=planmod.candidate_self_check_template(plan,self.asset['asset_id'])
                    plan['assets'][0]['candidate_self_check']=fixtures.write_json(self.project/'retry-review.json',review)
                    binding=fixtures.write_json(self.project/'retry-plan.json',plan)
                elif mutation=='stale_plan':
                    plan['completion_claim']='plan_complete';fixtures.write_json(self.project/'retry-plan.json',plan)
                else: fixtures.write_json(self.project/'retry-review.json',review)
                with self.assertRaises(ValueError):
                    planmod.build_candidate_repair_source(project_root=self.project,visual_plan_binding=binding,asset_id=self.asset['asset_id'],changes=self.changes)
                fixtures.write_json(self.project/'retry-review.json',self.review)
                fixtures.write_json(self.project/'retry-plan.json',self.plan)

    def test_changed_source_image_and_foreign_or_extra_reference_are_blocked(self):
        doc,_=self.repair_document()
        request=json.loads((self.project/'repair-request.json').read_text())
        for change in ('asset','extra'):
            bad=copy.deepcopy(request)
            if change=='asset':bad['reference_assets'][0]['asset_id']='foreign-asset'
            else:bad['reference_assets'].append(dict(bad['reference_assets'][0],input_id='extra'))
            modified=copy.deepcopy(doc);modified['input_spec']=fixtures.write_json(self.project/'bad-request.json',bad)
            self.assertIn('candidate_repair_reference_set_mismatch',self.validate(modified)[0])
        (self.project/'candidate-v01.png').write_bytes(planmod.test_png_bytes(1921,1080))
        self.assertTrue(any(x.startswith('candidate_repair_invalid:') for x in self.validate(doc)[0]))

    def test_prepare_spec_binds_only_this_candidate_and_exact_changes(self):
        spec=json.loads((self.project/'visual-spec.json').read_text())
        prepared=handoff.prepare_candidate_repair_spec(spec,self.binding,project_root=self.project,output_spec=self.project/'out-spec.json')
        self.assertEqual(prepared['mode'],'edit');self.assertEqual(prepared['intent'],handoff.REPAIR_INTENT)
        self.assertEqual(prepared['inputs'][0]['role'],'base_edit_source')
        self.assertEqual(prepared['inputs'][0]['source_ref'],'candidate-v01.png')
        self.assertEqual(prepared['constraints']['must_change'],[x['instruction'] for x in self.changes])
        self.assertEqual(spec['mode'],'create');self.assertEqual(spec['inputs'],[])
        doc,_=self.repair_document();bad=json.loads((self.project/'repair-spec.json').read_text())
        bad['constraints']['must_change']=['An unbound broader redesign instruction outside the selected defects.']
        doc['output_spec']['visual_generation_spec']=fixtures.write_json(self.project/'bad-spec.json',bad)
        self.assertIn('candidate_repair_spec_scope_mismatch',self.validate(doc)[0])

    def test_local_repair_drops_create_layout_pose_and_style_instructions(self):
        spec=json.loads((self.project/'visual-spec.json').read_text())
        spec.update(scene={'summary':'Rearrange the four views in a new order.'},
                    subjects=[{'pose':'Move every arm into an A-pose.'}],
                    lighting={'key':'Change the studio light.'},style='New costume design')
        prepared=handoff.prepare_candidate_repair_spec(spec,self.binding,project_root=self.project,output_spec=self.project/'repair-spec.json')
        for key in ('subjects','lighting','style'):
            self.assertNotIn(key,prepared)
        preserved=prepared['constraints']['must_preserve']
        self.assertIn(handoff.EDIT_SOURCE_REQUIREMENT,preserved)
        self.assertFalse(any('Four full-body' in item for item in preserved))
        self.assertEqual(handoff.role_spec_errors(prepared,self.asset),[])
        self.assertIn('Four full-body', '\n'.join(handoff.prepare_role_spec(spec,self.asset)['constraints']['must_preserve']))

    def test_recorded_repair_keeps_old_evidence_and_truth_without_promoting_or_reusing_pixels(self):
        old={name:(self.project/name).read_bytes() for name in ['candidate-v01.png','retry-plan.json','retry-review.json']}
        output=self.project/'candidate-v02.png';output.write_bytes(planmod.test_png_bytes(1921,1080))
        updated=planmod.record_candidate_output(self.plan,base_dir=self.project,asset_id=self.asset['asset_id'],image_path=output,execution_task_id='new-executor',repair_source=self.binding,project_root=self.project)
        row=next(a for a in updated['assets'] if a['asset_id']==self.asset['asset_id'])
        self.assertEqual(row['candidate_repair_source'],self.binding)
        self.assertEqual(row['truth_sha256'],self.asset['truth_sha256'])
        self.assertEqual(row['inherits_from'],[]);self.assertEqual(row['status'],'generated_candidate')
        self.assertIsNone(row['visual_qa_receipt']);self.assertIsNone(row['candidate_self_check'])
        self.assertEqual(planmod.validate_plan(updated,base_dir=self.project)[0],[])
        self.assertTrue(planmod.pending_candidate_self_checks(updated,base_dir=self.project,execution_task_id='another-task'))
        for name,raw in old.items():self.assertEqual((self.project/name).read_bytes(),raw)
        output.write_bytes(old['candidate-v01.png'])
        with self.assertRaisesRegex(ValueError,'new_output_pixels'):
            planmod.record_candidate_output(self.plan,base_dir=self.project,asset_id=self.asset['asset_id'],image_path=output,execution_task_id='new-executor',repair_source=self.binding,project_root=self.project)
        output.write_bytes(planmod.png_with_text_metadata(old['candidate-v01.png'],'note','same pixels'))
        with self.assertRaisesRegex(ValueError,'new_output_pixels'):
            planmod.record_candidate_output(self.plan,base_dir=self.project,asset_id=self.asset['asset_id'],image_path=output,execution_task_id='new-executor',repair_source=self.binding,project_root=self.project)


    def execution_packet(self):
        from tests.test_asset_execution_gate import AssetExecutionGateTests
        import dircreative_asset_execution_gate as gate
        doc,compiled=self.repair_document()
        handoff_binding=fixtures.write_json(self.project/'repair-handoff.json',doc)
        packet=AssetExecutionGateTests().character_packet(compiled['prompt'])
        packet['visual_plan']={'path':self.plan_binding['relative_path'],'sha256':self.plan_binding['sha256']}
        packet['candidate_repair']=self.binding
        packet['jingzao_asset_handoff']={
            'path':handoff_binding['relative_path'],'sha256':handoff_binding['sha256'],
            'provider_skill_sha256':doc['provider_skill']['sha256'],
            'compiled_prompt_manifest_sha256':doc['output_spec']['compiled_prompt_manifest']['sha256'],
            'skill_stack_receipt_sha256':doc['skill_stack_receipt']['sha256']}
        packet['prompt_authority']=gate.build_prompt_authority(self.asset,packet['prompt_sha256'],
            jingzao_handoff_sha256=handoff_binding['sha256'],jingzao_provider_skill_sha256=doc['provider_skill']['sha256'],
            jingzao_prompt_manifest_sha256=doc['output_spec']['compiled_prompt_manifest']['sha256'])
        return packet

    def test_actual_argument_gate_requires_retry_binding_and_preserves_other_pending_candidates(self):
        import dircreative_asset_execution_gate as gate
        packet=self.execution_packet()
        delivery={'imagegen_call_plan':{'status':'ready','required_input_ids':['candidate-repair-base'],
                  'expected_attachment_count':1,'mechanism':'referenced_image_paths','argument':[str(self.project/'candidate-v01.png')]}}
        def run(packet,retry=True):
            return gate.prepare_image_call(packet,project_root=self.project,reference_delivery=delivery,
                    execution_task_id='actual-test-task',retry_failed_asset=retry,
                    _trusted_jingzao_provider_roots=(self.provider,),_allow_unsandboxed_jingzao_replay_for_tests=True)
        result=run(packet)
        self.assertEqual(result['preflight_status'],'ready',result)
        self.assertEqual(result['imagegen_arguments']['referenced_image_paths'],[str(self.project/'candidate-v01.png')])
        self.assertIsNone(run(packet,False)['imagegen_arguments'])
        missing=copy.deepcopy(packet);missing.pop('candidate_repair')
        self.assertIsNone(run(missing)['imagegen_arguments'])
        forged=copy.deepcopy(packet);forged['candidate_repair']['source_image']['sha256']='0'*64
        self.assertIsNone(run(forged)['imagegen_arguments'])
        second=next(a for a in self.plan['assets'] if a['role']=='product_identity_board')
        image=self.project/'other-pending.png';image.write_bytes(planmod.test_png_bytes(1922,1080))
        self.plan=planmod.record_candidate_output(self.plan,base_dir=self.project,asset_id=second['asset_id'],image_path=image,execution_task_id='other-task')
        self.plan_binding=fixtures.write_json(self.project/'retry-plan.json',self.plan)
        self.binding=planmod.build_candidate_repair_source(project_root=self.project,visual_plan_binding=self.plan_binding,asset_id=self.asset['asset_id'],changes=self.changes)
        packet=self.execution_packet();result=run(packet)
        self.assertEqual(result['preflight_status'],'ready',result)
        self.assertIn('candidate_postcheck_required:'+second['asset_id'],
                      planmod.pending_candidate_self_checks(self.plan,base_dir=self.project,execution_task_id='audit'))

    def test_record_cli_cannot_reset_failed_review_with_renamed_old_pixels_without_repair_binding(self):
        source=self.project/'candidate-v01.png'
        renamed=self.project/'old-pixels-renamed.png';renamed.write_bytes(source.read_bytes())
        output=self.project/'unchanged-pixels-plan.json'
        command=[sys.executable,str(ROOT/'scripts/dircreative_asset_execution_gate.py'),'--record-output',
                 '--project-root',str(self.project),'--plan','retry-plan.json','--asset-id',self.asset['asset_id'],
                 '--image',renamed.name,'--execution-task-id','different-task','--output',output.name,
                 '--expected-plan-sha256',self.plan_binding['sha256']]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn('new_output_pixels_and_path',result.stdout)
        self.assertFalse(output.exists())
        actual=json.loads((self.project/'retry-plan.json').read_text())
        row=next(a for a in actual['assets'] if a['asset_id']==self.asset['asset_id'])
        self.assertEqual(row['candidate_self_check'],self.asset['candidate_self_check'])

    def test_second_repair_returns_to_bound_best_base_instead_of_degraded_latest(self):
        original_binding=copy.deepcopy(self.plan_binding)
        output=self.project/'candidate-v02.png';output.write_bytes(planmod.test_png_bytes(seed=91))
        current=planmod.record_candidate_output(self.plan,base_dir=self.project,asset_id=self.asset['asset_id'],
            image_path=output,execution_task_id='second',repair_source=self.binding,project_root=self.project)
        row=next(a for a in current['assets'] if a['asset_id']==self.asset['asset_id'])
        review=planmod.candidate_self_check_template(current,row['asset_id'])
        review.update(reviewed_at=row['technical_receipt']['checked_at'],reviewer_id='test',review_task_id='second-review')
        review['assets'][0]['decision']='retry'
        for item in review['assets'][0]['observations']:
            item.update(result='fail' if item['check_id']=='left_profile' else 'pass',observed='Unit fixture observation '+item['check_id'])
        row['candidate_self_check']=fixtures.write_json(self.project/'second-review.json',review)
        current_binding=fixtures.write_json(self.project/'second-plan.json',current)
        changes=[{'check_id':'left_profile','instruction':'Restore the missing shoulder detail in the nose-left view.'}]
        with self.assertRaisesRegex(ValueError,'best_base_or_fresh_generation'):
            planmod.build_candidate_repair_source(project_root=self.project,visual_plan_binding=current_binding,
                asset_id=row['asset_id'],changes=changes)
        with self.assertRaisesRegex(ValueError,'cover_base_defects'):
            planmod.build_candidate_repair_source(project_root=self.project,visual_plan_binding=current_binding,
                asset_id=row['asset_id'],changes=changes,base_plan_binding=original_binding)
        # Include defects known on the chosen base even if the current image
        # happened to repair them. The original purpose/truth stays bound.
        repaired=planmod.build_candidate_repair_source(project_root=self.project,visual_plan_binding=current_binding,
            asset_id=row['asset_id'],changes=changes+self.changes,base_plan_binding=original_binding)
        self.assertEqual(repaired['source_image']['relative_path'],'candidate-v01.png')
        self.assertEqual(repaired['source_plan'],current_binding)
        self.assertEqual(repaired['base_plan'],original_binding)
        prepared=handoff.prepare_candidate_repair_spec({'intent':row['purpose'],'inputs':[]},repaired,
            project_root=self.project,output_spec=self.project/'third-spec.json')
        self.assertEqual(prepared['inputs'][0]['source_ref'],'candidate-v01.png')
        forged=copy.deepcopy(original_binding);forged['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'base_plan_changed'):
            planmod.build_candidate_repair_source(project_root=self.project,visual_plan_binding=current_binding,
                asset_id=row['asset_id'],changes=changes,base_plan_binding=forged)
        copied=self.project/'copied-base.png';copied.write_bytes((self.project/'candidate-v01.png').read_bytes())
        with self.assertRaisesRegex(ValueError,'new_output_pixels'):
            planmod.record_candidate_output(current,base_dir=self.project,asset_id=row['asset_id'],image_path=copied,
                execution_task_id='third',repair_source=repaired,project_root=self.project)

    def test_exact_change_preserve_conflict_is_rejected_without_a_new_review_gate(self):
        spec={'mode':'edit','intent':self.asset['purpose'],'constraints':{
            'must_preserve':['Keep the shoulder on image-right.'],
            'must_change':['Keep the shoulder on image-right.']}}
        prepared=handoff.prepare_role_spec(spec,self.asset)
        self.assertIn('visual_asset_change_preserve_conflict',handoff.role_spec_errors(prepared,self.asset))

    def test_nonhuman_character_contract_keeps_multi_view_identity_without_human_anatomy(self):
        asset = {**self.asset, 'identity_kind': 'nonhuman', 'character_mode': 'headed_master'}
        requirements = handoff.canonical_asset_role_requirements(asset)
        compiled = '\n'.join(requirements).lower()
        self.assertIn('four complete reference views', compiled)
        self.assertNotIn('face close-up', compiled)
        self.assertNotIn('hands', compiled)
        self.assertNotIn('footwear', compiled)

    def test_legacy_human_character_contract_keeps_five_view_requirements(self):
        requirements = handoff.canonical_asset_role_requirements(self.asset)
        compiled = '\n'.join(requirements).lower()
        self.assertIn('face close-up', compiled)
        self.assertIn('four full-body views', compiled)
        self.assertIn('footwear', compiled)

    def test_prepare_and_record_clis_keep_expected_plan_guard_and_new_candidate_lineage(self):
        changes=fixtures.write_json(self.project/'changes.json',self.changes)
        command=[sys.executable,str(ROOT/'scripts/dircreative_visual_asset_jingzao_handoff.py'),'prepare-candidate-repair',
                 '--project-root',str(self.project),'--visual-plan','retry-plan.json','--expected-plan-sha256',self.plan_binding['sha256'],
                 '--asset-id',self.asset['asset_id'],'--spec','visual-spec.json','--changes','changes.json',
                 '--output-spec','cli-repair-spec.json','--output-binding','cli-repair-binding.json']
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(json.loads(result.stdout)['candidate_repair'],self.binding)
        source_sha=hashlib.sha256((self.project/'candidate-v01.png').read_bytes()).hexdigest()
        new=self.project/'candidate-v02.png';new.write_bytes(planmod.test_png_bytes(1921,1080))
        record=[sys.executable,str(ROOT/'scripts/dircreative_asset_execution_gate.py'),'--record-output','--project-root',str(self.project),
                '--plan','retry-plan.json','--asset-id',self.asset['asset_id'],'--image','candidate-v02.png','--execution-task-id','test-new-task',
                '--candidate-repair-binding','cli-repair-binding.json','--output','after-repair-plan.json','--expected-plan-sha256']
        rejected=subprocess.run(record+['0'*64],capture_output=True,text=True)
        self.assertEqual(rejected.returncode,1);self.assertFalse((self.project/'after-repair-plan.json').exists())
        self.assertIn('candidate_plan_changed_since_prepare',rejected.stdout)
        accepted=subprocess.run(record+[self.plan_binding['sha256']],capture_output=True,text=True)
        self.assertEqual(accepted.returncode,0,accepted.stdout+accepted.stderr)
        self.assertEqual(json.loads(accepted.stdout)['status'],'postcheck_required')
        actual=json.loads((self.project/'after-repair-plan.json').read_text())
        row=next(a for a in actual['assets'] if a['asset_id']==self.asset['asset_id'])
        self.assertEqual(row['candidate_repair_source'],self.binding);self.assertIsNone(row['visual_qa_receipt'])
        self.assertEqual(source_sha,hashlib.sha256((self.project/'candidate-v01.png').read_bytes()).hexdigest())


if __name__=='__main__':unittest.main()
