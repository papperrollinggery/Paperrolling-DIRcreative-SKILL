"""Project-scoped conversation pacing used by the existing DIR route.

Native question receipts/answers come from the host, never project source prose.
This module returns decisions; it does not display UI, dispatch workers or grant
image, video, client-delivery or repository-maintenance authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any


MODES = ("discuss", "direct", "checkpoints")
MODE_LABELS = {"discuss": "讨论共创", "direct": "直接执行", "checkpoints": "关键节点讨论"}
EXCLUDED_ROUTES = {"source_maintenance", "invalid_specialist_exchange", "adco_specialist_exchange", "video_distillation"}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _affirmative_clauses(request: str) -> list[str]:
    # Preserve full clause grammar. Historical, hypothetical, quoted, interrogative
    # and negated references are not interaction decisions.
    from dircreative_route import action_text
    clauses = re.split(r"[。；;\n，,]", action_text(request))
    return [c.strip() for c in clauses if c.strip() and not re.search(
        r"之前|以前|上次|曾经|当时|原来|历史|假如|如果|要是|等.{0,12}再|"
        r"是否|能否|可否|会不会|要不要|为什么|怎么|如何|是什么|有什么|哪些|优缺点|[?？]|吗\s*$|"
        r"(?:先|暂时|现在)?不(?:要|用|能|会|想|确认|开始|进入|执行)|别|尚未|还没|没有|没说|并非|未曾|未确认|"
        r"\b(?:previously|earlier|if|should|could|why|not|don't|do not)\b",
        c, re.IGNORECASE)]


def mode_choice(request: str) -> str | None:
    # A local '你来定' never changes the project. Explicit delegated full-film
    # work (自行编排/自主完成) does select direct operation for the stated scope.
    selected = None
    for clause in _affirmative_clauses(request):
        clause = re.sub(r"^\$dircreative\s*", "", clause)
        prefix = r"^(?:(?:这次|本次|本项目|现在|接下来|后续|请|帮我|我选|我选择|选择|采用|切换到|改成|使用|用|(?:根据|按|基于).{0,10}(?:brief|方案|计划|剧本|方向))\s*)*"
        if re.search(prefix + r"(?:关键节点(?:讨论|确认)|节点确认模式|checkpoints? mode)", clause, re.I):
            selected = "checkpoints"
        elif re.search(prefix + r"(?:讨论共创|共创模式|讨论模式|(?:先|一起|跟我|和我).{0,8}(?:讨论|聊聊|谈谈|共创)|discussion mode|let'?s discuss)", clause, re.I):
            selected = "discuss"
        elif re.search(prefix + r"(?:直接(?:执行|做|完成)(?!太|很|会|更|比较|是|的|有|让|可能)|(?:自行|自主).{0,6}(?:编排|创作|完成|执行)|direct execution(?: mode)?$|execute directly)", clause, re.I):
            selected = "direct"
    # Explicit no-discussion preference is affirmative about pacing; don't let
    # '不要直接执行' take this branch.
    from dircreative_route import action_text
    for clause in re.split(r"[。；;，,]", action_text(request)):
        if re.fullmatch(r"(?:这次|本次|现在|请)?(?:不讨论|不用讨论|不要讨论|无需讨论)(?:了)?", clause.strip()):
            selected = "direct"
    return selected


def _matches(request: str, pattern: str) -> bool:
    return any(re.search(pattern, c, re.I) for c in _affirmative_clauses(request))


def initial_state(scope_id: str) -> dict[str, Any]:
    return {"scope_id": scope_id, "status": "not_required", "mode": None,
            "professional_groups": [], "discussion_stage": "story",
            "checkpoint_stages": ["story", "visual_direction"],
            "awaiting_checkpoint": None, "choice_source": None,
            "production_scope": [], "production_revision": 0,
            "approved_production_revision": None, "pending_question": None,
            "question_sequence": 0}


def _question(state: dict[str, Any], kind: str, payload: dict[str, Any]) -> None:
    # Advising a different professional group does not re-open the same pacing
    # decision. Production payloads include their exact scope and revision.
    identity_payload = {k: v for k, v in payload.items() if k != "groups"}
    old = state["pending_question"]
    if old and old["kind"] == kind and {k: v for k, v in old["payload"].items() if k != "groups"} == identity_payload:
        return
    state["question_sequence"] += 1
    key = _digest([state["scope_id"], kind, identity_payload, state["question_sequence"]])
    state["pending_question"] = {"id": key, "kind": kind, "payload": payload,
                                 "host_call_id": None, "presented": False}


def resolve(
    request: str, route: str, reasons: list[str], *, scope_id: str,
    previous: dict[str, Any] | None = None, checkpoint_stage: str | None = None,
    production_scope: list[str] | None = None,
    question_receipt: dict[str, Any] | None = None,
    question_answer: dict[str, str] | None = None,
    event_request: str | None = None,
) -> tuple[dict[str, Any], bool]:
    from dircreative_route import ROOT, action_text, collaboration_contract, load_policy, requests_whole_film_development
    from dircreative_state_audit import _builtin_schema_errors
    if not isinstance(scope_id, str) or not scope_id.strip():
        raise ValueError("interaction_scope_id_required")
    state = initial_state(scope_id)
    if previous is not None:
        schema = json.loads((ROOT / "skills/dircreative/runtime/state-snapshot.schema.json").read_text())
        errors = _builtin_schema_errors(previous, schema["properties"]["interaction"], schema, "$.interaction")
        if errors:
            raise ValueError("invalid_interaction_state:" + str(errors[0]))
        if previous["scope_id"] == scope_id:
            state.update(copy.deepcopy(previous))
            pending = state["pending_question"]
            if pending is not None:
                payload = pending["payload"]
                if not isinstance(payload.get("options"), list) or not payload["options"] or not isinstance(payload.get("title"), str):
                    raise ValueError("invalid_interaction_question_payload")
                expected = _digest([scope_id, pending["kind"], {k: v for k, v in payload.items() if k != "groups"}, state["question_sequence"]])
                if pending["id"] != expected:
                    raise ValueError("interaction_question_payload_changed")
                if pending["kind"] == "production_start" and (payload.get("production_scope") != state["production_scope"] or payload.get("revision") != state["production_revision"]):
                    raise ValueError("interaction_production_question_stale")
    excluded = route in EXCLUDED_ROUTES or bool(set(reasons) & {
        "identity_state_contract_required", "seedance25_formal_compile", "layered_humanization"})
    asset_only = "asset_design_required" in reasons and not requests_whole_film_development(request)
    # Existing-artifact maintenance does not open a new-project onboarding.
    revision = bool(re.search(r"修改|优化|调整|润色|改写|评审|revise|rewrite|review", action_text(request), re.I))
    eligible = route == "film_development" and not excluded and not asset_only and not revision
    active = not excluded and not asset_only and (eligible or (
        state["status"] in {"pending", "confirmed"} and route in {"film_development", "bounded_revision"}) or (
        state["awaiting_checkpoint"] == "production_start" and route in {"generation_authorization", "client_delivery"}))
    if not active:
        return state, False  # Temporary analysis/edit preserves project choice.

    # Production consumers replay the original media request for its permissions
    # and craft scope, but not as a new conversational choice.
    event_request = request if event_request is None else event_request
    choice = mode_choice(event_request)
    old_question = state["pending_question"]
    if question_receipt is not None:
        native_accepted = question_receipt.get("accepted") is True and isinstance(question_receipt.get("tool_name"), str) and bool(question_receipt["tool_name"])
        text_shown = question_receipt.get("surface") == "text_fallback" and question_receipt.get("shown") is True and bool(question_receipt.get("unavailable_reason"))
        if not old_question or question_receipt.get("question_id") != old_question["id"] or not (question_receipt.get("host_call_id") or native_accepted or text_shown):
            raise ValueError("question_receipt_does_not_match_pending_question")
        if question_receipt.get("host_call_id") and old_question["host_call_id"] not in {None, question_receipt["host_call_id"]}:
            raise ValueError("question_already_presented")
        old_question["presented"] = True
        old_question["host_call_id"] = question_receipt.get("host_call_id", old_question["host_call_id"])
    answer = None
    if question_answer is not None:
        if not old_question or not old_question["presented"] or question_answer.get("question_id") != old_question["id"]:
            raise ValueError("answer_does_not_match_presented_question")
        answer = question_answer.get("choice")
        if isinstance(answer, str):
            answer = re.sub(r"（推荐）$", "", answer)
        if answer not in old_question["payload"]["options"]:
            raise ValueError("answer_choice_not_offered")
        if old_question["kind"] == "interaction_setup":
            choice = {v: k for k, v in MODE_LABELS.items()}[answer]

    if choice is not None:
        state.update(status="confirmed", mode=choice, choice_source="current_user")
        if old_question and old_question["kind"] == "interaction_setup":
            state["pending_question"] = None
        # Choosing direct during a pending production decision changes pacing,
        # not the unapproved scope; the production question stays in force.
    elif state["status"] != "confirmed":
        state.update(status="pending", mode=None, choice_source=None)
    groups = collaboration_contract(event_request, route, "continue", load_policy())["requested_groups"]
    if _matches(event_request, r"只(?:用|要|让).{0,3}创意组"):
        groups = ["creative"]
    elif _matches(event_request, r"只(?:用|要|让).{0,3}导演组"):
        groups = ["director"]
    state["professional_groups"] = groups or state["professional_groups"] or ["creative", "director"]

    if state["status"] == "pending":
        _question(state, "interaction_setup", {"title": "DIRcreative · 协作方式",
                  "options": list(MODE_LABELS.values()), "recommended": "讨论共创",
                  "groups": state["professional_groups"]})
        return state, True

    if checkpoint_stage is not None:
        if state["discussion_stage"] == "production":
            raise ValueError("creative_checkpoints_do_not_interrupt_production")
        if state["mode"] != "checkpoints" or checkpoint_stage not in state["checkpoint_stages"]:
            raise ValueError("checkpoint_not_in_confirmed_plan")
        state["awaiting_checkpoint"] = checkpoint_stage
    if _matches(event_request, r"(?:确认|采用|通过).{0,6}故事") and _matches(event_request, r"(?:进入|开始|写)剧本"):
        state["discussion_stage"] = "script"
    if _matches(event_request, r"(?:确认|采用|通过).{0,6}剧本") and _matches(event_request, r"(?:进入|开始|做)分镜"):
        state["discussion_stage"] = "shots"

    if production_scope is not None:
        if not production_scope or not all(isinstance(i, str) and i.strip() for i in production_scope):
            raise ValueError("production_scope_must_list_deliverables")
        if production_scope != state["production_scope"]:
            state["production_scope"] = list(production_scope)
            state["production_revision"] += 1
            state["approved_production_revision"] = None
            state["awaiting_checkpoint"] = "production_start"
            state["discussion_stage"] = "production_ready"
            # An answer to the previous scope must not authorize this revision.
            answer = None
            old_question = None
    if state["mode"] != "direct" and _matches(event_request, r"准备生产|准备制作|ready for production"):
        state["awaiting_checkpoint"] = "production_start"
        state["discussion_stage"] = "production_ready"
    if state["awaiting_checkpoint"] == "production_start":
        if answer == "继续调整" or _matches(event_request, r"继续讨论|继续调整|再聊聊|再讨论|keep discussing"):
            state.update(awaiting_checkpoint=None, pending_question=None, discussion_stage="story", mode="discuss")
        elif state["production_scope"]:
            payload = {"title": "DIRcreative · 开始制作", "options": ["按此开始制作", "继续调整"],
                       "production_scope": state["production_scope"], "revision": state["production_revision"]}
            _question(state, "production_start", payload)
            pending = state["pending_question"]
            same_presented = old_question and old_question["id"] == pending["id"] and old_question["presented"]
            explicit_start = any(re.fullmatch(
                r"(?:(?:我|请|现在|就|那就)\s*)*(?:确认开始生产|按此开始制作|按这个方向开始(?:做|制作)|开始刚才.{0,8}(?:制作|生产)|start (?:the )?agreed production)(?:吧|即可|就行)?",
                clause, re.I) for clause in _affirmative_clauses(event_request))
            if same_presented and (answer == "按此开始制作" or explicit_start):
                state.update(mode="direct", discussion_stage="production", awaiting_checkpoint=None,
                             approved_production_revision=state["production_revision"], pending_question=None)
    elif state["awaiting_checkpoint"]:
        stage = state["awaiting_checkpoint"]
        _question(state, "checkpoint", {"title": "DIRcreative · 方向确认",
                  "options": ["采用，进入下一阶段", "继续调整"], "stage": stage})
        if old_question and old_question["id"] == state["pending_question"]["id"] and answer in {"采用，进入下一阶段", "继续调整"}:
            state.update(awaiting_checkpoint=None, pending_question=None)
            if answer == "继续调整":
                state["mode"] = "discuss"
    return state, True


def response(state: dict[str, Any], active: bool) -> tuple[str | None, dict[str, Any] | None]:
    if not active:
        return None, None
    action = None
    if state["status"] == "pending":
        action = "ask_interaction_mode"
    elif state["awaiting_checkpoint"] == "production_start":
        action = "ask_production_start" if state["production_scope"] else "prepare_production_scope"
    elif state["awaiting_checkpoint"]:
        action = "review_checkpoint_and_wait"
    elif state["mode"] == "discuss":
        action = "discuss_and_wait"
    pending = state["pending_question"]
    question = None
    if pending and not pending["presented"]:
        question = {**pending["payload"], "question_id": pending["id"],
                    "surface": "native_question_tool", "requires_submitted_answer": True}
    return action, question
