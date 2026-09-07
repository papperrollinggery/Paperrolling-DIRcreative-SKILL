from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_narrative_spec_preflight as preflight  # noqa: E402


def narrative_spec() -> dict:
    return {
        "visual_generation_spec": "1.0",
        "mode": "create",
        "platform": "openai",
        "intent": "A 16:9 narrative frame of a courier handing a ledger to a witness under a rainy archway while a guard blocks their exit.",
        "canvas": {"aspect_ratio": "16:9"},
        "constraints": {"must_preserve": [], "must_change": [], "exclude": []},
        "direction": {"deliverable": "narrative_film_frame"},
        "cinematic": {"profile": "narrative_film_frame", "shot_function": "emphasize", "visible_event": "A ledger changes hands in the rain.", "relationship_pressure": "A guard blocks the exit.", "viewer_task": "See who holds the ledger.", "viewer_position": "Inside the archway.", "frozen_moment": "The ledger reaches both hands.", "withheld_information": "The guard's intention remains uncertain.", "posterization_guard": True},
        "lighting": {"summary": "Overcast daylight reflected by wet stone reveals faces and sleeve weave.", "motivation": "Daylight enters the open archway and bounces from wet stone.", "narrative_function": "Keep the handover readable while the guard remains partially shadowed."},
        "staging": {"primary_relationship": "Courier protects witness from guard.", "subject_positions": ["courier left", "witness right"], "eyeline_logic": "witness looks to courier", "screen_direction": "courier to archway", "axis": "alley line", "occlusion": "arch edge frames witness", "attention_path": "ledger to hands to guard"},
        "composition": {"camera_motivation": "Show transfer and threat in one view.", "camera_height": "eye level", "camera_distance": "medium", "lens_rationale": "read hands and space", "foreground_logic": "arch edge anchors the observer"},
    }


class NarrativeSpecPreflightTests(unittest.TestCase):
    def write_json(self, root: Path, name: str, value: object) -> Path:
        path = root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_generic_c_style_spec_is_rejected_before_provider_runs(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); path = self.write_json(root, "generic.json", {"visual_generation_spec": "1.0"})
            with mock.patch.object(preflight, "run_json_command") as runner:
                code, result = preflight.preflight(root, path.name)
            self.assertEqual(code, 1)
            self.assertIn("narrative_deliverable_required", result["errors"])
            runner.assert_not_called()

    def test_narrative_spec_runs_existing_provider_validator_and_compiler(self):
        with tempfile.TemporaryDirectory() as project_raw, tempfile.TemporaryDirectory() as provider_raw:
            root = Path(project_raw); path = self.write_json(root, "narrative.json", narrative_spec())
            provider = Path(provider_raw) / "jingzao-image-forge"
            provider.mkdir(); (provider / "SKILL.md").write_text("skill", encoding="utf-8"); (provider / "scripts").mkdir()
            for name in ("validate_spec.py", "compile_prompt.py", "reference_delivery.py"): (provider / "scripts" / name).write_text("# test", encoding="utf-8")
            native_plan = {"mechanism": "referenced_image_paths", "argument": [], "status": "ready"}
            outputs = [({"valid": True, "errors": []}, None), ({"prompt": "compiled narrative prompt", "prompt_review": {"status": "ready"}, "imagegen_call_plan": native_plan}, None), ({"valid": True, "imagegen_call_plan": native_plan}, None)]
            with mock.patch.object(preflight, "trusted_provider_roots", return_value=(provider,)), mock.patch.object(preflight, "run_json_command", side_effect=outputs) as runner:
                code, result = preflight.preflight(root, path.name, provider)
            self.assertEqual(code, 0)
            self.assertEqual(result["status"], "compile_only")
            self.assertEqual(result["verification"], "unverified")
            self.assertEqual(result["compiled"]["prompt"], "compiled narrative prompt")
            self.assertEqual(result["call_plan"], native_plan)
            self.assertEqual(runner.call_count, 3)

    def test_style_capsule_is_passed_to_compiler_without_becoming_an_attachment(self):
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as provider_raw:
            root=Path(raw); path=self.write_json(root,"narrative.json",narrative_spec()); capsule=self.write_json(root,"capsule.json",{"id":"c"})
            provider=Path(provider_raw)/"jingzao-image-forge"; provider.mkdir(); (provider/"SKILL.md").write_text("skill"); (provider/"scripts").mkdir()
            for name in ("validate_spec.py","compile_prompt.py","reference_delivery.py"): (provider/"scripts"/name).write_text("#")
            outputs=[({"valid":True,"errors":[]},None),({"prompt":"p","prompt_review":{"status":"ready"}},None),({"valid":True,"imagegen_call_plan":{"status":"ready","expected_attachment_count":0}},None)]
            with mock.patch.object(preflight,"trusted_provider_roots",return_value=(provider,)),mock.patch.object(preflight,"run_json_command",side_effect=outputs) as run:
                code,result=preflight.preflight(root,path.name,provider,style_capsule=capsule.name)
            self.assertEqual(code,0); compiler=run.call_args_list[1].args[0]; self.assertIn("--style-capsule",compiler); self.assertEqual(run.call_args_list[2].args[0][-1],"codex_imagegen")
            self.assertEqual(result['style_capsule'],{'relative_path':capsule.name,'sha256':hashlib.sha256(capsule.read_bytes()).hexdigest()})
            self.assertFalse(Path(compiler[compiler.index('--style-capsule')+1]).exists())

    def test_capsule_missing_escape_mutation_and_provider_failure_do_not_leave_snapshots(self):
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as provider_raw:
            root=Path(raw);path=self.write_json(root,'frame.json',narrative_spec())
            capsule=self.write_json(root,'style.json',{'palette':'ivory turquoise'})
            provider=Path(provider_raw)/'provider';(provider/'scripts').mkdir(parents=True)
            (provider/'SKILL.md').write_text('fixture')
            for name in ('validate_spec.py','compile_prompt.py','reference_delivery.py'):(provider/'scripts'/name).write_text('# fixture')
            with mock.patch.object(preflight,'trusted_provider_roots',return_value=(provider,)):
                for missing in ('missing.json','../style.json'):
                    with mock.patch.object(preflight,'run_json_command') as runner:
                        code,result=preflight.preflight(root,path.name,provider,style_capsule=missing)
                    self.assertEqual(code,1);runner.assert_not_called()
                with mock.patch.object(preflight,'run_json_command') as runner:
                    compiled,_,error=preflight.compile_snapshot(provider,path,path.read_bytes(),style_capsule=b'null')
                self.assertIsNone(compiled);self.assertEqual(error,'style_capsule_json_object_required');runner.assert_not_called()
                original=capsule.read_bytes()
                def runner(command,**kwargs):
                    if 'compile_prompt.py' in str(command):
                        snapshot=Path(command[command.index('--style-capsule')+1])
                        self.assertEqual(snapshot.read_bytes(),original)
                        capsule.write_text('{}')
                        return {'prompt':'ivory turquoise','prompt_review':{'status':'ready'}},None
                    if 'validate_spec.py' in str(command):return {'valid':True,'errors':[]},None
                    return {'valid':True,'imagegen_call_plan':{'status':'ready'}},None
                with mock.patch.object(preflight,'run_json_command',side_effect=runner):
                    code,result=preflight.preflight(root,path.name,provider,style_capsule=capsule.name)
                self.assertEqual(code,1);self.assertIn('style_capsule_changed_during_provider_replay',result['errors'])
                self.assertEqual(list(root.glob('.*.narrative-*')),[])
                with mock.patch.object(preflight,'run_json_command',side_effect=[({'valid':True,'errors':[]},None),RuntimeError('provider failure')]):
                    with self.assertRaisesRegex(RuntimeError,'provider failure'):
                        preflight.compile_snapshot(provider,path,path.read_bytes(),style_capsule=original)
                self.assertEqual(list(root.glob('.*.narrative-*')),[])

    def test_surface_review_is_accepted_but_blocking_and_unknown_approval_are_not(self):
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as provider_raw:
            root=Path(raw);path=self.write_json(root,'frame.json',narrative_spec())
            provider=Path(provider_raw)/'provider';(provider/'scripts').mkdir(parents=True)
            (provider/'SKILL.md').write_text('fixture')
            for name in ('validate_spec.py','compile_prompt.py','reference_delivery.py'):(provider/'scripts'/name).write_text('# fixture')
            valid={'status':'approved','approval_scope':'surface_risk_length_and_reference_complexity','reasons':['surface_risk_language:ultra detailed']}
            for review,expected in [(valid,0),({**valid,'reasons':['context_residue:as above']},1),({**valid,'approval_scope':'all'},1)]:
                outputs=[({'valid':True,'errors':[]},None),({'prompt':'full material details','prompt_review':review},None),({'valid':True,'imagegen_call_plan':{'status':'ready'}},None)]
                with mock.patch.object(preflight,'trusted_provider_roots',return_value=(provider,)),mock.patch.object(preflight,'run_json_command',side_effect=outputs):
                    code,_=preflight.preflight(root,path.name,provider,approve_review=True)
                self.assertEqual(code,expected)

    def test_a_to_b_to_a_source_mutation_cannot_change_provider_snapshot(self):
        with tempfile.TemporaryDirectory() as project_raw, tempfile.TemporaryDirectory() as provider_raw:
            root = Path(project_raw); path = self.write_json(root, "narrative.json", narrative_spec())
            provider = Path(provider_raw) / "jingzao-image-forge"; provider.mkdir(); (provider / "SKILL.md").write_text("skill", encoding="utf-8"); (provider / "scripts").mkdir()
            for name in ("validate_spec.py", "compile_prompt.py", "reference_delivery.py"): (provider / "scripts" / name).write_text("# test", encoding="utf-8")
            original = path.read_bytes()
            seen_snapshots: list[bytes] = []
            def runner(*args, **kwargs):
                snapshot = Path(next(value for value in args[0] if str(value).endswith(".json")))
                seen_snapshots.append(snapshot.read_bytes())
                if "validate_spec.py" in str(args[0]):
                    path.write_text(json.dumps({**narrative_spec(), "intent": "scarlet lighthouse"}), encoding="utf-8")
                    return {"valid": True, "errors": []}, None
                if "compile_prompt.py" in str(args[0]):
                    path.write_bytes(original)
                    return {"prompt": "compiled", "prompt_review": {"status": "ready"}}, None
                if "reference_delivery.py" in str(args[0]):
                    return {"valid": True, "imagegen_call_plan": {"status": "ready"}}, None
            with mock.patch.object(preflight, "trusted_provider_roots", return_value=(provider,)), mock.patch.object(preflight, "run_json_command", side_effect=runner):
                code, result = preflight.preflight(root, path.name, provider)
            self.assertEqual(code, 0)
            self.assertEqual(path.read_bytes(), original)
            self.assertTrue(seen_snapshots)
            self.assertTrue(all(payload == original for payload in seen_snapshots))

    def test_output_spec_uses_only_native_single_frame_or_production_manifest(self):
        frame = {"id": "P-S01", "shot_id": "S01"}
        self.assertEqual(preflight.output_spec_errors(narrative_spec(), [frame]), [])
        manifest = {"production_manifest": "1.0", "frames": [{**frame, "spec": narrative_spec()}]}
        self.assertEqual(preflight.output_spec_errors(manifest, [frame]), [])
        self.assertIn("output_spec_envelope_invalid", preflight.output_spec_errors({"spec": narrative_spec()}, [frame]))

    def test_bound_output_replays_only_manifest_bound_nonblocking_approval(self):
        with tempfile.TemporaryDirectory() as project_raw, tempfile.TemporaryDirectory() as provider_raw:
            root = Path(project_raw); provider = Path(provider_raw) / "jingzao-image-forge"; provider.mkdir(); (provider / "scripts").mkdir(); (provider / "SKILL.md").write_text("skill")
            for name in ("validate_spec.py", "compile_prompt.py", "reference_delivery.py"):
                (provider / "scripts" / name).write_text("# runtime")
            spec = narrative_spec(); output = {"production_manifest": "1.0", "frames": [{"id": "P-S01", "shot_id": "S01", "spec": spec}]}
            output_bytes = json.dumps(output).encode(); (root / "output.json").write_bytes(output_bytes)
            prompt = "compiled"; manifest = {"frame_prompts": [{"frame_id": "P-S01", "prompt": prompt, "prompt_sha256": __import__("hashlib").sha256(prompt.encode()).hexdigest(), "prompt_review": {"status": "approved", "approval_scope": "length_and_reference_complexity_only"}}]}
            manifest_bytes = json.dumps(manifest).encode(); (root / "prompts.json").write_bytes(manifest_bytes)
            binding = {"relative_path": "output.json", "sha256": __import__("hashlib").sha256(output_bytes).hexdigest(), "prompt_manifest_relative_path": "prompts.json", "prompt_manifest_sha256": __import__("hashlib").sha256(manifest_bytes).hexdigest()}
            compiled = {"prompt": prompt, "prompt_review": manifest["frame_prompts"][0]["prompt_review"]}
            with mock.patch.object(preflight, "compile_snapshot", return_value=(compiled, {"valid": True, "errors": []}, None)) as replay:
                errors = preflight.bound_output_spec_errors(root, binding, [{"frame_id": "P-S01", "shot_id": "S01"}], provider_root=provider)
            self.assertEqual(errors, [])
            self.assertTrue(replay.call_args.kwargs["approve_review"])
            capsule=self.write_json(root,'style.json',{'palette':'ivory and turquoise'})
            binding['style_capsule']={'relative_path':capsule.name,'sha256':hashlib.sha256(capsule.read_bytes()).hexdigest()}
            with mock.patch.object(preflight,'compile_snapshot',return_value=(compiled,{'valid':True,'errors':[]},None)) as replay:
                self.assertEqual(preflight.bound_output_spec_errors(root,binding,[{'frame_id':'P-S01','shot_id':'S01'}],provider_root=provider),[])
                self.assertEqual(replay.call_args.kwargs['style_capsule'],capsule.read_bytes())
            for bad in ({'relative_path':'missing.json','sha256':'0'*64},
                        {'relative_path':'../style.json','sha256':binding['style_capsule']['sha256']},
                        {'relative_path':'style.json','sha256':'0'*64}):
                changed={**binding,'style_capsule':bad}
                self.assertIn('narrative_style_capsule_invalid_or_changed',preflight.bound_output_spec_errors(root,changed,[{'frame_id':'P-S01','shot_id':'S01'}],provider_root=provider))

    def test_storyboard_handoff_schema_accepts_the_same_two_field_capsule_binding(self):
        import dircreative_storyboard_frame_handoff as handoff
        document=json.loads((ROOT/'tests/fixtures/storyboard-frame-jingzao/valid-chain.json').read_text())
        document['output_spec']['style_capsule']={'relative_path':'styles/changsheng.json','sha256':'a'*64}
        self.assertEqual(handoff.validate(document),[])
        document['output_spec']['style_capsule']['artifact_id']='unnecessary-field'
        self.assertTrue(any(error.startswith('schema_error:') for error in handoff.validate(document)))
