from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_prepare_asset as prepare  # noqa: E402
import tests.test_visual_asset_jingzao_handoff as visual_fixture  # noqa: E402


class PrepareAssetTests(unittest.TestCase):
    def fixture_inputs(self, project: Path, provider: Path) -> tuple[str, str, str]:
        # Reuse the formal handoff fixture's real plan/provider shape, then make
        # only the source inputs and design payload this helper owns.
        visual_fixture.VisualAssetJingzaoHandoffTests().fixture(project, provider, first_image=True)
        # The shared handoff fixture only needs this provider file to exist.
        # This helper exercises the actual delivery call, so make the fixture
        # return the documented, input-derived delivery receipt.
        (provider / "scripts/reference_delivery.py").write_text(
            "import json,sys\n"
            "from pathlib import Path\n"
            "spec=json.load(open(sys.argv[1]))\n"
            "items=[x for x in spec.get('inputs',[]) if x.get('must_attach')]\n"
            "ids=[x['id'] for x in items]\n"
            "paths=[str((Path(sys.argv[1]).parent/x['source_ref']).resolve()) for x in items]\n"
            "print(json.dumps({'imagegen_call_plan':{'status':'ready','errors':[],'required_input_ids':ids,'expected_attachment_count':len(ids),'mechanism':'referenced_image_paths' if ids else 'none','argument':paths if paths else None}}))\n",
            encoding="utf-8",
        )
        plan = json.loads((project / "visual-plan.json").read_text())
        asset = next(item for item in plan["assets"] if item["role"] == "character_identity_reference")
        spec = {"visual_generation_spec": "1.0", "mode": "create", "intent": asset["purpose"], "inputs": [],
                "character_master": {"mode": "headed_master", "layout": "single_horizontal_row", "portrait_position": "far_left",
                                     "full_body_views": ["front", "left_profile", "right_profile", "back"], "min_subject_height_ratio": 0.75,
                                     "body_scale": "equal", "ground_line": "shared", "identity_facts": ["33-year-old Chinese woman", "oval face", "neat low bun"],
                                     "wardrobe_facts": ["charcoal tailored suit", "off-white blouse", "black flat shoes"],
                                     "wardrobe_materials": ["charcoal wool suiting", "matte cotton blouse"], "side_specific_details": ["one earpiece at the right ear"]}}
        (project / "source-spec.json").write_text(json.dumps(spec), encoding="utf-8")
        design = {"contract_id": "asset_foundation_stage_artifact_v1", "artifact_id": "caller-authored-identity", "payload": {"asset_descriptors": [asset["asset_id"]], "state_families": ["office-look"]}}
        (project / "design.json").write_text(json.dumps(design), encoding="utf-8")
        return asset["asset_id"], "source-spec.json", "design.json"

    def test_prepares_validated_native_call_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "project"; project.mkdir(); provider = Path(raw) / "provider/jingzao-image-forge"
            asset_id, spec, design = self.fixture_inputs(project, provider)
            request = "$dircreative 创建这个长期角色的人物母版资产，固定面部、服装材质和左右细节"
            result = prepare.prepare_asset(project_root=project, plan_path="visual-plan.json", asset_id=asset_id, source_spec_path=spec, design_artifact_path=design, original_request=request, output_dir=".production/prepare-a", execution_task_id="test-run-a", provider_root=provider, _test_mode=True)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["imagegen_arguments"].get("referenced_image_paths"), None)
            again = prepare.prepare_asset(project_root=project, plan_path="visual-plan.json", asset_id=asset_id, source_spec_path=spec, design_artifact_path=design, original_request=request, output_dir=".production/prepare-a", execution_task_id="test-run-a", provider_root=provider, _test_mode=True)
            self.assertEqual(again, result)

    def test_missing_design_fields_and_changed_input_do_not_fallback_or_overwrite(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "project"; project.mkdir(); provider = Path(raw) / "provider/jingzao-image-forge"
            asset_id, spec, design = self.fixture_inputs(project, provider)
            bad = json.loads((project / design).read_text()); bad["payload"] = {"asset_descriptors": [asset_id]}
            (project / design).write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "design_artifact_required_field_missing"):
                prepare.prepare_asset(project_root=project, plan_path="visual-plan.json", asset_id=asset_id, source_spec_path=spec, design_artifact_path=design, original_request="create", output_dir=".production/prepare-b", execution_task_id="test-run-b", provider_root=provider, _test_mode=True)
            self.fixture_inputs(project, provider)
            request = "$dircreative 创建这个长期角色的人物母版资产，固定面部、服装材质和左右细节"
            prepare.prepare_asset(project_root=project, plan_path="visual-plan.json", asset_id=asset_id, source_spec_path=spec, design_artifact_path=design, original_request=request, output_dir=".production/prepare-c", execution_task_id="test-run-c", provider_root=provider, _test_mode=True)
            with self.assertRaisesRegex(ValueError, "output_exists_for_different_input"):
                prepare.prepare_asset(project_root=project, plan_path="visual-plan.json", asset_id=asset_id, source_spec_path=spec, design_artifact_path=design, original_request=request + " changed", output_dir=".production/prepare-c", execution_task_id="test-run-c", provider_root=provider, _test_mode=True)

    def test_reuses_existing_foundation_pass(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "project"; project.mkdir(); provider = Path(raw) / "provider/jingzao-image-forge"
            asset_id, spec, _design = self.fixture_inputs(project, provider)
            request = "$dircreative 创建这个长期角色的人物母版资产，固定面部、服装材质和左右细节"
            result = prepare.prepare_asset(project_root=project, plan_path="visual-plan.json", asset_id=asset_id,
                                           source_spec_path=spec, foundation_pass_path="asset-foundation-pass.json",
                                           original_request=request, output_dir=".production/prepare-foundation",
                                           execution_task_id="test-run-foundation", provider_root=provider, _test_mode=True)
            self.assertEqual(result["paths"]["foundation_pass"]["relative_path"], "asset-foundation-pass.json")

    def test_design_artifact_binds_and_normalizes_declared_local_reference(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "project"; project.mkdir(); provider = Path(raw) / "provider/jingzao-image-forge"
            asset_id, spec, design = self.fixture_inputs(project, provider)
            reference = project / "refs" / "design.png"; reference.parent.mkdir(); reference.write_bytes(b"caller reference")
            source = json.loads((project / spec).read_text())
            source["inputs"] = [{"id": "caller-ref", "role": "identity", "type": "image", "must_attach": True,
                                 "source_kind": "local_path", "source_ref": "refs/design.png",
                                 "rights_status": "user_provided", "approval_status": "reference_only_approved"}]
            (project / spec).write_text(json.dumps(source), encoding="utf-8")
            request = "$dircreative 创建这个长期角色的人物母版资产，固定面部、服装材质和左右细节"
            result = prepare.prepare_asset(project_root=project, plan_path="visual-plan.json", asset_id=asset_id,
                                           source_spec_path=spec, design_artifact_path=design, original_request=request,
                                           output_dir=".production/prepare-reference", execution_task_id="test-run-reference",
                                           provider_root=provider, _test_mode=True)
            role_spec = json.loads((project / result["paths"]["role_spec"]["relative_path"]).read_text())
            self.assertEqual(role_spec["inputs"][0]["source_ref"], "../../refs/design.png")
            foundation_doc = json.loads((project / result["paths"]["foundation_pass"]["relative_path"]).read_text())
            self.assertIn("design-" + asset_id, {item["asset_id"] for item in foundation_doc["source_assets"]})

    def test_idempotent_readback_rejects_changed_provider_reference(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "project"; project.mkdir(); provider = Path(raw) / "provider/jingzao-image-forge"
            asset_id, spec, design = self.fixture_inputs(project, provider)
            request = "$dircreative 创建这个长期角色的人物母版资产，固定面部、服装材质和左右细节"
            kwargs = dict(project_root=project, plan_path="visual-plan.json", asset_id=asset_id, source_spec_path=spec,
                          design_artifact_path=design, original_request=request, output_dir=".production/prepare-readback",
                          execution_task_id="test-run-readback", provider_root=provider, _test_mode=True)
            prepare.prepare_asset(**kwargs)
            (provider / "references/visual-spec.md").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "existing_handoff_invalid"):
                prepare.prepare_asset(**kwargs)


if __name__ == "__main__":
    unittest.main()
