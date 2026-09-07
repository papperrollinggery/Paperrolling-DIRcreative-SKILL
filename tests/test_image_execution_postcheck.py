from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import dircreative_asset_execution_gate as gate
import dircreative_visual_asset_jingzao_handoff as handoff
import dircreative_visual_asset_plan as planmod
from tests import test_visual_asset_jingzao_handoff as handoff_tests
write_json = handoff_tests.write_json


class ImageExecutionPostcheckTests(unittest.TestCase):
    def test_legal_generic_compile_does_not_satisfy_character_role(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); project = root / 'project'; project.mkdir()
            provider = root / 'providers/jingzao-image-forge'
            document, _ = handoff_tests.VisualAssetJingzaoHandoffTests().fixture(project, provider, first_image=True)
            # Generic compiler legality is distinct from adopting the asset role.
            spec_path = project / document['output_spec']['visual_generation_spec']['relative_path']
            spec = json.loads(spec_path.read_text()); spec.pop('constraints', None)
            document['output_spec']['visual_generation_spec'] = write_json(spec_path, spec)
            errors, _ = handoff.validate(document, project_root=project, provider_root=provider,
                                        trusted_provider_roots=(provider,), allow_unsandboxed_test_replay=True)
            self.assertIn('visual_asset_role_requirements_missing', errors)



class LiveCallAndCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        fixture = ROOT / 'tests/fixtures/asset-execution'
        for name in ('character-plan.json', 'character-inventory.json', 'character-creative-source.json', 'character-shot-cards.json'):
            (self.root / name).write_bytes((fixture / name).read_bytes())
        self.plan = json.loads((self.root / 'character-plan.json').read_text())
        self.asset = next(a for a in self.plan['assets'] if a['role'] == 'product_identity_board')
        self.task = 'unit-execution-task'
        self.delivery = {'imagegen_call_plan': {'status': 'ready', 'errors': [], 'required_input_ids': [],
                         'expected_attachment_count': 0, 'mechanism': 'none', 'argument': None}}

    def packet(self, plan=None):
        selected = self.plan if plan is None else plan
        binding = write_json(self.root / 'live-plan.json', selected)
        active = next(a for a in selected['assets'] if a['asset_id'] == self.asset['asset_id'])
        prompt = gate.build_role_prompt(active, selected)
        ref = 'skills/dircreative/references/asset-foundation-pass.md'
        return {'contract_id': gate.CONTRACT_ID, 'asset_id': active['asset_id'], 'asset_role': active['role'],
                'media_scope': 'pre_video_assets', 'authorization': {'source': 'validated_route_context', 'image_generation': True, 'video_generation': False},
                'visual_plan': {'path': binding['relative_path'], 'sha256': binding['sha256']},
                'active_asset_truth_sha256': active['truth_sha256'],
                'stage_contract': {'stage_id': 'production_design', 'reference': ref, 'sha256': hashlib.sha256((ROOT/ref).read_bytes()).hexdigest()},
                'dependencies': [], 'execution': {'adapter': 'imagegen', 'mode': 'serial_review_gated', 'parallel_group': None},
                'prompt': prompt, 'prompt_sha256': gate.sha256_text(prompt),
                'prompt_authority': gate.build_prompt_authority(active, gate.sha256_text(prompt))}

    def prepare(self, packet, **kwargs):
        return gate.prepare_image_call(packet, project_root=self.root, reference_delivery=self.delivery,
                                       execution_task_id=self.task, **kwargs)

    def saved(self):
        image = self.root/'actual-fixture-output.png'
        image.write_bytes(planmod.test_png_bytes(1920, 1080))
        return planmod.record_candidate_output(self.plan, base_dir=self.root, asset_id=self.asset['asset_id'],
                                              image_path=image, execution_task_id=self.task)

    def observed(self, candidate, decision='checked'):
        manifest = planmod.candidate_self_check_template(candidate, self.asset['asset_id'])
        row = next(a for a in candidate['assets'] if a['asset_id'] == self.asset['asset_id'])
        manifest.update(reviewed_at=row['technical_receipt']['checked_at'], reviewer_id='unit-executor', review_task_id=self.task)
        entry=manifest['assets'][0]; entry['decision']=decision
        for item in entry['observations']:
            item.update(result='pass', observed='Unit fixture observation only: '+item['check_id'])
        return manifest

    def bind(self, candidate, manifest):
        result=copy.deepcopy(candidate)
        binding=write_json(self.root/'candidate-review.json', manifest)
        next(a for a in result['assets'] if a['asset_id']==self.asset['asset_id'])['candidate_self_check']=binding
        return result

    def test_live_arguments_use_validated_prompt_and_reject_stale_packet_and_foreign_references(self):
        packet=self.packet(); result=self.prepare(packet)
        self.assertEqual(result['preflight_status'], 'ready', result)
        self.assertEqual(result['imagegen_arguments'], {'prompt':packet['prompt']})
        changed=copy.deepcopy(packet); changed['prompt']+=' arbitrary change'
        self.assertIsNone(self.prepare(changed)['imagegen_arguments'])
        self.delivery['imagegen_call_plan'].update(mechanism='referenced_image_paths', argument=['/unbound.png'])
        self.assertIsNone(self.prepare(packet)['imagegen_arguments'])
        self.delivery['imagegen_call_plan'].update(mechanism='none', argument=None)
        (self.root/'live-plan.json').write_text('{}')
        self.assertIsNone(self.prepare(packet)['imagegen_arguments'])

    def test_registered_output_blocks_batch_then_specific_observations_unlock_only_iteration(self):
        candidate=self.saved(); asset=next(a for a in candidate['assets'] if a['asset_id']==self.asset['asset_id'])
        self.assertEqual(asset['status'],'generated_candidate'); self.assertIsNone(asset['visual_qa_receipt'])
        self.assertEqual(planmod.validate_plan(candidate,base_dir=self.root)[0],[])
        result=self.prepare(self.packet(candidate))
        self.assertIn('candidate_postcheck_required:'+self.asset['asset_id'],result['errors'])
        self.assertIsNone(result['imagegen_arguments'])
        manifest=self.observed(candidate)
        missing=copy.deepcopy(manifest); missing['assets'][0]['observations'].pop()
        self.assertEqual(planmod.validate_candidate_self_check(missing,payload=candidate,asset_id=self.asset['asset_id'],base_dir=self.root),['candidate_self_check_role_coverage_invalid'])
        reviewed=self.bind(candidate,manifest)
        self.assertEqual(self.prepare(self.packet(reviewed))['preflight_status'],'ready')
        self.assertIsNone(next(a for a in reviewed['assets'] if a['asset_id']==self.asset['asset_id'])['visual_qa_receipt'])
        _,problem=planmod.validate_visual_review_manifest(manifest,payload=reviewed,evidence_by_asset={},truth_locked_at=reviewed['truth_locked_at'])
        self.assertIsNotNone(problem,'executor self-check cannot become independent approval')
        manifest['reviewer_type']='independent_ai'
        self.assertTrue(planmod.validate_candidate_self_check(manifest,payload=candidate,asset_id=self.asset['asset_id'],base_dir=self.root))

    def test_changed_pixels_or_review_fails_closed_and_retry_is_explicit(self):
        candidate=self.saved(); review=self.observed(candidate,decision='retry')
        review['assets'][0]['observations'][0].update(result='fail',observed='Unit fixture: material failure visible in the saved candidate.')
        reviewed=self.bind(candidate,review); packet=self.packet(reviewed)
        self.assertIsNone(self.prepare(packet)['imagegen_arguments'])
        # Focused retry is allowed only for the reviewed failing asset, never a batch bypass.
        retry=self.prepare(packet,retry_failed_asset=True)
        self.assertEqual(retry['preflight_status'],'ready',retry)
        (self.root/'actual-fixture-output.png').write_bytes(planmod.test_png_bytes(1921,1080))
        self.assertIsNone(self.prepare(packet,retry_failed_asset=True)['imagegen_arguments'])

    def test_resuming_same_plan_with_new_task_id_cannot_skip_pending_candidate(self):
        candidate=self.saved(); packet=self.packet(candidate)
        result=gate.prepare_image_call(packet,project_root=self.root,reference_delivery=self.delivery,execution_task_id='another-task')
        self.assertIsNone(result['imagegen_arguments'], result)
        self.assertIn('candidate_postcheck_required:'+self.asset['asset_id'], result['errors'])

    def test_record_and_failed_check_cli_preserve_candidate_and_error_observations(self):
        image=self.root/'input.png'; image.write_bytes(planmod.test_png_bytes(1920,1080))
        command=[sys.executable,str(ROOT/'scripts/dircreative_asset_execution_gate.py'),'--project-root',str(self.root)]
        expected_plan_hash=hashlib.sha256((self.root/'character-plan.json').read_bytes()).hexdigest()
        run=subprocess.run(command+['--record-output','--plan','character-plan.json','--expected-plan-sha256',expected_plan_hash,'--asset-id',self.asset['asset_id'],'--image','input.png','--execution-task-id',self.task,'--output','saved.json'],text=True,capture_output=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)
        candidate=json.loads((self.root/'saved.json').read_text()); review=self.observed(candidate,'retry')
        write_json(self.root/'retry.json',review)
        check=subprocess.run(command+['--check-output','--plan','saved.json','--asset-id',self.asset['asset_id'],'--self-check-manifest','retry.json','--output','checked.json'],text=True,capture_output=True)
        self.assertEqual(check.returncode,1,check.stdout+check.stderr)
        self.assertEqual(json.loads(check.stdout)['status'],'postcheck_failed')
        checked=json.loads((self.root/'checked.json').read_text()); asset=next(a for a in checked['assets'] if a['asset_id']==self.asset['asset_id'])
        self.assertEqual(asset['status'],'generated_candidate'); self.assertEqual(asset['generated_file'],'input.png')
        self.assertIsNotNone(asset['candidate_self_check']); self.assertIsNone(asset['visual_qa_receipt'])

    def test_output_registration_rejects_a_plan_changed_during_generation(self):
        prepared=self.prepare(self.packet())
        self.assertEqual(prepared['preflight_status'],'ready',prepared)
        image=self.root/'input.png'; image.write_bytes(planmod.test_png_bytes(1920,1080))
        changed=dict(self.plan); changed['completion_claim']='none' if self.plan['completion_claim'] != 'none' else 'plan_complete'
        write_json(self.root/'live-plan.json',changed)
        run=subprocess.run([
            sys.executable,str(ROOT/'scripts/dircreative_asset_execution_gate.py'),
            '--project-root',str(self.root),'--record-output','--plan',prepared['visual_plan_path'],
            '--expected-plan-sha256',prepared['visual_plan_sha256'],'--asset-id',self.asset['asset_id'],
            '--image',str(image),'--execution-task-id',self.task,'--output','wrong-truth.json',
        ],text=True,capture_output=True)
        self.assertNotEqual(run.returncode,0,run.stdout)
        self.assertIn('candidate_plan_changed_since_prepare',run.stdout)
        self.assertFalse((self.root/'wrong-truth.json').exists())
        self.assertTrue(image.is_file())

    def test_record_cli_accepts_absolute_paths_under_the_supplied_project_root(self):
        prepared=self.prepare(self.packet())
        image=self.root/'absolute-output.png'; image.write_bytes(planmod.test_png_bytes(1920,1080))
        run=subprocess.run([
            sys.executable,str(ROOT/'scripts/dircreative_asset_execution_gate.py'),
            '--project-root',str(self.root),'--record-output','--plan',str(self.root/'live-plan.json'),
            '--expected-plan-sha256',prepared['visual_plan_sha256'],'--asset-id',self.asset['asset_id'],
            '--image',str(image),'--execution-task-id',self.task,'--output',str(self.root/'registered-absolute.json'),
        ],text=True,capture_output=True)
        self.assertEqual(run.returncode,0,run.stdout+run.stderr)


    def test_pending_product_blocks_a_different_dependency_free_asset(self):
        candidate=self.saved()
        prior_id=self.asset['asset_id']
        self.asset=next(a for a in self.plan['assets'] if a['role']=='prop_continuity_board')
        packet=self.packet(candidate)
        self.assertEqual(packet['dependencies'],[])
        for retry in (False,True):
            result=self.prepare(packet,retry_failed_asset=retry)
            self.assertIn('candidate_postcheck_required:'+prior_id,result['errors'])
            self.assertIsNone(result['imagegen_arguments'])

    def test_character_checklist_alone_cannot_replace_actual_structure_probe(self):
        self.asset=next(a for a in self.plan['assets'] if a['role']=='character_identity_reference')
        candidate=self.saved(); manifest=self.observed(candidate)
        errors=planmod.validate_candidate_self_check(manifest,payload=candidate,asset_id=self.asset['asset_id'],base_dir=self.root)
        self.assertIn('candidate_self_check_character_structure_failed',errors)
        self.assertIn('character_master_visual_receipt_missing_or_invalid',errors)
        manifest['assets'][0]['observations'][4]['result']='not_applicable'
        self.assertIn('candidate_self_check_required_observation_not_applicable',planmod.validate_candidate_self_check(
            manifest,payload=candidate,asset_id=self.asset['asset_id'],base_dir=self.root))

    def test_registration_does_not_accept_symlink_or_external_output(self):
        image=self.root/'physical.png'; image.write_bytes(planmod.test_png_bytes(1920,1080))
        linked=self.root/'symlink.png'; linked.symlink_to(image)
        with self.assertRaises(ValueError):
            planmod.record_candidate_output(self.plan,base_dir=self.root,asset_id=self.asset['asset_id'],image_path=linked,execution_task_id=self.task)
        with tempfile.TemporaryDirectory() as raw:
            outside=Path(raw)/'outside.png'; outside.write_bytes(image.read_bytes())
            with self.assertRaises(ValueError):
                planmod.record_candidate_output(self.plan,base_dir=self.root,asset_id=self.asset['asset_id'],image_path=outside,execution_task_id=self.task)

    def test_prepare_call_checks_exact_local_reference_order_and_bytes(self):
        from tests.test_asset_execution_gate import AssetExecutionGateTests
        provider=self.root/'provider/jingzao-image-forge'
        project=self.root/'motion-project';project.mkdir()
        packet,request,_=AssetExecutionGateTests().rough_motion_fixture(project,provider,planning_target=True)
        paths=[str((project/f'user-reference-{i}.png').resolve()) for i in range(2)]
        delivery={'imagegen_call_plan':{'status':'ready','required_input_ids':['ref-0','ref-1'],
                  'expected_attachment_count':2,'mechanism':'referenced_image_paths','argument':paths}}
        def run():
            return gate.prepare_image_call(packet,project_root=project,reference_delivery=delivery,
                    execution_task_id=self.task,request_text=request,_trusted_jingzao_provider_roots=(provider,),
                    _allow_unsandboxed_jingzao_replay_for_tests=True)
        self.assertEqual(run()['imagegen_arguments'],{'prompt':packet['prompt'],'referenced_image_paths':paths})
        delivery['imagegen_call_plan']['argument']=list(reversed(paths))
        self.assertIsNone(run()['imagegen_arguments'])
        delivery['imagegen_call_plan']['argument']=paths
        (project/'user-reference-0.png').write_bytes(planmod.test_png_bytes(17,16))
        self.assertIsNone(run()['imagegen_arguments'])


class CanonicalRoleCompilationTests(unittest.TestCase):
    def test_role_mode_replacement_removes_stale_dir_constraints_only(self):
        plan=json.loads((ROOT/'tests/fixtures/asset-execution/character-plan.json').read_text())
        master=next(a for a in plan['assets'] if a['role']=='character_identity_reference')
        original={'mode':'create','intent':master['purpose'],'constraints':{'must_preserve':['Keep the supplied 2D ink medium.']}}
        spec=handoff.prepare_role_spec(original,master)
        derivative={**master,'character_mode':'headless_safe'}
        spec['mode']='edit'
        polluted=copy.deepcopy(spec)
        polluted['constraints']['must_preserve']+=handoff.canonical_asset_role_requirements(derivative)
        self.assertIn('visual_asset_role_requirements_stale',handoff.role_spec_errors(polluted,derivative))
        fixed=handoff.prepare_role_spec(spec,derivative)
        self.assertEqual(handoff.role_spec_errors(fixed,derivative),[])
        self.assertEqual(fixed['mode'],'edit')
        self.assertIn('Keep the supplied 2D ink medium.',fixed['constraints']['must_preserve'])
        self.assertFalse(any('views are headed' in item or 'nose pointing' in item for item in fixed['constraints']['must_preserve']))
        self.assertTrue(any('fully headless' in item for item in fixed['constraints']['must_preserve']))

    def test_five_foundation_roles_get_canonical_constraints_without_changing_create_or_ratio(self):
        plan=json.loads((ROOT/'tests/fixtures/asset-execution/character-plan.json').read_text())
        roles={'character_identity_reference','product_identity_board','prop_continuity_board',
               'scene_geography_camera_fov_reference','lighting_material_style_board'}
        for asset in plan['assets']:
            if asset['role'] not in roles:
                continue
            with self.subTest(role=asset['role']):
                spec={'visual_generation_spec':'1.0','mode':'create','intent':asset['purpose'],
                      'canvas':{'aspect_ratio':'16:9'},'inputs':[],
                      'constraints':{'must_preserve':['Keep the supplied artistic medium.']}}
                prepared=handoff.prepare_role_spec(spec,asset)
                self.assertEqual(prepared['mode'],'create'); self.assertEqual(prepared['canvas'],spec['canvas'])
                self.assertEqual(spec['constraints']['must_preserve'],['Keep the supplied artistic medium.'])
                self.assertEqual(handoff.role_spec_errors(prepared,asset),[])
                self.assertEqual(handoff.prepare_role_spec(prepared,asset),prepared)
                prepared['constraints']['must_preserve'].pop(0)
                self.assertEqual(handoff.role_spec_errors(prepared,asset),['visual_asset_role_requirements_missing'])
        character=next(a for a in plan['assets'] if a['role']=='character_identity_reference')
        normal=handoff.canonical_asset_role_requirements(character)
        self.assertTrue(any('anatomical left profile' in item and 'anatomical right profile' in item for item in normal))
        headless=handoff.canonical_asset_role_requirements({**character,'character_mode':'headless_safe'})
        self.assertFalse(any('nose pointing' in item for item in headless))
        self.assertTrue(any('fully headless' in item for item in headless))

    def test_even_replayed_compiler_cannot_drop_canonical_spec_requirements(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); project=root/'project'; project.mkdir(); provider=root/'provider/jingzao-image-forge'
            document,_=handoff_tests.VisualAssetJingzaoHandoffTests().fixture(project,provider,first_image=True)
            script=provider/'scripts/compile_prompt.py'
            lines=script.read_text().splitlines()
            prompt_lines=[i for i,line in enumerate(lines) if line.startswith("prompt=")]
            self.assertEqual(len(prompt_lines),1)
            lines[prompt_lines[0]]="prompt='Goal:\\n'+spec['intent']"
            script.write_text("\n".join(lines)+"\n")
            runtime=next(x for x in document['provider_runtime_files'] if x['relative_path']=='scripts/compile_prompt.py')
            runtime.update(sha256=hashlib.sha256(script.read_bytes()).hexdigest(),bytes=script.stat().st_size)
            run=subprocess.run([sys.executable,str(script),str(project/'visual-spec.json')],text=True,capture_output=True)
            self.assertEqual(run.returncode,0,run.stderr)
            compiled=json.loads(run.stdout)
            document['output_spec']['compiled_prompt_manifest']=write_json(project/'compiled.json',compiled)
            sha=hashlib.sha256(compiled['prompt'].encode()).hexdigest()
            document['output_spec']['prompt_sha256']=sha; document['delivery_consumption']['consumed_prompt_sha256']=sha
            errors,_=handoff.validate(document,project_root=project,provider_root=provider,
                                      trusted_provider_roots=(provider,),allow_unsandboxed_test_replay=True)
            self.assertIn('jingzao_compiler_dropped_asset_role_requirements',errors)


if __name__ == '__main__':
    unittest.main()
