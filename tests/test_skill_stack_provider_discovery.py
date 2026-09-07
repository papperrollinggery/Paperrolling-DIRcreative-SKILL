from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_skill_stack as stack  # noqa: E402


BUILTINS = ("ai-film-asset-stress-test", "ai-film-production-ledger")


class RuntimeProviderDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dir-provider-discovery-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = stack.load_registry()
        self.skills = self.root / "external-skills"
        self.skills.mkdir()
        self.package = self.root / "package"

    def skill(self, root, skill_id, *, directory=None):
        target = root / (directory or skill_id) / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"---\nname: {skill_id}\ndescription: Bounded provider discovery fixture.\n---\n\n# Fixture\nReal fixture body.\n")
        return target

    def bundle(self, *, installed=False):
        self.package.mkdir(exist_ok=True)
        main = self.package / "SKILL.md" if installed else self.package / "skills/dircreative/SKILL.md"
        main.parent.mkdir(parents=True, exist_ok=True)
        main.write_text("---\nname: dircreative\ndescription: Trusted package fixture.\n---\n# DIRcreative\n")
        for skill_id in BUILTINS:
            source = ROOT / "skills" / skill_id / "SKILL.md"
            if source.is_file():
                text = source.read_text()
            else:
                body = source.with_name("INTERNAL_SKILL.md").read_text()
                text = f"---\nname: {skill_id}\ndescription: Bundled layout fixture.\n---\n" + body
            filename = "INTERNAL_SKILL.md" if installed else "SKILL.md"
            if installed:
                text = text.split("\n---\n", 1)[1].lstrip("\n")
            path = self.package / "skills" / skill_id / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def runtime(self, *, catalog_path=None, roots=None):
        return stack.load_runtime_catalog(
            self.registry, roots=roots if roots is not None else [("user_skill", self.skills)],
            catalog_path=catalog_path, package_root=self.package,
        )

    def host_catalog(self, entries):
        path = self.root / "host-catalog.json"
        path.write_text(json.dumps({"skills": entries}))
        return path

    def test_discovers_one_system_layer_and_deduplicates_roots(self):
        path = self.skill(self.skills / ".system", "imagegen")
        self.skill(self.skills / ".other", "hidden-unrelated")
        self.skill(self.skills / ".system/.system", "hidden-nested")
        catalog, rejected = stack.discover_roots(
            [("user_skill", self.skills), ("system_skill", self.skills / ".system")], self.registry,
        )
        self.assertEqual(set(catalog), {"imagegen"})
        self.assertEqual(rejected, [])
        self.assertFalse(catalog["imagegen"].body_loaded)
        loaded = stack.body_loader_for_roots([("user_skill", self.skills)], self.registry)("imagegen", catalog["imagegen"])
        self.assertTrue(loaded.body_loaded)
        self.assertEqual(loaded.body_sha256, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_system_symlink_is_not_followed(self):
        outside = self.root / "outside"
        self.skill(outside, "imagegen")
        (self.skills / ".system").symlink_to(outside, target_is_directory=True)
        catalog, rejected = stack.discover_roots([("user_skill", self.skills)], self.registry)
        self.assertNotIn("imagegen", catalog)
        self.assertTrue(any("symlink" in row["reason"] for row in rejected))

    def test_system_provider_symlink_is_not_followed(self):
        outside = self.root / "outside"
        self.skill(outside, "imagegen")
        system = self.skills / ".system"
        system.mkdir()
        (system / "imagegen").symlink_to(outside / "imagegen", target_is_directory=True)
        catalog, _ = stack.discover_roots([("user_skill", self.skills)], self.registry)
        self.assertNotIn("imagegen", catalog)

    def test_duplicate_public_and_system_provider_fails_closed(self):
        self.skill(self.skills, "imagegen")
        self.skill(self.skills / ".system", "imagegen")
        catalog, rejected = stack.discover_roots([("user_skill", self.skills)], self.registry)
        self.assertNotIn("imagegen", catalog)
        self.assertTrue(any(row["reason"] == "duplicate_skill_id" for row in rejected))

    def test_system_symlink_swap_after_discovery_cannot_load_body(self):
        self.skill(self.skills / ".system", "imagegen")
        catalog, _ = stack.discover_roots([("user_skill", self.skills)], self.registry)
        loader = stack.body_loader_for_roots([("user_skill", self.skills)], self.registry)
        (self.skills / ".system").rename(self.skills / "replacement")
        (self.skills / ".system").symlink_to(self.skills / "replacement", target_is_directory=True)
        self.assertIsNone(loader("imagegen", catalog["imagegen"]))

    def test_source_provider_identity_mismatch_is_not_available(self):
        self.bundle()
        path = self.package / "skills" / BUILTINS[0] / "SKILL.md"
        path.write_text(path.read_text().replace("name: " + BUILTINS[0], "name: unrelated"))
        catalog, _, _ = self.runtime(roots=[])
        self.assertNotIn(BUILTINS[0], catalog)

    def test_internal_bundle_needs_a_dircreative_package_identity(self):
        self.bundle(installed=True)
        (self.package / "SKILL.md").write_text("---\nname: unrelated\ndescription: Wrong package.\n---\n")
        catalog, _, _ = self.runtime(roots=[])
        self.assertEqual(catalog, {})

    def test_final_stress_pass_covers_its_declared_gap_without_claiming_media(self):
        self.bundle(installed=True)
        catalog, _, loader = self.runtime(roots=[])
        case = next(case for case in json.loads(stack.CASES_PATH.read_text())["cases"]
                    if case["id"] == "p51_asset_foundation_stress_pass")
        case["intent"]["asset_pass_status"] = "passed"
        receipt = stack.select_stack(case["intent"], self.registry, stack.load_routing(), catalog,
                                     route_context=stack._fixture_route_context(case), body_loader=loader)
        self.assertEqual(receipt["missing_gaps"], [])
        self.assertEqual(receipt["status"], "ready")
        self.assertFalse(receipt["execution_performed"])
        self.assertFalse(receipt["generated"])
        self.assertEqual(receipt["host_adoption_status"], "unverified")

    def test_source_bundles_work_without_external_roots(self):
        self.bundle()
        catalog, rejected, loader = self.runtime(roots=[])
        self.assertEqual(set(catalog), set(BUILTINS))
        self.assertEqual(rejected, [])
        for skill_id in BUILTINS:
            self.assertFalse(catalog[skill_id].body_loaded)
            loaded = loader(skill_id, catalog[skill_id])
            self.assertTrue(loaded.body_loaded)
            self.assertEqual(loaded.body_sha256, hashlib.sha256(loaded.skill_file.read_bytes()).hexdigest())

    def test_installed_internal_bodies_have_real_hashes_without_public_entries(self):
        self.bundle(installed=True)
        catalog, rejected, loader = self.runtime(roots=[])
        self.assertEqual(set(catalog), set(BUILTINS))
        self.assertEqual(rejected, [])
        for skill_id in BUILTINS:
            entry = catalog[skill_id]
            self.assertEqual(entry.skill_file.name, "INTERNAL_SKILL.md")
            self.assertFalse(entry.body_loaded)
            loaded = loader(skill_id, entry)
            self.assertTrue(loaded.body_loaded)
            self.assertEqual(loaded.frontmatter_bytes, 0)
            self.assertEqual(loaded.body_bytes, entry.skill_file.stat().st_size)
            self.assertEqual(loaded.body_sha256, hashlib.sha256(entry.skill_file.read_bytes()).hexdigest())
            self.assertNotIn("skill_file", loaded.public())

    def test_arbitrary_internalized_external_skill_is_not_a_bundle(self):
        self.bundle(installed=True)
        bad = self.skills / "unrelated" / "INTERNAL_SKILL.md"
        bad.parent.mkdir(parents=True)
        bad.write_text("# Unrelated internal instruction\n")
        catalog, _, _ = self.runtime()
        self.assertEqual(set(catalog), set(BUILTINS))

    def test_missing_bundles_stay_missing(self):
        catalog, rejected, _ = self.runtime(roots=[])
        self.assertEqual(catalog, {})
        self.assertEqual({row["skill_id"] for row in rejected}, set(BUILTINS))

    def test_corrupt_internal_body_is_not_available(self):
        self.bundle(installed=True)
        path = self.package / "skills" / BUILTINS[0] / "INTERNAL_SKILL.md"
        path.write_text("# Wrong Skill\nDo something else.\n")
        catalog, rejected, _ = self.runtime(roots=[])
        self.assertNotIn(BUILTINS[0], catalog)
        self.assertTrue(any(row["skill_id"] == BUILTINS[0] for row in rejected))

    def test_symlinked_bundle_container_is_not_trusted(self):
        self.bundle(installed=True)
        (self.package / "skills").rename(self.root / "redirected-skills")
        (self.package / "skills").symlink_to(self.root / "redirected-skills", target_is_directory=True)
        catalog, _, _ = self.runtime(roots=[])
        self.assertEqual(catalog, {})

    def test_changed_internal_body_is_rechecked_at_hydration(self):
        self.bundle(installed=True)
        catalog, _, loader = self.runtime(roots=[])
        entry = catalog[BUILTINS[0]]
        entry.skill_file.write_text("# Wrong replacement\n")
        with self.assertRaises(stack.SkillStackError):
            loader(BUILTINS[0], entry)

    def test_host_unavailable_and_duplicate_entries_are_not_resurrected(self):
        self.bundle(installed=True)
        for rows in (
            [{"skill_id": BUILTINS[0], "description": "Unavailable", "available": False}],
            [{"skill_id": BUILTINS[0], "description": "Duplicate", "available": True}] * 2,
            [{"skill_id": BUILTINS[0], "description": "Available", "available": True},
             {"skill_id": BUILTINS[0], "description": "Disabled", "available": False}],
        ):
            with self.subTest(rows=rows):
                catalog, _, _ = self.runtime(roots=[], catalog_path=self.host_catalog(rows))
                self.assertNotIn(BUILTINS[0], catalog)
                self.assertIn(BUILTINS[1], catalog)

    def test_rejected_external_duplicates_do_not_fall_back_to_bundles(self):
        self.bundle()
        self.skill(self.skills, BUILTINS[0], directory="alias-a")
        self.skill(self.skills, BUILTINS[0], directory="alias-b")
        catalog, rejected, _ = self.runtime()
        self.assertNotIn(BUILTINS[0], catalog)
        self.assertTrue(any(row.get("skill_id") == BUILTINS[0] for row in rejected))

    def test_host_metadata_can_load_trusted_internal_body_without_roots(self):
        self.bundle(installed=True)
        host = self.host_catalog([{"skill_id": BUILTINS[0], "description": "Package validator", "available": True}])
        catalog, _, loader = self.runtime(roots=[], catalog_path=host)
        loaded = loader(BUILTINS[0], catalog[BUILTINS[0]])
        self.assertTrue(loaded.body_loaded)
        self.assertEqual(loaded.skill_file.name, "INTERNAL_SKILL.md")

    def test_explicit_empty_catalog_retains_bundled_providers_without_discovery(self):
        self.bundle(installed=True)
        host = self.host_catalog([])
        with patch.object(stack, "ROOT", self.package), patch.object(
            stack, "configured_skill_roots", side_effect=AssertionError("explicit catalog must not trigger discovery")
        ):
            catalog, _, loader = stack._catalog_from_args(argparse.Namespace(catalog=host, root=[]), self.registry)
        self.assertEqual(set(catalog), set(BUILTINS))
        self.assertTrue(loader(BUILTINS[0], catalog[BUILTINS[0]]).body_loaded)

    def test_selected_internal_validator_is_materialized_not_adopted(self):
        self.bundle(installed=True)
        catalog, _, loader = self.runtime(roots=[])
        case = next(row for row in stack.load_json(stack.CASES_PATH)["cases"] if row["id"] == "p49_asset_stress_validation")
        result = stack.select_stack(case["intent"], self.registry, stack.load_json(stack.ROUTING_PATH), catalog,
                                    route_context=stack._fixture_route_context(case), body_loader=loader)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["validator"]["skill_id"], BUILTINS[0])
        self.assertEqual(result["validator"]["status"], "materialized")
        self.assertEqual(result["host_adoption_status"], "unverified")

    def test_truly_missing_required_validator_keeps_stress_pass_blocked(self):
        self.bundle(installed=True)
        (self.package / "skills" / BUILTINS[0] / "INTERNAL_SKILL.md").unlink()
        catalog, _, loader = self.runtime(roots=[])
        case = next(row for row in stack.load_json(stack.CASES_PATH)["cases"] if row["id"] == "p51_asset_foundation_stress_pass")
        result = stack.select_stack(case["intent"], self.registry, stack.load_json(stack.ROUTING_PATH), catalog,
                                    route_context=stack._fixture_route_context(case), body_loader=loader)
        self.assertEqual(result["status"], "blocked")
        self.assertIsNone(result["validator"])
        self.assertEqual(result["host_adoption_status"], "not_required")


if __name__ == "__main__":
    unittest.main()
