from __future__ import annotations

import sys
import subprocess
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_skill_stack as stack  # noqa: E402


class SkillStackRouteContextTests(unittest.TestCase):
    def test_authorized_clean_image_keeps_selected_craft_owner(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            stack._write_mock_skill(root, "im2-clean-image")
            stack._write_mock_skill(root, "imagegen")
            registry = stack.load_registry()
            catalog, rejected = stack.discover_roots([("codex_skill", root)], registry)
            self.assertEqual(rejected, [])
            case = next(
                item
                for item in json.loads(stack.CASES_PATH.read_text())["cases"]
                if item["id"] == "p42_authorized_generation_adapter"
            )
            case = json.loads(json.dumps(case))
            case["intent"]["scenario_id"] = "clean_image"
            receipt = stack.select_stack(
                stack._fixture_intent(case),
                registry,
                stack.load_routing(),
                catalog,
                route_context=stack._fixture_route_context(case),
                body_loader=stack.body_loader_for_roots([("codex_skill", root)], registry),
            )
        self.assertEqual(receipt["status"], "ready")
        self.assertEqual(receipt["scenario_id"], "clean_image")
        self.assertEqual(receipt["craft_owner"]["skill_id"], "im2-clean-image")
        self.assertEqual(receipt["execution_adapter"]["skill_id"], "imagegen")

    def test_authorized_key_visual_keeps_selected_craft_owner(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            stack._write_mock_skill(root, "visual-style-aesthetic-direction")
            stack._write_mock_skill(root, "imagegen")
            registry = stack.load_registry()
            catalog, rejected = stack.discover_roots([("codex_skill", root)], registry)
            self.assertEqual(rejected, [])
            case = next(
                item
                for item in json.loads(stack.CASES_PATH.read_text())["cases"]
                if item["id"] == "p42_authorized_generation_adapter"
            )
            case = json.loads(json.dumps(case))
            case["intent"]["scenario_id"] = "key_visual"
            receipt = stack.select_stack(
                stack._fixture_intent(case),
                registry,
                stack.load_routing(),
                catalog,
                route_context=stack._fixture_route_context(case),
                body_loader=stack.body_loader_for_roots([("codex_skill", root)], registry),
            )
        self.assertEqual(receipt["status"], "ready")
        self.assertEqual(receipt["scenario_id"], "key_visual")
        self.assertEqual(receipt["craft_owner"]["skill_id"], "visual-style-aesthetic-direction")
        self.assertEqual(receipt["execution_adapter"]["skill_id"], "imagegen")

    def test_missing_execution_project_root_fails_as_structured_skill_error(self):
        with tempfile.TemporaryDirectory() as raw:
            missing = Path(raw) / "missing-project"
            with self.assertRaisesRegex(stack.SkillStackError, "execution project root"):
                stack.validate_primary_route_context(
                    {
                        "route_id": "generation_authorization",
                        "mode": "delivery",
                        "execution_context": "standalone_chat",
                    },
                    request_text="$dircreative 现在直接出图",
                    execution_project_root=missing,
                )

    def test_oversized_intent_cli_returns_blocked_json(self):
        with tempfile.TemporaryDirectory() as raw:
            intent = Path(raw) / "oversized.json"
            intent.write_bytes(b"x" * (stack.MAX_INTENT_BYTES + 1))
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/dircreative_skill_stack.py"),
                    "select",
                    "--intent",
                    str(intent),
                    "--catalog",
                    str(ROOT / "tests/fixtures/skill-stack/host-catalog.json"),
                    "--request",
                    "$dircreative 现在直接出图",
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(proc.returncode, 2)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn("intent exceeds size limit", proc.stdout)

    def test_seedance_method_version_drift_fails_closed_to_dir(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            stack._write_mock_skill(root, "mr-li-seedance-25")
            skill = root / "mr-li-seedance-25/SKILL.md"
            skill.write_text(
                skill.read_text(encoding="utf-8").replace('version: "1.9.0"', 'version: "1.8.2"'),
                encoding="utf-8",
            )
            registry = stack.load_registry()
            catalog, rejected = stack.discover_roots([("codex_skill", root)], registry)
            self.assertEqual(rejected, [])
            case = next(
                item
                for item in json.loads(stack.CASES_PATH.read_text())["cases"]
                if item["id"] == "p17_seedance_direct"
            )
            receipt = stack.select_stack(
                stack._fixture_intent(case),
                registry,
                stack.load_routing(),
                catalog,
                route_context=stack._fixture_route_context(case),
                body_loader=stack.body_loader_for_roots([("codex_skill", root)], registry),
            )
        self.assertEqual(receipt["craft_owner"]["skill_id"], "dircreative")
        self.assertIsNone(receipt["priority_method_provider"])
        self.assertIn("provider_version_mismatch", receipt["materialization_failures"].values())


if __name__ == "__main__":
    unittest.main()
