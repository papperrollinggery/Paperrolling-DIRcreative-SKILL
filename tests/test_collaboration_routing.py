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

    def test_spatial_discussion_uses_existing_studio_selector_and_host_contract(self):
        result = self.route("两人在同一个房间对话，我想看看站位和正反打怎么安排。")
        self.assertEqual((result["mode"], result["route"]), ("studio", "film_development"))
        self.assertEqual(result["deliverable_layer"], "spatial_discussion")
        self.assertEqual(
            result["required_files"],
            ["skills/dircreative/references/spatial-discussion.md"],
        )
        self.assertFalse(result["shot_matrix_allowed"])
        self.assertEqual(
            result["spatial_discussion"],
            {
                "requested": True,
                "interaction": "presentation_only",
                "host_visualize_contract": "read_current_host_contract",
                "scene_state_owner": "existing_scene_shot_artifacts",
                "adoption": "explicit_user_intent_required",
                "generation": "requires_existing_generation_authorization",
            },
        )

    def test_full_preproduction_with_reverse_shots_is_not_collapsed_to_spatial_discussion(self):
        result = self.route("给我做一支两人对话广告片的完整前期：故事、剧本、逐镜代表图、完整视频提示词和实际上传顺序，包含正反打。")
        self.assertEqual((result["mode"], result["route"]), ("studio", "film_development"))
        self.assertNotEqual(result["deliverable_layer"], "spatial_discussion")
        self.assertTrue(result["shot_matrix_allowed"])
        self.assertFalse(result["spatial_discussion"]["requested"])

    def test_prompt_only_revision_does_not_enter_spatial_discussion(self):
        result = self.route("只把这个两人正反打镜头提示词改得简洁，别扩写。")
        self.assertEqual((result["mode"], result["route"]), ("fast", "prompt_revision"))
        self.assertEqual(result["deliverable_layer"], "bounded_output")
        self.assertFalse(result["spatial_discussion"]["requested"])

    def test_local_blocking_change_enters_spatial_discussion_without_moving_unaffected_facts(self):
        result = self.route("只改甲绕桌走到门边，乙和房间不动。")
        self.assertEqual(result["deliverable_layer"], "spatial_discussion")
        self.assertEqual(result["spatial_discussion"]["scene_state_owner"], "existing_scene_shot_artifacts")
        self.assertEqual(result["spatial_discussion"]["adoption"], "explicit_user_intent_required")

    def test_natural_action_preproduction_exposes_existing_craft_stages(self):
        result = self.route(
            "$dircreative 帮我做一部一分钟武侠动作短片，要有故事，"
            "把需要的图片都真实生成好，停在视频生成前，视频我自己生成。"
        )
        self.assertEqual(result["route"], "film_development")
        self.assertEqual(result["media_scope"], "pre_video_assets")
        self.assertFalse(result["video_generation_authorized"])
        self.assertEqual(result["required_files"], ["skills/dircreative/references/film-development.md"])
        stages = result["craft_stages"]
        self.assertEqual(stages[0]["stage"], "shot_design")
        intents = [item["selection_intent"] for item in stages if "selection_intent" in item]
        self.assertEqual(
            [intent["scenario_id"] for intent in intents],
            ["technical_storyboard", "action_choreography", "master_camera", "technical_storyboard", "cinematic_storyboard_frames", "cinematic_storyboard_frames"],
        )
        self.assertEqual(stages[-2]["stage"], "motion_board")
        self.assertEqual(intents[-2]["downstream_use"], "rough_planning")
        self.assertEqual(intents[-1]["downstream_use"], "full_preproduction")
        self.assertTrue(all(intent["media"] == "storyboard" and intent["real_side_effect"] is False for intent in intents))
        self.assertTrue(all(item["status"] == "pending" for item in stages))
        registry = json.loads((ROOT / "skills/dircreative/runtime/visual-skill-policy.json").read_text())
        scenarios = {item["scenario_id"]: item for item in registry["scenarios"]}
        for intent in intents:
            self.assertIn(intent["media"], scenarios[intent["scenario_id"]]["media"])
        for item in stages:
            if "task_reference" in item:
                self.assertTrue((ROOT / item["task_reference"]).is_file())

    def test_action_effects_are_conditional_and_never_authorize_execution(self):
        result = self.route("做一部完整武侠动作短片，环境破碎要有因果，暂时只做前期计划。")
        intents = [item["selection_intent"] for item in result["craft_stages"] if "selection_intent" in item]
        self.assertIn("vfx_design", [intent["scenario_id"] for intent in intents])
        self.assertTrue(all(intent["real_side_effect"] is False for intent in intents))
        quiet = self.route("做一部完整静物短片，不要打斗，不要爆炸，真实生成全部图片，视频我自己做。")
        quiet_scenarios = [item["selection_intent"]["scenario_id"] for item in quiet["craft_stages"] if "selection_intent" in item]
        self.assertNotIn("action_choreography", quiet_scenarios)
        self.assertNotIn("vfx_design", quiet_scenarios)

    def test_bounded_revision_client_story_and_identity_keep_their_scope(self):
        for request in (
            "只把这个武侠打斗镜头提示词改得简洁，别扩写。",
            "请为客户写一页武侠故事，只要故事，不要分镜和资产。",
            "审查 DIRcreative 源码的动作分镜路由。",
        ):
            with self.subTest(request=request):
                self.assertEqual(self.route(request)["craft_stages"], [])


class NaturalAssetRoutingTests(unittest.TestCase):
    def route(self, request):
        return route_request(request)

    def test_original_nine_grid_and_asset_requests_keep_both_deliverables(self):
        for request in (
            "生成一段《将夜》的九宫格剧情。1分钟左右，给我分镜头和相关资产就好了。使用Dirskil。",
            "$dircreative 生成一段《将夜》的九宫格剧情。1分钟左右，给我分镜头和相关资产就好了。",
            "$dircreative 请写九格故事板，并准备相关角色、环境和道具参考资产。",
        ):
            with self.subTest(request=request):
                result = self.route(request)
                self.assertEqual(result["route"], "film_development")
                self.assertEqual(result["deliverable_layer"], "narrative_storyboard")
                self.assertFalse(result["shot_matrix_allowed"])
                stages = {item["stage"]: item for item in result["craft_stages"]}
                self.assertIn("identity_state", stages)
                self.assertIn("production_design", stages)
                self.assertIn("camera_geography", stages)
                self.assertNotIn("shot_design", stages)
                self.assertEqual(stages["identity_state"]["task_reference"], "skills/dircreative/references/character-master-sheet.md")
                self.assertFalse(result["video_generation_authorized"])

    def test_scoped_asset_design_does_not_acquire_a_whole_film(self):
        cases = (
            ("$dircreative 为短片从零设计一位反复出场的女信使，没有人物素材，先给我人物资产设计方案。", "identity_state", "asset_foundation"),
            ("$dircreative 请制作一个古代女信使的人物资产，供后续多个镜头统一人物外观，图片现在生成。", "identity_state", "asset_foundation"),
            ("$dircreative 给这个茶馆做场景参考图，包含入口、柜台、后门的关系，以及两人对话的正反打机位，图片现在生成。", "camera_geography", "asset_foundation"),
            ("$dircreative 为机械短片设计折叠盾从前臂展开的结构与分阶段参考图，铰链、锁止、手腕接触要讲得通，先给方案。", "mechanical_transformation", "mechanical_transformation"),
        )
        for request, stage, scenario in cases:
            with self.subTest(stage=stage):
                result = self.route(request)
                self.assertEqual(result["route"], "film_development")
                self.assertFalse(result["shot_matrix_allowed"])
                stages = {item["stage"]: item for item in result["craft_stages"]}
                self.assertNotIn("shot_design", stages)
                self.assertNotIn("frame_compile", stages)
                self.assertEqual(stages[stage]["selection_intent"]["scenario_id"], scenario)

    def test_character_state_design_keeps_the_character_reference(self):
        for request in (
            "$dircreative 已有人物母版，只把外套换成棉袍，脸和身材不变，生成新服装状态图片。",
            "$dircreative 沿用已给的人物母版，生成淋湿且左袖破损的状态资产，不改变人物身份。",
        ):
            with self.subTest(request=request):
                result = self.route(request)
                stage = next((item for item in result["craft_stages"] if item["stage"] == "identity_state"), None)
                self.assertIsNotNone(stage)
                self.assertEqual(stage["task_reference"], "skills/dircreative/references/character-master-sheet.md")
                self.assertFalse(result["shot_matrix_allowed"])

    def test_negated_assets_and_standalone_portraits_do_not_create_masters(self):
        for request in (
            "$dircreative 请设计一张女信使的独立肖像海报，不需要角色母版，不出图。",
            "$dircreative 现在直接出图：女信使单张肖像海报，不需要角色母版。",
            "$dircreative 只写九宫格剧情，不要角色资产、场景资产和道具资产，不出图。",
            "$dircreative 请做人物资产方案，但不要场景资产和道具资产。",
        ):
            with self.subTest(request=request):
                result = self.route(request)
                stages = [item["stage"] for item in result["craft_stages"]]
                if "请做人物资产" not in request:
                    self.assertNotIn("identity_state", stages)
                    self.assertNotIn("skills/dircreative/references/character-master-sheet.md", result["required_files"])
                self.assertNotIn("camera_geography", stages)
                self.assertNotIn("production_design", stages)

    def test_related_assets_do_not_restore_explicitly_excluded_roles(self):
        result = self.route("$dircreative 给我九宫格剧情和相关资产，不需要人物资产，只要场景和道具。")
        stages = [item["stage"] for item in result["craft_stages"]]
        self.assertNotIn("identity_state", stages)
        self.assertIn("production_design", stages)
        self.assertIn("camera_geography", stages)

    def test_prompt_shorthand_keeps_the_specific_fast_reference(self):
        result = self.route("$dircreative 只把这个打斗提示词改短，保留原动作和反打机位，不扩写、不出图。")
        self.assertEqual(result["route"], "prompt_revision")
        self.assertEqual(result["craft_stages"], [])
        self.assertEqual(result["required_files"], ["skills/dircreative/references/prompt-model.md"])

    def test_reusing_text_does_not_start_asset_readback(self):
        result = self.route("$dircreative 沿用现有故事，只润色第三句文案。")
        self.assertEqual(result["route"], "copy_revision")
        self.assertEqual(result["craft_stages"], [])

    def test_shortening_a_character_prompt_does_not_restart_character_design(self):
        result = self.route("$dircreative 精简这个人物母版提示词，保留五个视图。")
        self.assertEqual(result["route"], "prompt_revision")
        self.assertEqual(result["craft_stages"], [])

    def test_reuse_request_exposes_readback_without_requiring_new_character_design(self):
        result = self.route("$dircreative 做一部完整短片，图片真实生成好，视频我自己做。已给人物、场景和道具图片，沿用这些素材，只生成缺少的分镜图片。")
        stages = {item["stage"]: item for item in result["craft_stages"]}
        self.assertIn("asset_readback", stages)
        self.assertEqual(stages["asset_readback"]["task_reference"], "skills/dircreative/references/image-execution.md")
        self.assertNotIn("identity_state", stages)

    def test_mixed_reuse_preserves_new_roles_and_new_identities(self):
        cases = [
            ("沿用已有人物母版，并给茶馆制作新的场景参考图，图片现在生成。", "camera_geography", "identity_state"),
            ("沿用已给场景图片，同时给新角色制作人物资产，图片现在生成。", "identity_state", "camera_geography"),
            ("复用已有人物资产，并为另一个新人物制作母版，图片现在生成。", "identity_state", None),
        ]
        for request, wanted, absent in cases:
            with self.subTest(request=request):
                stages = {item["stage"] for item in self.route("$dircreative " + request)["craft_stages"]}
                self.assertIn("asset_readback", stages)
                self.assertIn(wanted, stages)
                if absent:
                    self.assertNotIn(absent, stages)

    def test_local_state_change_does_not_rebuild_all_supplied_asset_roles(self):
        result = self.route("$dircreative 已给人物、场景和道具图片，沿用这些素材，只生成淋湿且左袖破损的状态资产，图片现在生成。")
        stages = {item["stage"] for item in result["craft_stages"]}
        self.assertIn("identity_state", stages)
        self.assertNotIn("production_design", stages)
        self.assertNotIn("camera_geography", stages)


class ClientStoryContextTests(unittest.TestCase):
    def test_client_story_loads_only_its_small_craft_reference(self):
        from dircreative_route import route_request
        result = route_request("$dircreative 请创意组为品牌写一页客户可读的故事，只要故事，不要分镜和资产")
        self.assertEqual(result["deliverable_layer"], "client_story")
        self.assertEqual(result["required_files"], ["skills/dircreative/references/client-story.md"])
        self.assertFalse(result["shot_matrix_allowed"])


if __name__ == "__main__":
    unittest.main()
