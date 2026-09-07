from __future__ import annotations

import argparse
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import dircreative_acceptance_preflight as preflight  # noqa: E402
import dircreative_goal_audit as goal  # noqa: E402
import dircreative_install_parity as parity  # noqa: E402
import dircreative_objective_audit as objective  # noqa: E402


class InstalledRuntimeAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dir-installed-acceptance-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / "canonical-source"
        self.target = self.base / "unpublished-stage"
        self.root_text = "---\nname: dircreative\ndescription: Explicit film workflow, any editorial wording.\n---\n\n# Film tools\nNo obsolete heading is necessary.\n"
        self.policy = 'interface:\n  display_name: "DIRcreative"\n  default_prompt: "Use $dircreative for the requested film work."\npolicy:\n  allow_implicit_invocation: false\n'
        files = {
            self.source / "skills/dircreative/SKILL.md": self.root_text,
            self.source / "skills/dircreative/agents/openai.yaml": self.policy,
            self.source / "VERSION": "0.8.1\n",
            self.target / "SKILL.md": self.root_text,
            self.target / "agents/openai.yaml": self.policy,
            self.target / "skills/dircreative/INTERNAL_SKILL.md": "# Film tools\nNo obsolete heading is necessary.\n",
            self.target / "skills/dircreative/agents/openai.yaml": self.policy,
            self.target / "VERSION": "0.8.1\n",
        }
        for path, text in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        for name in ("dircreative_install_parity.py", "dircreative_package_layout.py", "dircreative_release_preflight.py"):
            data = (ROOT / "scripts" / name).read_bytes()
            for base in (self.source, self.target):
                path = base / "scripts" / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(data)

    def verify(self, **kwargs):
        options = {"required": True, "source_root": self.source, "install_target": self.target, "caller_root": self.source}
        options.update(kwargs)
        return parity.verify_installed_runtime(**options)

    def test_source_router_contract_cannot_be_satisfied_only_by_frontmatter(self):
        import validate_project as validation

        source = ROOT / "skills/dircreative/SKILL.md"
        body = parity.strip_skill_frontmatter_bytes(source.read_bytes()).decode("utf-8")
        metadata_only = self.base / "metadata-only-command.md"
        metadata_only.write_text(
            '---\nname: dircreative\ndescription: "Use $dircreative for film work."\n---\n'
            + body.replace("$dircreative", "DIRcreative")
        )
        original = validation.require_path
        with mock.patch.object(
            validation, "require_path",
            side_effect=lambda path: metadata_only if path == "skills/dircreative/SKILL.md" else original(path),
        ):
            with self.assertRaisesRegex(validation.ValidationError, r"root router missing v2 contract term: \$dircreative"):
                validation.validate_skills()
        validation.validate_skills()

    def test_independent_staging_passes_without_obsolete_root_phrases(self):
        result = self.verify()
        self.assertTrue(result.ok, result.errors)
        self.assertIn("INSTALL_PARITY: PASS", result.parity_output)
        self.assertNotIn("Live Chat Start Contract", self.root_text)

    def test_installed_wrapper_requires_and_accepts_external_source(self):
        self.assertTrue(self.verify(caller_root=self.target).ok)
        missing = self.verify(caller_root=self.target, source_root=None)
        self.assertFalse(missing.ok)
        self.assertIn("source", " ".join(missing.errors))

    def test_source_entry_can_default_to_its_independent_checkout(self):
        self.assertTrue(self.verify(source_root=None).ok)

    def test_missing_canonical_verifier_fails_clearly(self):
        (self.source / "scripts/dircreative_install_parity.py").unlink()
        result = self.verify()
        self.assertFalse(result.ok)
        self.assertIn("source verifier", " ".join(result.errors))

    def test_symlinked_canonical_verifier_is_not_used(self):
        verifier = self.source / "scripts/dircreative_install_parity.py"
        verifier.unlink()
        verifier.symlink_to(self.target / "scripts/dircreative_install_parity.py")
        result = self.verify()
        self.assertFalse(result.ok)
        self.assertIn("source verifier", " ".join(result.errors))

    def test_installed_copy_cannot_certify_itself(self):
        result = self.verify(source_root=self.target, caller_root=self.target)
        self.assertFalse(result.ok)
        self.assertIn("independent source", " ".join(result.errors))

    def test_missing_target_is_not_replaced_by_another_global_install(self):
        result = self.verify(install_target=self.base / "missing-target")
        self.assertFalse(result.ok)
        self.assertEqual(result.install_target, (self.base / "missing-target").resolve())

    def test_changed_target_fails_independent_parity(self):
        (self.target / "VERSION").write_text("0.1.0\n")
        result = self.verify()
        self.assertFalse(result.ok)
        self.assertIn("changed installed files", result.parity_output)

    def test_target_verifier_cannot_fake_its_own_parity(self):
        (self.target / "scripts/dircreative_install_parity.py").write_text('print("INSTALL_PARITY: PASS")\n')
        result = self.verify(caller_root=self.target)
        self.assertFalse(result.ok)
        self.assertIn("scripts/dircreative_install_parity.py", result.parity_output)

    def test_identity_and_implicit_activation_must_be_valid(self):
        for path, text in (
            (self.target / "SKILL.md", self.root_text.replace("name: dircreative", "name: unrelated")),
            (self.target / "agents/openai.yaml", self.policy.replace("false", "true")),
        ):
            original = path.read_text()
            with self.subTest(path=path.name):
                path.write_text(text)
                result = self.verify()
                self.assertFalse(result.ok)
                self.assertTrue(result.errors)
            path.write_text(original)

    def test_unrequested_verification_never_reads_global_or_runs_parity(self):
        with mock.patch.object(Path, "exists", side_effect=AssertionError("filesystem probe")), \
             mock.patch.object(parity.subprocess, "run", side_effect=AssertionError("parity executed")):
            result = parity.verify_installed_runtime(required=False)
            item = goal.installed_skill_item(False)
        self.assertTrue(result.ok)
        self.assertFalse(result.required)
        self.assertEqual(item.status, "PASS")

    def test_cli_aliases_and_remote_flag_are_forwarded_only_explicitly(self):
        parser = argparse.ArgumentParser()
        parity.add_installed_runtime_arguments(parser)
        args = parser.parse_args(["--require-installed", "--target", str(self.target), "--source-root", str(self.source), "--verify-remote-tag"])
        flags = parity.installed_runtime_cli_args(args)
        self.assertIn("--install-target", flags)
        self.assertIn(str(self.target.resolve()), flags)
        self.assertIn("--source-root", flags)
        self.assertIn("--verify-remote-tag", flags)
        self.assertEqual(parity.installed_runtime_cli_args(parser.parse_args([])), [])

    def test_remote_verification_flag_reaches_parity_command(self):
        original = parity.subprocess.run
        parity_commands = []

        def run(command, *args, **kwargs):
            if "--source-root" in command:
                parity_commands.append(command)
            return original(command, *args, **kwargs)

        with mock.patch.object(parity.subprocess, "run", side_effect=run):
            self.assertTrue(self.verify().ok)
            self.assertTrue(self.verify(verify_remote_tag=True).ok)
        self.assertNotIn("--verify-remote-tag", parity_commands[0])
        self.assertIn("--verify-remote-tag", parity_commands[1])
        for command in parity_commands:
            self.assertIn(str(self.source.resolve() / "scripts/dircreative_install_parity.py"), command)
            self.assertNotIn(str(self.target.resolve() / "scripts/dircreative_install_parity.py"), command)

    def test_user_acceptance_remains_user_owned_after_install_passes(self):
        self.assertTrue(self.verify().ok)
        item = goal.live_user_acceptance_item(self.base / "no-acceptance.yaml")
        self.assertEqual(item.status, "NEEDS_USER")

    def test_existing_objective_receipt_cannot_certify_an_unchecked_candidate(self):
        receipt = self.base / "historical-acceptance.yaml"
        receipt.write_text("historical user receipt\n")
        with mock.patch.object(objective, "LIVE_ACCEPTANCE", receipt), \
             mock.patch.object(objective, "run_ok", side_effect=AssertionError("implicit global verification")):
            result = objective.live_acceptance_requirement()
        self.assertEqual(result.status, "NEEDS_VERIFICATION")

    def test_goal_keeps_valid_historical_acceptance_separate_from_current_install(self):
        accepted = goal.AuditItem("live user acceptance of chat experience", "PASS", "Real recorded user acceptance")
        with mock.patch.object(goal, "live_user_acceptance_item", return_value=accepted):
            unchecked = goal.completion_acceptance_item(self.base / "accepted.yaml", installation_verified=False)
            checked = goal.completion_acceptance_item(self.base / "accepted.yaml", installation_verified=True)
        self.assertEqual(unchecked.status, "NEEDS_VERIFICATION")
        self.assertEqual(checked.status, "PASS")

    def test_installed_preflight_wrapper_forwards_independent_source_and_target(self):
        commands = []

        def nested_run(command):
            commands.append(command)
            return True, "OBJECTIVE_TECHNICAL_READINESS: PASS\nOBJECTIVE_COMPLETE: NO\nreal user acceptance"

        args = ["preflight", "--require-installed", "--install-target", str(self.target), "--source-root", str(self.source)]
        with mock.patch.object(preflight, "ROOT", self.target), \
             mock.patch.object(preflight, "RECEIPT", self.target / "absent-acceptance.yaml"), \
             mock.patch.object(preflight, "run", side_effect=nested_run), \
             mock.patch.object(sys, "argv", args), contextlib.redirect_stdout(io.StringIO()) as output:
            code = preflight.main()
        self.assertEqual(code, 0, output.getvalue())
        self.assertEqual(commands, [["python3", "scripts/dircreative_objective_audit.py", "--require-installed", "--install-target", str(self.target.resolve()), "--source-root", str(self.source.resolve())]])
        self.assertIn("receipt_creation_allowed: false", output.getvalue())

    def test_unrequested_preflight_does_not_check_installation(self):
        with mock.patch.object(preflight, "RECEIPT", self.base / "no-receipt.yaml"), \
             mock.patch.object(preflight, "run", return_value=(True, "OBJECTIVE_TECHNICAL_READINESS: PASS\nOBJECTIVE_COMPLETE: NO\nreal user acceptance")) as nested, \
             mock.patch.object(parity, "_installed_identity_errors", side_effect=AssertionError("global read")), \
             mock.patch.object(sys, "argv", ["preflight"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(preflight.main(), 0)
        nested.assert_called_once_with(["python3", "scripts/dircreative_objective_audit.py"])

    def test_v2_operator_prompt_takes_precedence_over_legacy_text(self):
        runbook = "## Legacy Operator Prompt\n```text\nOld mandatory gates\n```\n## V2 Operator Prompt\n```text\n我要做一次 DIRcreative 真实聊天验收。\nCurrent scoped work.\n```\n## Later\n"
        self.assertEqual(preflight.extract_operator_prompt(runbook), "我要做一次 DIRcreative 真实聊天验收。\nCurrent scoped work.")
        self.assertEqual(preflight.extract_operator_prompt("## Operator Prompt\n```text\nHistorical reader only.\n```"), "Historical reader only.")

    def test_malformed_v2_section_does_not_fall_back_to_legacy_prompt(self):
        text = "```text\nLegacy confirmation sequence\n```\n## V2 Operator Prompt\nMissing text block\n## Next\n```text\nUnrelated\n```"
        with self.assertRaises(ValueError):
            preflight.extract_operator_prompt(text)


if __name__ == "__main__":
    unittest.main()
