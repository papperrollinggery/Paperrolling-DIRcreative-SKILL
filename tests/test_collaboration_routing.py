from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from dircreative_route import route_request  # noqa: E402


class CollaborationRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dir-collaboration-fixture-")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)

    def route(self, request):
        return route_request(request, project_root=self.project)

    def test_default_studio_remains_one_controller(self):
        result = self.route("开发完整广告片，给我故事、脚本和分镜。")
        self.assertEqual(result["collaboration"]["execution_mode"], "main_thread_perspectives")
        self.assertFalse(result["threads_allowed"])
        self.assertFalse(result["collaboration"]["subagents_allowed"])

    def test_named_groups_are_not_proof_of_real_workers(self):
        result = self.route("请调用导演组和创意组，开发完整广告片。")
        collaboration = result["collaboration"]
        self.assertEqual(collaboration["requested_groups"], ["creative", "director"])
        self.assertEqual(collaboration["execution_mode"], "main_thread_perspectives")
        self.assertEqual(collaboration["execution_status"], "not_dispatched")
        self.assertEqual(collaboration["dispatch_receipts"], [])

    def test_explicit_subagents_do_not_create_user_tasks(self):
        result = self.route("请导演组和创意组启用真实子代理并行，开发完整广告片。")
        self.assertEqual(result["collaboration"]["execution_mode"], "host_subagents")
        self.assertTrue(result["collaboration"]["subagents_allowed"])
        self.assertFalse(result["threads_allowed"])
        self.assertEqual(result["collaboration"]["dispatch_receipts"], [])

    def test_joint_group_work_selects_bounded_subagents(self):
        result = self.route("请调用导演组与创意组联合协作，开发完整广告片。")
        self.assertEqual(result["collaboration"]["execution_mode"], "host_subagents")
        self.assertEqual(result["collaboration"]["max_subagents"], 2)

    def test_worker_assignment_can_contain_an_explanation_or_research_question(self):
        for request in (
            "请启用子代理研究怎么优化这个镜头。",
            "请调用导演组与创意组联合研究如何完善完整广告片。",
            "请启用子代理解释这个镜头是否满足时长。",
        ):
            with self.subTest(request=request):
                self.assertEqual(self.route(request)["collaboration"]["execution_mode"], "host_subagents")

    def test_explicit_new_task_is_separate_from_subagents(self):
        result = self.route("请创建两个新任务，分别让创意组和导演组开发完整广告片。")
        self.assertEqual(result["collaboration"]["execution_mode"], "host_threads")
        self.assertTrue(result["threads_allowed"])
        self.assertFalse(result["collaboration"]["subagents_allowed"])

    def test_simple_named_group_request_stays_fast(self):
        result = self.route("请调用导演组，优化这个镜头。")
        self.assertEqual((result["mode"], result["route"]), ("fast", "shot_optimization"))
        self.assertEqual(result["collaboration"]["execution_mode"], "main_thread_perspectives")

    def test_later_cancellation_removes_dispatch_permission(self):
        for request in (
            "请调用真实子代理。不要调用子代理，只优化这个镜头。",
            "请创建新任务。不要创建新任务，只优化这个镜头。",
            "请调用导演组与创意组联合协作。不要联合协作，只优化这个镜头。",
            "请调用导演组联合协作。不要调用导演组，只优化这个镜头。",
        ):
            with self.subTest(request=request):
                result = self.route(request)
                self.assertFalse(result["threads_allowed"])
                self.assertFalse(result["collaboration"]["subagents_allowed"])

    def test_non_action_group_and_worker_mentions_do_not_dispatch(self):
        for request in (
            "不要调用导演组和创意组，不要启用子代理，只优化这个镜头。",
            "如果需要再启用子代理，先优化这个镜头。",
            "之前导演组和创意组调用有问题，先优化这个镜头。",
            "导演组和创意组联合调用有问题，先优化这个镜头。",
            "等我确认后再启用子代理，先优化这个镜头。",
            "解释一下如何调用导演组和创意组并行工作。",
            "是否需要启用真实子代理？先优化这个镜头。",
            "请解释真实子代理和新任务的区别。",
            "请比较子代理与新任务的区别。",
            "请比较导演组与创意组联合协作的优缺点。",
            '优化这个镜头，原文是“请调用导演组和创意组联合协作”。',
            "优化这个镜头。`请创建两个新任务，启用真实子代理。`",
        ):
            with self.subTest(request=request):
                result = self.route(request)
                self.assertFalse(result["threads_allowed"])
                self.assertFalse(result["collaboration"]["subagents_allowed"])

    def test_maintenance_suppresses_collaboration(self):
        result = self.route("审查 DIRcreative 源码，优化导演组和创意组联合调用真实子代理。")
        self.assertEqual(result["action"], "stop_skill_runtime")
        self.assertEqual(result["collaboration"]["execution_mode"], "none")
        self.assertFalse(result["threads_allowed"])

    def test_invalid_handoff_cannot_dispatch(self):
        result = route_request("请创建新任务并调用子代理。", {"invalid": True})
        self.assertEqual(result["collaboration"]["execution_mode"], "none")
        self.assertFalse(result["threads_allowed"])

    def test_valid_adco_worker_cannot_nest_dispatch(self):
        from dircreative_adco_native_exchange import register_v2_fixture_handoff

        handoff = copy.deepcopy(json.loads((ROOT / "tests/fixtures/activation-policy/valid-adco-v2-handoff.json").read_text()))
        descriptor = json.loads((ROOT / "docs/film-preproduction/schemas/adco-specialist-descriptor.json").read_text())
        brief = self.project / handoff["brief_snapshot"]
        brief.parent.mkdir(parents=True, exist_ok=True)
        brief.write_text("Isolated collaboration fixture.\n")
        handoff["locked_decisions"][0]["sha256"] = hashlib.sha256(brief.read_bytes()).hexdigest()
        handoff_path = self.project / "exchange/v2-handoff.json"
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        handoff_path.write_text(json.dumps(handoff))
        output_parent = Path(handoff["requested_outputs"][0]["path_root"]).parent
        register_v2_fixture_handoff(self.project, handoff, handoff_path, descriptor,
                                   receipt_path=(output_parent / "receipt.json").as_posix())
        result = route_request("请导演组和创意组启用真实子代理，并创建新任务。", handoff,
                               project_root=self.project, descriptor=descriptor, handoff_path=handoff_path)
        self.assertEqual(result["route"], "adco_specialist_exchange")
        self.assertEqual(result["collaboration"]["execution_mode"], "none")
        self.assertFalse(result["collaboration"]["subagents_allowed"])
        self.assertFalse(result["threads_allowed"])

    def test_negated_side_effects_do_not_replace_bounded_work(self):
        for request, expected in (
            ("不要真实生成，只优化这一句提示词。", "prompt_revision"),
            ("不需要发给客户，只修改这段文案。", "copy_revision"),
        ):
            with self.subTest(request=request):
                result = self.route(request)
                self.assertEqual(result["route"], expected)
                self.assertEqual(result["action"], "continue")

    def test_resolved_or_delegated_concept_choice_does_not_reask(self):
        for request in (
            "两个方向冲突已经解决，按 A 继续写完整脚本。",
            "方向冲突时按你的专业判断选择，开发完整广告片。",
        ):
            with self.subTest(request=request):
                self.assertEqual(self.route(request)["action"], "continue")
        self.assertEqual(self.route("两个方向冲突，开发完整广告片前让我选。")["external_user_gate"], "concept_lock")
        self.assertEqual(self.route("两个方向冲突，不要按你的专业判断选择，先让我选。")["external_user_gate"], "concept_lock")

    def test_other_sentence_question_does_not_cancel_generation(self):
        result = self.route("请现在生成一张图片。完成后解释一下怎么保持人物一致。")
        self.assertEqual(result["action"], "continue")
        self.assertTrue(result["image_generation_authorized"])

    def test_numeric_single_shot_stays_fast(self):
        self.assertEqual(self.route("请把这 1 个镜头优化得更紧张。")["route"], "shot_optimization")

    def test_single_direction_client_story_stops_at_requested_layer(self):
        for request in (
            "调用创意组，为新品牌写一页客户可读的故事，只要故事，不要分镜和资产。",
            "请给我单页客户故事。",
            "请为提案写客户可读故事，只输出故事。",
        ):
            with self.subTest(request=request):
                result = self.route(request)
                self.assertEqual(result["deliverable_layer"], "client_story")
                self.assertFalse(result["shot_matrix_allowed"])

    def test_small_story_excerpt_does_not_shrink_full_film_or_extra_outputs(self):
        for request in (
            "开发完整广告片，先给一句核心概念，再给故事、脚本和分镜。",
            "开发完整广告片，给我一页客户故事和分镜。",
            "不要只给一页客户故事，开发完整广告片。",
            '开发完整广告片。原文是“一页客户可读的故事，只要故事”。',
        ):
            with self.subTest(request=request):
                result = self.route(request)
                self.assertNotEqual(result["deliverable_layer"], "client_story")
                self.assertTrue(result["shot_matrix_allowed"])


class ClientStoryContextTests(unittest.TestCase):
    def test_client_story_loads_only_its_small_craft_reference(self):
        from dircreative_route import route_request
        result = route_request("$dircreative 请创意组为品牌写一页客户可读的故事，只要故事，不要分镜和资产")
        self.assertEqual(result["deliverable_layer"], "client_story")
        self.assertEqual(result["required_files"], ["skills/dircreative/references/client-story.md"])
        self.assertFalse(result["shot_matrix_allowed"])


if __name__ == "__main__":
    unittest.main()
