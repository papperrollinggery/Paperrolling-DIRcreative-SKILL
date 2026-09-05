from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_director_harness_audit as director
import dircreative_route as routing
import dircreative_thread_audit as thread


class RuntimeAuditScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.harness = director.load_yaml(director.HARNESS_PATH)["director_role_harness"]
        cls.cleanup = thread.load_yaml(thread.CLEANUP_RECEIPT)
        cls.objective = thread.load_yaml(thread.OBJECTIVE_RECEIPT)
        cls.release = thread.load_yaml(thread.RELEASE_RECEIPT)

    def test_primary_route_cannot_be_overridden_by_one_line_substring(self):
        for request in (
            "完整广告片，交付脚本和分镜，先给一句核心概念",
            "帮我写一个故事并给我脚本和分镜",
            "不要真实生成，只优化这一句提示词",
            "修改 DIRcreative 源码的导演组路由，不开始创作",
        ):
            with self.subTest(request=request):
                route = routing.route_request(request)
                selected = director.select_perspectives(request, self.harness)
                self.assertEqual(selected["mode"], route["mode"])
                if route["route"] == "film_development":
                    self.assertTrue(selected["selected_perspectives"])
                if route["route"] == "source_maintenance":
                    self.assertFalse(selected["director_room_used"])
                    self.assertEqual(selected["selected_perspectives"], [])

    def test_existing_adco_route_is_preserved_without_nested_room(self):
        primary = {
            "execution_context": "orchestrated_worker", "mode": "delivery",
            "route": "adco_specialist_exchange", "collaboration": {"execution_mode": "none"},
        }
        result = director.select_perspectives(
            "请让导演组和创意组联合完成完整广告片", self.harness, primary_route=primary,
        )
        self.assertEqual(result["mode"], "delivery")
        self.assertFalse(result["director_room_used"])
        self.assertEqual(result["selected_perspectives"], [])
        self.assertEqual(result["collaboration"], primary["collaboration"])

    def test_archiving_a_task_does_not_assert_worktree_removal(self):
        cleanup = json.loads(json.dumps(self.cleanup))
        cleanup["dispatches"].append({
            "thread_class": "isolated_worktree_worker", "worktree_path": "/tmp/retained-worker",
            "archived": True, "professional_identity": "reviewer", "allowed_actions": ["review"],
            "stop_condition": "review complete", "may_mark_goal_complete": False,
        })
        with mock.patch.object(thread, "git_worktrees", return_value=(["/tmp/retained-worker"], "git")):
            failures, details = thread.build_failures(cleanup, self.objective, self.release, check_git_worktrees=True)
        self.assertEqual(failures, [])
        self.assertEqual(details["unexpected_worktrees"], [])

    def test_legacy_fixture_validation_does_not_read_live_worktrees(self):
        with mock.patch.object(thread, "git_worktrees", side_effect=AssertionError("live state queried")):
            failures, details = thread.build_failures(self.cleanup, self.objective, self.release)
        self.assertEqual(failures, [])
        self.assertEqual(details["worktree_source"], "historical_fixture_only")

    def test_explicit_worktree_check_is_scoped_to_recorded_workers(self):
        with mock.patch.object(thread, "git_worktrees", return_value=([str(ROOT), "/tmp/unrelated-project"], "git")):
            failures, _ = thread.build_failures(self.cleanup, self.objective, self.release, check_git_worktrees=True)
        self.assertEqual(failures, [])
        cleanup = json.loads(json.dumps(self.cleanup))
        cleanup["worktree_audit"]["expected_absent_worktrees"] = ["/tmp/recorded-stale-worker"]
        with mock.patch.object(thread, "git_worktrees", return_value=([str(ROOT), "/tmp/recorded-stale-worker"], "git")):
            failures, _ = thread.build_failures(cleanup, self.objective, self.release, check_git_worktrees=True)
        self.assertTrue(any("recorded-stale-worker" in item for item in failures))


if __name__ == "__main__":
    unittest.main()
