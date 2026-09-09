from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from dircreative_route import route_request


class InteractionModesTests(unittest.TestCase):
    def route(self, request, state=None, **kwargs):
        return route_request(request, interaction_state=state, scope_id="film-A", **kwargs)

    def start(self, mode="discuss"):
        label = {"discuss": "讨论共创", "direct": "直接执行", "checkpoints": "关键节点讨论"}[mode]
        return self.route(f"做一支30秒短片，{label}。")["interaction"]

    def show(self, result):
        q = result["interaction_question"]
        return self.route("继续", result["interaction"], question_receipt={
            "question_id": q["question_id"], "host_call_id": "fixture-host-call"})

    def production_question(self):
        r = self.route("方向已经清楚", self.start(), production_scope=["一页故事", "30秒剧本"])
        return self.show(r)

    def test_complete_brief_still_asks_for_unselected_mode(self):
        r = self.route("做一支完整30秒广告片，brief已完整。")
        self.assertEqual(r["action"], "ask_interaction_mode")
        self.assertEqual(r["interaction_question"]["options"], ["讨论共创", "直接执行", "关键节点讨论"])
        self.assertFalse(r["shot_matrix_allowed"])
        self.assertEqual(r["craft_stages"], [])

    def test_named_group_does_not_answer_mode_question(self):
        r = self.route("请调用创意组，做完整广告片。")
        self.assertEqual(r["action"], "ask_interaction_mode")
        self.assertEqual(r["interaction"]["professional_groups"], ["creative"])

    def test_native_choice_requires_actual_question_receipt(self):
        r = self.route("做30秒短片")
        answer = {"question_id": r["interaction_question"]["question_id"], "choice": "直接执行"}
        with self.assertRaisesRegex(ValueError, "presented_question"):
            self.route("", r["interaction"], question_answer=answer)
        shown = self.show(r)
        picked = self.route("", shown["interaction"], question_answer=answer)
        self.assertEqual(picked["interaction"]["mode"], "direct")
        self.assertEqual(picked["action"], "continue")
        self.assertIsNone(picked["interaction_question"])

    def test_same_question_is_not_redisplayed_during_followups(self):
        shown = self.show(self.route("做30秒短片"))
        for text in ("继续", "这三个模式有什么区别", "我还没决定"):
            r = self.route(text, shown["interaction"])
            self.assertEqual(r["action"], "ask_interaction_mode")
            self.assertIsNone(r["interaction_question"])
            self.assertEqual(r["interaction"]["status"], "pending")

    def test_discussion_has_no_automatic_question_or_stage_advance(self):
        for text in ("继续", "女主角要更主动一些", "继续聊聊女主角的动机", "为什么要这样结尾"):
            r = self.route(text, self.start())
            self.assertEqual(r["action"], "discuss_and_wait")
            self.assertEqual(r["interaction"]["discussion_stage"], "story")
            self.assertIsNone(r["interaction_question"])

    def test_explicit_delegation_selects_direct_without_menu(self):
        for text in ("自行去编排精彩剧本，生成30秒短片所需资产。", "直接执行，开发完整广告片。", "请直接做一支30秒短片", "直接完成一份完整剧本"):
            r = self.route(text)
            self.assertEqual(r["action"], "continue")
            self.assertEqual(r["interaction"]["mode"], "direct")

    def test_history_questions_negation_and_quotes_are_not_mode_selection(self):
        for text in ("我之前选过直接执行", "直接执行会不会跳过讨论", "不要直接执行", "如果直接执行会怎样", '他说“直接执行”', "男主角直接执行命令", "讨论模式是什么意思", "直接执行太快了，先谈谈人物", "直接执行有问题"):
            r = self.route(text, self.start())
            self.assertEqual(r["interaction"]["mode"], "discuss", text)

    def test_local_delegation_does_not_unlock_production(self):
        r = self.production_question()
        after = self.route("这个标题你来定", r["interaction"])
        self.assertEqual(after["interaction"]["mode"], "discuss")
        self.assertEqual(after["interaction"]["awaiting_checkpoint"], "production_start")

    def test_negative_or_ambiguous_start_keeps_pending(self):
        state = self.production_question()["interaction"]
        for text in ("先不确认开始生产", "不要确认开始生产", "确认开始生产吗？", "继续", "可以", "我之前说过确认开始生产", "我没有确认开始生产", "我没说按此开始制作", "并非确认开始生产"):
            r = self.route(text, state)
            self.assertEqual(r["interaction"]["mode"], "discuss", text)
            self.assertEqual(r["interaction"]["awaiting_checkpoint"], "production_start", text)

    def test_concrete_presented_scope_and_explicit_start(self):
        r = self.production_question()
        out = self.route("确认开始生产", r["interaction"])
        self.assertEqual(out["action"], "continue")
        self.assertEqual(out["interaction"]["discussion_stage"], "production")
        self.assertEqual(out["interaction"]["approved_production_revision"], 1)
        self.assertFalse(out["image_generation_authorized"])
        self.assertFalse(out["video_generation_authorized"])

    def test_empty_scope_never_offers_a_start_button(self):
        r = self.route("准备生产", self.start())
        self.assertEqual(r["action"], "prepare_production_scope")
        self.assertIsNone(r["interaction_question"])

    def test_changed_scope_invalidates_old_answer(self):
        r = self.production_question()
        old = r["interaction"]["pending_question"]
        changed = self.route("确认开始生产", r["interaction"], production_scope=["角色五视图"])
        self.assertEqual(changed["action"], "ask_production_start")
        self.assertNotEqual(changed["interaction_question"]["question_id"], old["id"])
        self.assertIsNone(changed["interaction"]["approved_production_revision"])
        with self.assertRaisesRegex(ValueError, "presented_question"):
            self.route("", changed["interaction"], question_answer={"question_id": old["id"], "choice": "按此开始制作"})

    def test_return_to_discussion_preserves_scope_for_revision(self):
        r = self.route("继续调整", self.production_question()["interaction"])
        self.assertEqual(r["action"], "discuss_and_wait")
        self.assertIsNone(r["interaction"]["pending_question"])
        self.assertEqual(r["interaction"]["production_scope"], ["一页故事", "30秒剧本"])

    def test_analysis_detour_preserves_confirmed_mode(self):
        r = self.route("分析参考片", self.start())
        self.assertEqual(r["route"], "video_distillation")
        self.assertEqual(r["interaction"]["status"], "confirmed")
        resumed = self.route("继续聊这个故事", r["interaction"])
        self.assertEqual(resumed["action"], "discuss_and_wait")

    def test_cross_project_selection_does_not_transfer(self):
        r = route_request("做完整广告片", interaction_state=self.start("direct"), scope_id="film-B")
        self.assertEqual(r["action"], "ask_interaction_mode")

    def test_bounded_edit_does_not_start_menu_or_erase_choice(self):
        r = self.route("修改脚本第三句", self.start())
        self.assertEqual((r["route"], r["action"]), ("copy_revision", "continue"))
        self.assertEqual(r["interaction"]["mode"], "discuss")

    def test_checkpoint_waits_only_when_reached(self):
        state = self.start("checkpoints")
        self.assertEqual(self.route("继续写故事", state)["action"], "continue")
        reached = self.route("故事已写完", state, checkpoint_stage="story")
        self.assertEqual(reached["action"], "review_checkpoint_and_wait")
        shown = self.show(reached)
        self.assertIsNone(self.route("继续", shown["interaction"])["interaction_question"])

    def test_explicit_optional_stage_shortcut(self):
        r = self.route("确认故事，进入剧本", self.start())
        self.assertEqual(r["interaction"]["discussion_stage"], "script")
        self.assertEqual(r["action"], "discuss_and_wait")

    def test_new_process_reads_current_project_state(self):
        with tempfile.TemporaryDirectory(prefix="dir-interaction-test-") as temp:
            path = Path(temp) / "interaction.json"
            path.write_text(json.dumps(self.start()))
            result = subprocess.run([sys.executable, str(ROOT / "scripts/dircreative_route.py"), "继续", "--scope-id", "film-A", "--interaction-state", str(path)], text=True, capture_output=True, check=True)
            self.assertEqual(json.loads(result.stdout)["action"], "discuss_and_wait")

    def test_confirmed_choice_reaches_actual_stage_selector(self):
        from dircreative_skill_stack import stage_selection_intent, SkillStackError
        request = "做完整广告片，给故事、剧本和相关资产。"
        with self.assertRaises(SkillStackError):
            stage_selection_intent(request_text=request, stage="identity_state")
        intent, dispatch = stage_selection_intent(request_text=request, stage="identity_state", interaction_state=self.start("direct"), interaction_scope_id="film-A")
        self.assertEqual(intent["route_id"], "film_development")
        self.assertTrue(dispatch)

    def test_explicit_image_permission_does_not_consume_pending_start(self):
        r = self.route("授权生成真实图片，现在生成", self.production_question()["interaction"])
        self.assertEqual(r["action"], "ask_production_start")
        self.assertTrue(r["image_generation_authorized"])

    def test_group_adjustment_does_not_duplicate_mode_question(self):
        shown = self.show(self.route("做30秒短片"))
        r = self.route("只用创意组", shown["interaction"])
        self.assertEqual(r["interaction"]["professional_groups"], ["creative"])
        self.assertIsNone(r["interaction_question"])

    def test_modified_question_is_rejected(self):
        state = self.production_question()["interaction"]
        state["pending_question"]["payload"]["production_scope"].append("生成全片视频")
        with self.assertRaisesRegex(ValueError, "payload_changed"):
            self.route("确认开始生产", state)

    def test_reoffered_scope_has_a_new_question_lifecycle(self):
        first = self.production_question()
        old = first["interaction"]["pending_question"]["id"]
        adjusted = self.route("继续调整", first["interaction"])
        second = self.show(self.route("准备生产", adjusted["interaction"]))
        self.assertNotEqual(second["interaction"]["pending_question"]["id"], old)
        with self.assertRaisesRegex(ValueError, "presented_question"):
            self.route("", second["interaction"], question_answer={"question_id": old, "choice": "按此开始制作"})

    def test_old_checkpoint_answer_cannot_clear_a_new_checkpoint(self):
        first = self.show(self.route("故事已写完", self.start("checkpoints"), checkpoint_stage="story"))
        qid = first["interaction"]["pending_question"]["id"]
        second = self.route("", first["interaction"], question_answer={"question_id": qid, "choice": "采用，进入下一阶段"}, checkpoint_stage="visual_direction")
        self.assertEqual(second["action"], "review_checkpoint_and_wait")
        self.assertEqual(second["interaction"]["awaiting_checkpoint"], "visual_direction")

    def test_original_discussion_request_does_not_reopen_after_start(self):
        from dircreative_skill_stack import stage_selection_intent
        started = self.route("确认开始生产", self.production_question()["interaction"])
        intent, _ = stage_selection_intent(request_text="讨论共创，制作完整短片及角色资产。", stage="identity_state",
                                          interaction_state=started["interaction"], interaction_scope_id="film-A")
        self.assertEqual(intent["route_id"], "film_development")

    def test_native_acknowledgement_does_not_require_an_unexposed_call_id(self):
        r = self.route("做30秒短片")
        qid = r["interaction_question"]["question_id"]
        shown = self.route("", r["interaction"], question_receipt={"question_id": qid, "tool_name": "request_user_input_async", "accepted": True})
        self.assertIsNone(shown["interaction_question"])
        self.assertEqual(shown["interaction"]["status"], "pending")
        answer = self.route("", shown["interaction"], question_answer={"question_id": qid, "choice": "讨论共创"})
        self.assertEqual(answer["action"], "discuss_and_wait")

    def test_text_fallback_can_confirm_the_presented_scope(self):
        r = self.route("准备生产", self.start(), production_scope=["一页故事"])
        qid = r["interaction_question"]["question_id"]
        shown = self.route("", r["interaction"], question_receipt={"question_id": qid, "surface": "text_fallback", "shown": True, "unavailable_reason": "Host has no native question tool"})
        self.assertEqual(self.route("确认开始生产", shown["interaction"])["action"], "continue")


if __name__ == "__main__":
    unittest.main()
