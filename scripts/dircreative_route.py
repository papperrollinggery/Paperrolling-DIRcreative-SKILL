#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "skills/dircreative/runtime/routing-policy.yaml"
CASES_PATH = ROOT / "tests/fixtures/routing/cases.json"
DESCRIPTOR_PATH = ROOT / "docs/film-preproduction/schemas/adco-specialist-descriptor.json"


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    try:
        data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"routing policy parse failed: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("routing policy must be a mapping")
    return data


def has(text: str, pattern: str) -> bool:
    return re.search(pattern, text, flags=re.IGNORECASE) is not None


QUOTED_OR_CODE_RE = re.compile(
    r"```.*?```|`[^`]*`|“[^”]*”|‘[^’]*’|\"[^\"]*\"|'[^']*'|"
    r"【[^】]*】|「[^」]*」|『[^』]*』|《[^》]*》|〈[^〉]*〉|〔[^〕]*〕|"
    r"\[[^\]]*\]|（[^）]*）|\([^)]*\)",
    flags=re.DOTALL,
)


def action_text(request: str) -> str:
    """Remove quoted/example payloads before deciding whether an action was authorized."""
    return " ".join(QUOTED_OR_CODE_RE.sub(" ", request).split())


def explicit_action_match(text: str, pattern: str) -> bool:
    """Accept an imperative only when it is not negated, conditional, or a question."""
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        before = re.split(r"[。；;\n]", text[max(0, match.start() - 36) : match.start()])[-1]
        after = re.split(r"[。；;\n]", text[match.end() : match.end() + 48])[0]
        if has(
            before,
            r"(?:不要|别|暂时别|暂不|先别|先不要|无需|不用|不需要|不可|不能|禁止|勿|"
            r"尚未|还未|还没|并未|未经|未获|未曾|未批准|未授权|是否|能否|可否|可以不|"
            r"should\s+we|could\s+we|do\s+not|don't|\bnot\b(?:\s+yet)?|"
            r"without\s+(?:approval|authorization)|unauthori[sz]ed|unapproved).{0,12}$|"
            r"未\s*$|"
            r"(?:如果|若|假如|if\s+).{0,20}$|等.{0,8}(?:再|后).{0,8}$",
        ):
            continue
        if has(
            after,
            r"^[\s:：=，,;；。]*(?:false\b|no\b|否(?:\s|[.。;；]|$)|未批准|未授权|"
            r"不得|不要|别|禁止|勿|do\s+not\b|don't\b)",
        ):
            continue
        if has(
            after,
            r"(?:[?？]|吗(?:\s|$)|呢(?:\s|$)|是否|能否|可否|可不可以|会不会|要不要|"
            r"多少钱|费用|成本|价格|如何|怎么|哪些|谁|何时|为什么)",
        ):
            continue
        return True
    return False


def collaboration_contract(request: str, route: str, action: str, policy: dict[str, Any]) -> dict[str, Any]:
    """Describe host collaboration intent; this function never dispatches a worker.

    The selected route remains authoritative. Team names describe perspectives;
    only affirmative collaboration or new-task instructions select host work.
    """
    config = policy["collaboration_policy"]
    clauses = re.split(r"[。；;！？?!\n，,]", action_text(request))
    groups: set[str] = set()
    subagents_requested = False
    threads_requested = False
    joint_requested = False
    for clause in clauses:
        denied = has(clause, r"不要|不用|无需|不需要|禁止|别|\b(?:not|never)\b|don't")
        if denied:
            if has(clause, r"子代理|sub[- ]?agents?"):
                subagents_requested = False
            if has(clause, r"新任务|独立任务|线程|\b(?:tasks?|threads?)\b"):
                threads_requested = False
            if has(clause, r"联合|协作|并行|joint|parallel|collaborat"):
                joint_requested = False
            if has(clause, r"导演组|director\s+(?:team|room)"):
                groups.discard("director")
                joint_requested = False
            if has(clause, r"创意组|creative\s+team"):
                groups.discard("creative")
                joint_requested = False
            continue
        # A historic report, explanation, conditional, or negated invocation is
        # context, not a fresh delegation instruction. Inspect the instruction
        # prefix: the assigned worker may legitimately explain or research how
        # to solve the task after the user has explicitly requested dispatch.
        target = re.search(r"调用|启用|启动|创建|新建|导演组|创意组|子代理|sub[- ]?agents?|threads?", clause, re.IGNORECASE)
        prefix = clause[:target.start()] if target else clause
        if has(prefix, r"如果|假如|是否|能否|可否|等.{0,12}(?:确认|批准).{0,8}(?:后|再)|"
               r"之前|过去|上次|曾经|解释|如何|怎么|"
               r"\b(?:if|unless|explain|previously)\b|how\s+to"):
            continue
        if has(clause, r"调用有问题|调用失败") and not has(prefix, r"请|帮我"):
            continue
        if has(clause, r"^(?:\s*\$dircreative\s*)?(?:请|帮我)?\s*(?:比较|介绍|说明|分析).{0,12}(?:导演组|创意组|子代理|新任务)"):
            continue
        requested_group = has(
            clause,
            r"(?:调用|启用|让|安排|召集|组织|使用|交给|由).{0,24}(?:导演组|创意组)|"
            r"请\s*(?:导演组|创意组)|"
            r"(?:导演组|创意组).{0,12}(?:请|负责|来做|来写|启用|联合|协作|并行)|"
            r"(?:use|invoke|ask|engage).{0,24}(?:director|creative)\s+(?:room|team)",
        )
        if requested_group:
            if has(clause, r"创意组|creative\s+team"):
                groups.add("creative")
            if has(clause, r"导演组|director\s+(?:room|team)"):
                groups.add("director")
            joint_requested |= has(clause, r"联合|并行|协作|joint|parallel|collaborat")
        subagents_requested |= has(
            clause,
            r"(?:调用|启用|启动|使用|安排|让|用).{0,20}(?:子代理|sub[- ]?agents?)|"
            r"请\s*(?:真实\s*)?(?:子代理|sub[- ]?agents?)|"
            r"(?:子代理|sub[- ]?agents?).{0,12}(?:并行|协作|来做|负责|执行)|"
            r"(?:use|spawn|start|invoke|dispatch).{0,20}sub[- ]?agents?",
        )
        threads_requested |= has(
            clause,
            r"(?:创建|新建|开启|启动|开)\s*(?:[一二两三四五六七八九十0-9]+\s*(?:个|条)?\s*)?"
            r"(?:新的?|独立的?)?(?:任务|线程)|"
            r"(?:使用|启用|创建|新建|用).{0,12}(?:真实\s*)?(?:Threads?\b|线程)|"
            r"(?:create|start|open).{0,16}(?:new|separate|independent).{0,10}(?:tasks?|threads?)",
        )
    requested_mode = "threads" if threads_requested else "subagents" if subagents_requested or joint_requested else "perspectives"
    blocked_context = route in {"source_maintenance", "invalid_specialist_exchange", "adco_specialist_exchange"}
    dispatch_allowed = not blocked_context and action == "continue"
    execution_mode = (
        "none" if blocked_context else
        "host_threads" if requested_mode == "threads" and dispatch_allowed else
        "host_subagents" if requested_mode == "subagents" and dispatch_allowed else
        "main_thread_perspectives"
    )
    return {
        "requested_groups": sorted(groups),
        "requested_mode": requested_mode,
        "execution_mode": execution_mode,
        "execution_status": "blocked_by_context" if blocked_context else "blocked_by_gate" if not dispatch_allowed else "not_dispatched",
        "subagents_allowed": execution_mode == "host_subagents",
        "threads_allowed": execution_mode == "host_threads",
        "max_subagents": config["max_subagents"] if execution_mode == "host_subagents" else 0,
        "nested_dispatch_allowed": False,
        "dispatch_receipts": [],
        "host_capability_check_required": execution_mode in {"host_threads", "host_subagents"},
        "unavailable_host_action": config["unavailable_host_action"],
    }


GENERATION_DENIAL_RE = re.compile(
    r"没有(?:获得)?授权|未获(?:得)?授权|未经授权|从未批准|从未授权|"
    r"(?:生成授权|授权).{0,12}没有(?:获得)?批准|"
    r"(?:客户|用户).{0,16}?(?:没有|未|不同意|不|拒绝|撤销).{0,8}?"
    r"(?:同意|批准)?(?:生成授权|生成|授权)|"
    r"授权(?:已|被)?(?:撤销了?|拒绝|失效)|不得(?:执行|生成)|不要生成|禁止生成|"
    r"(?:authorization|approval)(?:\s+for\s+generation)?\s+"
    r"(?:has(?:\s+not|n't)\s+been\s+granted|"
    r"(?:was|is)(?:\s+not|n't)\s+(?:granted|approved)|"
    r"never\s+(?:granted|approved)|(?:(?:was|is|has\s+been)\s+)?"
    r"(?:denied|revoked|rejected|refused|declined|expired))|"
    r"(?:client|user).{0,24}?(?:denied|revoked|rejected|refused|declined|"
    r"did(?:\s+not|n't)|does(?:\s+not|n't)|has(?:\s+not|n't)|never)"
    r".{0,20}?(?:generation|generat(?:e|ion)|authorization|approval)|"
    r"never\s+(?:authorized|approved)|do\s+not\s+generate",
    re.IGNORECASE,
)
GENERATION_REAUTH_RE = re.compile(
    r"(?:我|本人)\s*(?:(?:现在|重新|明确|正式|确认)\s*)*授权\s*(?:真实)?生成|"
    r"\bi\s+(?:now\s+|hereby\s+|explicitly\s+|re-?)?authorize\s+"
    r"(?:real\s+)?generation(?:\s+now)?",
    re.IGNORECASE,
)
DELIVERY_DENIAL_RE = re.compile(
    r"(?:客户交付|外发|发给客户).{0,12}(?:没有(?:获得)?批准|未获(?:得)?批准|"
    r"未经批准|从未批准|批准(?:已|被)?(?:撤销|拒绝|失效)|不得|禁止)|"
    r"(?:客户|用户).{0,16}?(?:没有|未|不同意|不|拒绝|撤销).{0,8}?"
    r"(?:同意|批准|授权)?(?:客户交付|外发|发给客户)|"
    r"没有(?:获得)?批准.{0,12}(?:客户交付|外发|发给客户)|"
    r"(?:client\s+delivery|send(?:ing)?\s+to\s+(?:the\s+)?client).{0,24}"
    r"(?:not\s+approved|never\s+approved|denied|revoked|expired)|"
    r"(?:approval|client\s+delivery\s+approval)\s+(?:has\s+)?"
    r"(?:not\s+been\s+granted|never\s+approved|denied|revoked|expired)|"
    r"(?:client|user).{0,24}?(?:denied|revoked|rejected|refused|declined|"
    r"did(?:\s+not|n't)|does(?:\s+not|n't)|has(?:\s+not|n't)|never)"
    r".{0,20}?(?:delivery|send(?:ing)?|approval|authorization)|"
    r"do\s+not\s+send",
    re.IGNORECASE,
)
DELIVERY_REAUTH_RE = re.compile(
    r"(?:我|本人)\s*(?:(?:现在|重新|明确|正式|确认)\s*)*(?:批准|授权)\s*"
    r"(?:客户交付|外发|发给客户)|"
    r"\bi\s+(?:now\s+|hereby\s+|explicitly\s+|re-?)?(?:approve|authorize)\s+"
    r"(?:the\s+)?client\s+delivery",
    re.IGNORECASE,
)


def generation_authorized(request: str) -> bool:
    text = action_text(request)
    denials = list(GENERATION_DENIAL_RE.finditer(text))
    if denials:
        return explicit_action_match(
            text[denials[-1].end() :], GENERATION_REAUTH_RE.pattern
        )
    return explicit_action_match(
        text,
        r"(?:现在|立即|直接|马上|开始|(?<!申)请)\s*(?:真实)?生成|"
        r"(?:直接|立即|马上|现在|请|帮我)\s*(?:出图|渲染(?:一张图)?|跑(?:一张|图))|"
        r"(?:^|\s)跑一张(?:看看|试试)?|"
        r"(?:我|本人)\s*(?:(?:现在|重新|明确|正式|确认)\s*)*授权\s*(?:真实)?生成|"
        r"(?:please\s+)?generate\s+now|start\s+(?:real\s+)?generation(?:\s+now)?|"
        r"\bi\s+(?:hereby\s+)?authorize\s+(?:real\s+)?generation(?:\s+now)?",
    )


def client_delivery_authorized(request: str) -> bool:
    text = action_text(request)
    denials = list(DELIVERY_DENIAL_RE.finditer(text))
    if denials:
        return explicit_action_match(
            text[denials[-1].end() :], DELIVERY_REAUTH_RE.pattern
        )
    return explicit_action_match(
        text,
        r"(?:现在|立即|直接|马上|(?<!申)请)\s*(?:正式\s*)?"
        r"(?:交付(?:给)?|发送(?:给)?|发给)客户|"
        r"(?:现在|立即|马上)\s*把(?:这个|该|这些)?(?:文件|成片|结果|素材|资产)?\s*发给客户|"
        r"正式\s*(?:交付(?:给)?|发送(?:给)?|发给)客户|"
        r"(?:我|本人)\s*(?:(?:现在|重新|明确|正式|确认)\s*)*(?:批准|授权)\s*"
        r"(?:客户交付|外发|发给客户)|"
        r"(?:please\s+)?send\s+to\s+(?:the\s+)?client\s+now|"
        r"send\s+(?:the\s+)?client\s+delivery\s+now",
    )


def denied_generation_followed_by_imperative(request: str) -> bool:
    text = action_text(request)
    denials = list(GENERATION_DENIAL_RE.finditer(text))
    if not denials:
        return False
    return explicit_action_match(
        text[denials[-1].end() :],
        r"(?:现在|立即|直接|马上|开始)\s*(?:真实)?生成|"
        r"(?:please\s+)?generate\s+now|start\s+(?:real\s+)?generation",
    )


def requested_asset_components(request: str) -> dict[str, bool]:
    """Find requested asset work inside the existing route, never authorization.

    This is a design intake. A role may still be ruled out by the developed story;
    no entity, image, source approval or generation event is created here.
    """
    text = action_text(request)
    if has(text, r"提示词|prompt") and explicit_action_match(
        text, r"改短|缩短|精简|修改|改写|调整|优化|压缩|revise|shorten|compress"
    ) and not requests_whole_film_development(request):
        return dict.fromkeys(("identity_state", "production_design", "camera_geography", "mechanical_transformation", "reuse"), False)
    # Keep coordinated exclusions together (不要人物、场景和道具资产). An
    # excluded role must not turn into a positive request because its noun exists.
    clauses = re.split(r"[。；;!?！？\n，,]", text)
    positive_clauses = [
        re.split(r"不要|不需要|无需|不用|不做|别做|不改变|do\s+not|don't|without", clause, maxsplit=1, flags=re.IGNORECASE)[0]
        for clause in clauses
    ]
    positive = " ".join(positive_clauses)
    asset_words = has(positive, r"资产|母版|设定图|参考图|设计图|asset|reference\s+(?:image|sheet)|master\s+sheet")
    related = has(positive, r"相关(?:图片|图像|参考)?资产|所需(?:图片|图像|参考)?资产") and has(
        positive, r"九宫格|九格|分镜|故事|剧情|storyboard|story"
    )
    character = explicit_action_match(positive, r"人物母版|角色母版|人物设定(?:图|资产)|角色设定(?:图|资产)|"
                                     r"character\s+(?:master|turnaround|model)\s+(?:sheet|asset)") or (
        asset_words and has(positive, r"人物|角色|服装状态|造型状态|character|wardrobe")
    )
    scene = asset_words and has(positive, r"场景|环境|地理|scene|location")
    prop = asset_words and has(positive, r"道具|产品|载具|武器|prop|product|vehicle")
    mechanical = has(positive, r"机械|机甲|折叠盾|铰链|锁止|mechanical|mecha") and has(
        positive, r"展开|折叠|变形|结构|部署|transform|deploy|fold"
    )
    role_patterns = {
        "identity_state": r"人物|角色|服装|造型|character|wardrobe",
        "production_design": r"道具|产品|载具|武器|机械|机甲|折叠盾|prop|product|vehicle|mechanical|mecha",
        "camera_geography": r"场景|环境|地理|scene|location",
    }
    requested_roles = {
        role for role, present in zip(role_patterns, (character or related, prop or related or mechanical, scene or related))
        if present
    }
    supplied_roles: set[str] = set()
    reused_roles: set[str] = set()
    newly_requested_roles: set[str] = set()
    reuse = False
    # Reuse applies to its objects, not to all later clauses or every asset role.
    for clause in positive_clauses:
        for part in re.split(r"并且|同时|另外|然后|并(?=给|为|制作|生成|设计)|\band\s+(?=create|make|generate|design|reuse)", clause, flags=re.IGNORECASE):
            roles = {role for role, pattern in role_patterns.items() if has(part, pattern)}
            supplied = has(part, r"已给|已有|现有|提供|existing|supplied")
            if supplied:
                supplied_roles.update(roles)
            reuse_action = explicit_action_match(part, r"沿用|复用|继续用|reuse") and bool(
                roles or has(part, r"图片|图像|素材|资产|母版|参考图|PNG|images?|assets?|master|references?")
            )
            if reuse_action:
                reuse = True
                reused_roles.update(roles or supplied_roles or requested_roles)
            creation = explicit_action_match(part, r"生成|制作|设计|建立|创建|改成|改为|修改|换|create|make|generate|design|change")
            changed_or_new = has(part, r"新(?:的|人物|角色|场景|建|做)|另一个|淋湿|破损|受损|损伤|状态|\bnew\b|another|damaged|wet|state")
            if not roles and creation and has(part, r"淋湿|破损|受损|损伤|状态|damaged|wet|state"):
                available = reused_roles or supplied_roles
                state_hints = {
                    "identity_state": r"衣袖|袖口|左袖|右袖|衣摆|发型|发丝|伤痕|sleeve|cuff|hairstyle|scar",
                    "production_design": r"瓶盖|包装|铰链|车轮|刀刃|握柄|hinge|wheel|blade|handle|bottle\s*cap",
                    "camera_geography": r"墙面|墙壁|地面|屋顶|天花板|wall|floor|roof|ceiling",
                }
                roles = {role for role in available if has(part, state_hints[role])}
                if not roles and (len(available) == 1 or has(part, r"全部|全都|所有|\ball\b")):
                    roles = available
            if roles and (creation or (changed_or_new and not supplied)) and (not reuse_action or changed_or_new):
                newly_requested_roles.update(roles)
    cancelled = " ".join(re.findall(
        r"(?:不要|不需要|无需|不用|不做|别做|do\s+not|don't|without)(?!改变|修改|改动)([^。；;!?！？\n，,]+)",
        text, flags=re.IGNORECASE,
    ))
    cancellation_has_assets = related or has(cancelled, r"资产|母版|设定图|参考图|asset|sheet")
    return {
        "identity_state": bool((character or related) and ("identity_state" not in reused_roles or "identity_state" in newly_requested_roles) and not (cancellation_has_assets and has(cancelled, r"人物|角色|character"))),
        "production_design": bool((prop or related or mechanical) and ("production_design" not in reused_roles or "production_design" in newly_requested_roles) and not (cancellation_has_assets and has(cancelled, r"道具|产品|载具|武器|prop|product|vehicle"))),
        "camera_geography": bool((scene or related) and ("camera_geography" not in reused_roles or "camera_geography" in newly_requested_roles) and not (cancellation_has_assets and has(cancelled, r"场景|环境|scene|location"))),
        "mechanical_transformation": bool(mechanical),
        "reuse": bool(reuse),
    }


def requests_whole_film_development(request: str) -> bool:
    text = action_text(request)
    return explicit_action_match(text, r"(?:做|制作|创作|开发|完成|筹备).{0,24}(?:短片|广告片|品牌片|电影)|"
                                r"(?:完整|全套|全部|全片).{0,24}(?:前期|流程|剧本|故事|分镜)|"
                                r"(?:make|create|develop|prepare).{0,32}(?:film|commercial|movie)")


def classify_media_scope(request: str) -> dict[str, Any]:
    """Resolve image generation and final-video generation as separate scopes."""
    text = action_text(request)
    prompt_only = has(
        text,
        r"prompt[- ]?only|dry[- ]?run|纯文本|只(?:输出|做|给).{0,20}(?:提示词|资产计划)|"
        r"不要?(?:实际)?生成(?:任何)?(?:真实)?媒体|不出图",
    )
    image_denied = has(
        text,
        r"不要生成(?:任何)?(?:真实)?(?:图片|图像)|不生成(?:任何)?(?:真实)?(?:图片|图像)|"
        r"不授权(?:任何)?(?:图片|图像)(?:资产)?生成|"
        r"do\s+not\s+generate\s+(?:any\s+)?images?|no\s+image\s+generation",
    )
    video_denied = has(
        text,
        r"不要生成(?:最终)?视频|不生成(?:最终)?视频|不授权(?:最终)?视频生成|"
        r"视频生成(?:暂缓|延后|不在本轮)|停在视频生成前|"
        r"do\s+not\s+generate\s+(?:the\s+)?(?:final\s+)?video|no\s+video\s+generation",
    )
    pre_video_assets = has(
        text,
        r"(?:直到|完成|做到|走到).{0,16}(?:视频生成|生成视频)(?:之)?前.{0,24}(?:全部|全套|流程|图片|图像|资产)|"
        r"(?:视频生成|生成视频)前.{0,24}(?:全部|全套|流程|图片|图像|资产)|"
        r"(?:全部|全套|完整).{0,20}(?:前期图片|图片资产|视觉资产)|"
        r"(?:pre[- ]video|pre[- ]generation).{0,24}(?:image|visual|asset)",
    )
    image_action = explicit_action_match(
        text,
        r"(?:生成|产出|制作|做完|落盘).{0,16}(?:图片|图像|图片资产|视觉资产)|"
        r"(?:图片|图像|图片资产|视觉资产).{0,16}(?:生成|产出|制作|做完|落盘)|"
        r"出图|渲染(?:一张图)?|跑图|跑一张(?:看看|试试)?|"
        r"generate.{0,16}(?:images?|visual assets?)",
    )
    video_action = explicit_action_match(
        text,
        r"(?:生成|制作|开始|授权).{0,16}(?:最终视频|成片|视频生成)|"
        r"(?:最终视频|成片).{0,12}(?:生成|制作)|generate.{0,16}(?:final\s+)?video",
    )
    forwarded_context = has(
        text,
        r"用户原始要求|原始用户要求|派发限制|转交限制|source\s+request|delegated\s+constraint",
    )
    authorization_application = has(
        text,
        r"(?:正在|准备|打算)?申请.{0,16}(?:生成|出图|视频).{0,8}授权|"
        r"apply(?:ing)?\s+for.{0,16}(?:generation|rendering)\s+authorization",
    )
    planning_request = has(
        text,
        r"需要哪些|包括什么|包含什么|有哪些|只想知道|帮我规划|请规划|"
        r"怎么规划|如何规划|what\s+(?:does|is|are)|explain\s+how|"
        r"plan(?:ning)?\s+the\s+workflow",
    )
    explanation_request = has(text, r"explain\s+how\s+to|how\s+do\s+i") and not has(
        text, r"(?:then|and\s+then).{0,16}generate|然后.{0,16}生成",
    )
    scope_conflict = forwarded_context and pre_video_assets and image_denied
    if scope_conflict:
        return {
            "media_scope": "scope_conflict",
            "image_generation_authorized": False,
            "video_generation_authorized": False,
            "minimum_evidence": "scope_resolution_required",
        }
    if prompt_only or (image_denied and not video_action):
        return {
            "media_scope": "prompt_only",
            "image_generation_authorized": False,
            "video_generation_authorized": False,
            "minimum_evidence": "planning_artifacts",
        }
    if authorization_application or explanation_request or (
        planning_request and not image_action and not video_action
    ):
        return {
            "media_scope": "planning_only",
            "image_generation_authorized": False,
            "video_generation_authorized": False,
            "minimum_evidence": "planning_artifacts",
        }
    if video_action and not video_denied:
        return {
            "media_scope": "video_generation",
            "image_generation_authorized": image_action and not image_denied,
            "video_generation_authorized": True,
            "minimum_evidence": "generated_video",
        }
    if pre_video_assets or image_action:
        return {
            "media_scope": "pre_video_assets",
            "image_generation_authorized": True,
            "video_generation_authorized": False,
            "minimum_evidence": "generated_image_assets",
        }
    return {
        "media_scope": "planning_only",
        "image_generation_authorized": False,
        "video_generation_authorized": False,
        "minimum_evidence": "planning_artifacts",
    }


TECHNICAL_DELIVERABLE_RE = re.compile(
    r"技术(?:制作|分镜)|镜头表|逐镜(?:脚本|规格|分镜|清单)|shot\s*list|"
    r"technical\s*storyboard|production\s*worksheet|制作工作表|素材槽|"
    r"TN\s*[/+-]?\s*CG|资产矩阵|asset\s*matrix",
    re.IGNORECASE,
)
TECHNICAL_ACTION_RE = re.compile(
    r"制作|输出|需要|请给|展开|生成|整理|提供|也给我|给我|要|"
    r"create|deliver|build|provide|include",
    re.IGNORECASE,
)
TECHNICAL_NEGATION_RE = re.compile(
    r"不要|不展开|不需要|无需|不用|不做|别|禁止|勿|do\s+not|don't|without|exclude",
    re.IGNORECASE,
)


def requests_spatial_discussion(request: str) -> bool:
    """Identify a bounded staging/camera discussion without treating it as media execution.

    This remains a Studio craft path because a useful response may need a
    source-bound scene view.  It deliberately does not select a provider,
    create a second router, write scene truth, or authorize generation.
    """
    text = action_text(request)
    if has(
        text,
        r"(?:只|仅).{0,12}(?:修改|优化|精简|改写).{0,20}(?:提示词|prompt)|"
        r"(?:提示词|prompt).{0,20}(?:简洁|精简|别扩写|不要扩写|修改|优化)",
    ):
        return False
    # A whole-film/preproduction request may include blocking as one required
    # craft layer.  It must retain the broader deliverable rather than being
    # collapsed into a presentation-only staging discussion.
    if has(
        text,
        r"(?:完整|全套|全部|全片|整支).{0,32}(?:前期|广告片|品牌片|短片|故事|剧本|分镜|视频提示词|上传顺序)|"
        r"(?:故事|剧本).{0,24}(?:逐镜|分镜|视频提示词|上传顺序)|"
        r"(?:full|complete).{0,32}(?:preproduction|film|commercial|script|storyboard|upload)",
    ):
        return False
    spatial_subject = has(
        text,
        r"两人|二人|三人|多人|甲.{0,24}乙|乙.{0,24}甲|人物.{0,12}(?:对话|交接|遮挡|走位)|"
        r"(?:对话|交接|遮挡).{0,12}(?:人物|角色|两人|二人|三人)|"
        r"two\s+(?:people|characters)|multiple\s+characters",
    )
    spatial_intent = has(
        text,
        r"站位|走位|动线|空间关系|空间布局|俯视(?:图|布局)?|"
        r"正反打|反打|过肩|关系轴|轴线|机位|镜位|(?:绕|走到).{0,12}(?:桌|门|窗|墙|吧台)|"
        r"(?:桌|门|窗|墙|吧台).{0,12}(?:边|口|旁)|camera\s+(?:position|angle)|"
        r"blocking|staging|shot[ -]?reverse[ -]?shot",
    )
    discussion_action = has(
        text,
        r"看看|展示|讨论|安排|怎么(?:拍|摆|走)|如何(?:拍|摆|走)|"
        r"给我(?:看|一个).{0,16}(?:方案|示意)|show|discuss|plan|arrange",
    )
    return spatial_intent and (spatial_subject or discussion_action)


def explicit_technical_request(text: str) -> bool:
    """Require an affirmative technical-deliverable request in the same clause."""
    clauses = re.split(r"[。；;!?！？\n，,]", text)
    for clause in clauses:
        for match in TECHNICAL_DELIVERABLE_RE.finditer(clause):
            before = clause[max(0, match.start() - 24) : match.start()]
            after = clause[match.end() : match.end() + 24]
            if TECHNICAL_NEGATION_RE.search(before) or TECHNICAL_NEGATION_RE.search(after):
                continue
            if TECHNICAL_ACTION_RE.search(before) or TECHNICAL_ACTION_RE.search(after):
                return True
    return False


def classify_route(
    request: str,
    handoff: dict[str, Any] | None = None,
    *,
    project_root: Path | None = None,
    descriptor: dict[str, Any] | None = None,
    handoff_path: Path | None = None,
) -> tuple[str, list[str]]:
    if handoff is not None:
        from dircreative_adco_native_exchange import validate_handoff
        from dircreative_specialist_exchange_contract import valid_v2_handoff

        if not valid_v2_handoff(handoff):
            return "invalid_specialist_exchange", ["invalid_adco_handoff", "schema_validation_failed"]
        if project_root is None or descriptor is None:
            return "invalid_specialist_exchange", ["unverified_adco_handoff", "project_validation_required"]
        validation_failures = validate_handoff(
            project_root,
            handoff,
            descriptor,
            handoff_path=handoff_path,
        )
        if validation_failures:
            failure_codes = sorted({item.split(":", 1)[0] for item in validation_failures})
            return "invalid_specialist_exchange", [
                "invalid_adco_handoff",
                "project_validation_failed",
                *failure_codes,
            ]
        return "adco_specialist_exchange", ["validated_adco_v2_handoff", "inline_execution"]

    text = " ".join(request.split())
    actionable = action_text(request)
    asset_components = requested_asset_components(request)
    asset_design_target = any(asset_components.values())
    character_master_target = asset_components["identity_state"]
    maintenance_target = has(
        text,
        r"(?:DIRcreative\s+Skill\s*(?:本身)?|DIR\s*(?:的)?\s*SKILL\.md|DIR\s*安装器|"
        r"DIRcreative\s*(?:源码|源代码|仓库)|Paperrolling-DIRcreative-SKILL|source\s+repo)",
    )
    maintenance_action = has(text, r"维护|优化|审查|调试|重构|测试|评估|修改|maintain|review|debug|refactor|test|evaluate|modify")
    if maintenance_target and maintenance_action:
        return "source_maintenance", ["repository_maintenance", "skill_runtime_forbidden"]


    media_scope = classify_media_scope(request)["media_scope"]
    # A prohibition on a side effect must not replace the requested text work.
    # Historical denied/revoked approval records still follow the existing gate.
    side_effect_intent = " ".join(
        clause for clause in re.split(r"[。；;\n，,]", actionable)
        if not has(clause, r"(?:不要|不用|无需|不需要|禁止|别).{0,8}(?:真实生成|发给客户|客户交付|发送客户)")
    )
    pre_video_full_scope = media_scope == "scope_conflict" or has(
        actionable,
        r"(?:直到|完成|做到|走到).{0,16}(?:视频生成|生成视频)(?:之)?前.{0,24}(?:全部|全套|流程)|"
        r"(?:视频生成|生成视频)前.{0,20}(?:全部|全套|完整).{0,12}(?:技术)?流程",
    )
    connected_image_preproduction = media_scope == "pre_video_assets" and (
        pre_video_full_scope or explicit_action_match(
            actionable,
            r"(?:做|制作|创作|开发|完成|筹备).{0,32}(?:短片|动作片|广告片|品牌片|电影)|"
            r"(?:make|create|develop|prepare).{0,40}(?:film|commercial|movie)",
        )
    )

    if has(
        side_effect_intent,
        r"客户交付|客户可见|正式交付|发给客户|发送客户|client[- ]visible|"
        r"client delivery|send[- ]ready|send\s+to\s+(?:the\s+)?client",
    ):
        return "client_delivery", ["client_delivery_intent"]
    if not connected_image_preproduction and not asset_design_target and (has(
        side_effect_intent,
        r"真实生成|生成授权|授权生成|generation authorization|generation\s+authorized|"
        r"authorize (?:real )?generation",
    ) or (
        (generation_authorized(request) or denied_generation_followed_by_imperative(request))
        and not has(actionable, r"Prompt|提示词|方案|计划|plan")
    )):
        return "generation_authorization", ["real_generation_requires_authorization"]

    if asset_design_target:
        if character_master_target and not has(actionable, r"九宫格|九格|storyboard|nine[- ]grid") and not requests_whole_film_development(request):
            return "film_development", ["character_master_asset", "identity_state_contract_required"]
        return "film_development", ["asset_design_required"]

    # Study the media itself; prompt-only criticism stays on the existing route.
    study_action = explicit_action_match(
        actionable, r"拆解|蒸馏|拉片|深度分析|分析|distill|analy[sz]e|break\s+down"
    )
    study_media = has(text, r"视频|参考片|成片|video|clip|reference\s+film|\.(?:mp4|mov|mkv|webm|m4v|avi)\b|https?://(?:v\.douyin\.com|www\.douyin\.com/video/|(?:www\.)?youtube\.com/watch|youtu\.be/|(?:www\.)?vimeo\.com/|(?:www\.)?tiktok\.com/)")
    text_artifact_only = has(actionable, r"提示词|脚本|文案|台词|分镜|prompt|script|copy|storyboard") and not has(
        text, r"蒸馏|拉片|参考片|成片|https?://|\.(?:mp4|mov|mkv|webm|m4v|avi)\b"
    )
    if study_action and study_media and not text_artifact_only:
        return "video_distillation", ["reference_media_study", "evidence_before_inference"]

    seedance25_target = has(text, r"seedance\s*2(?:[._\s-]*5)|seedance25")
    seedance25_prompt_target = has(actionable, r"提示词|prompt")
    seedance25_source_scope = has(actionable, r"剧本|脚本|场次|场景|script|scene")
    seedance25_compile_action = has(
        actionable,
        r"写成|改成|做成|生成(?:成|为)?|转(?:换|成)|编译|制作(?:成)?|输出(?:为)?|"
        r"convert|compile|turn\s+.+\s+into",
    )
    if (
        seedance25_target
        and seedance25_prompt_target
        and seedance25_source_scope
        and seedance25_compile_action
    ):
        return "film_development", [
            "seedance25_formal_compile",
            "visual_baseline_required",
        ]

    explicit_sepia = has(text, r"\bSepia\b") and has(
        actionable,
        r"去\s*AI|AI\s*痕迹|人味|润色|改写|重构|重写|审查|评审|检查|诊断|写作|写|"
        r"humaniz|unslop|polish|rewrite|review|inspect|diagnos|refactor|recreate|write",
    )
    layered_humanization = explicit_sepia or has(
        actionable,
        r"(?:Sepia|深度|结构|篇章|全文|整篇|整份|整部).{0,36}"
        r"(?:去\s*AI|AI\s*痕迹|人味|humaniz|unslop|润色|改写|重构|重写|审查|评审|review|refactor|recreate)|"
        r"(?:去\s*AI|AI\s*痕迹|humaniz|unslop).{0,36}"
        r"(?:结构|篇章|全文|整篇|整份|整部|重构|重写)",
    )
    if layered_humanization:
        return "film_development", [
            "layered_humanization",
            "diagnosis_before_edit",
        ]

    concept_decision_resolved = explicit_action_match(
        actionable,
        r"(?:方向|冲突).{0,12}(?:已经解决|已解决|已选定|已经选定)|"
        r"(?:按|由).{0,12}(?:你的专业判断|你决定|你来定).{0,8}(?:选择|决定)?|"
        r"concept\s+conflict\s+(?:is\s+)?resolved",
    )
    if not concept_decision_resolved and has(
        actionable,
        r"方向(?:互不兼容|不可兼容|冲突)|不可兼容(?:的)?(?:创意)?方向|incompatible (?:creative )?directions?|material concept conflict",
    ):
        return "film_development", ["incompatible_creative_directions", "concept_lock_required"]

    if requests_spatial_discussion(request):
        return "film_development", [
            "bounded_spatial_discussion",
            "presentation_only_scene_view",
        ]

    bounded = has(
        actionable,
        r"第三句|一句|一段|单镜头|这个镜头|一个镜头|少量分镜|局部分镜|局部|"
        r"one sentence|one paragraph|single shot|this shot|few storyboards|bounded",
    )
    revision = has(actionable, r"修改|优化|调整|润色|改写|改短|缩短|精简|评审|补充|分析|改(?:得|成|为)|revise|rewrite|polish|adjust|review|improve|analy[sz]e")
    complete = pre_video_full_scope or has(actionable, r"完整|全套|多产物|概念\s*\+|故事\s*\+|脚本\s*\+\s*分镜|full|complete|multi[- ]artifact")
    broad_scope = has(
        actionable,
        r"(?:整个|整支|整部|全片|全部|全套|逐一|每个)\s*(?:[0-9]+\s*个?)?"
        r"(?:广告片|品牌片|短片|TVC|film|commercial|脚本|镜头|分镜)|"
        r"(?:这|共|全部)?\s*(?:[2-9]|[1-9][0-9]+)\s*(?:个\s*)?(?:镜头|分镜|镜)|"
        r"[0-9]+\s*秒\s*(?:广告片|品牌片|TVC|film|commercial)",
    )

    if revision and not broad_scope and (bounded or not complete):
        if has(actionable, r"Prompt|提示词"):
            return "prompt_revision", ["bounded_revision", "prompt_target"]
        if has(actionable, r"分镜|storyboard") and not has(actionable, r"脚本\s*\+\s*分镜"):
            return "storyboard_review", ["bounded_review", "storyboard_target"]
        if has(actionable, r"镜头|shot"):
            return "shot_optimization", ["bounded_revision", "shot_target"]
        if has(actionable, r"句|段|文案|脚本|copy|line|paragraph|script"):
            return "copy_revision", ["bounded_revision", "copy_target"]
        return "bounded_revision", ["bounded_revision"]

    if broad_scope or complete or has(actionable, r"广告片|品牌片|短片|film|commercial|故事|剧情|九宫格|九格|脚本|story|script"):
        return "film_development", ["multi_artifact_or_complete_creation"]
    return "bounded_revision", ["single_output_default"]


def classify_deliverable_layer(request: str, route: str) -> tuple[str | None, bool]:
    """Keep client narrative, frame content, and technical production as separate layers."""
    if route == "invalid_specialist_exchange":
        return None, False
    if route == "adco_specialist_exchange":
        return "bounded_specialist_output", False
    if route == "video_distillation":
        return "reference_analysis", False
    if route != "film_development":
        return "bounded_output", False

    text = action_text(request)
    assets = requested_asset_components(request)
    narrative_board = has(text, r"九宫格|九格(?:故事板|分镜)?|9\s*(?:宫格|格)|nine[- ]grid")
    if any(assets.values()) and not narrative_board and not requests_whole_film_development(request):
        return "technical_production", False
    if requests_spatial_discussion(request):
        return "spatial_discussion", False
    technical = explicit_technical_request(text)
    if technical:
        return "technical_production", True
    if has(text, r"九宫格|九格(?:故事板|分镜)?|9\s*(?:宫格|格)|nine[- ]grid"):
        return "narrative_storyboard", False
    if has(
        text,
        r"逐帧内容|逐格内容|每一帧(?:的)?(?:内容|storyline|故事线)|"
        r"frame[- ]by[- ]frame\s*content|View\s*[/+|]\s*Storyline",
    ):
        return "frame_content_spec", False
    compact_pages = has(text, r"一至两页|一到两页|一两页|1\s*(?:-|至|到)\s*2\s*页|两页|一页|1\s*页|单页")
    clauses = re.split(r"[。；;!?！？\n，,]", text)
    client_story_requested = any(explicit_action_match(
        clause, r"(?:客户可读|客户|提案).{0,12}(?:故事|故事线)|client[- ](?:readable\s+)?stor(?:y|ies)",
    ) for clause in clauses)
    story_only = any(explicit_action_match(
        clause, r"(?:只要|只写|只给|只输出|仅需|仅写|仅输出)\s*(?:纯)?(?:故事|故事线)|(?:story|narrative)[- ]only",
    ) for clause in clauses)
    additional_outputs = any(
        explicit_action_match(clause, r"分镜|资产|镜头表|提示词|storyboard|shot\s*list|assets?|prompts?")
        and has(clause, TECHNICAL_ACTION_RE.pattern)
        for clause in clauses
    )
    if not additional_outputs and (client_story_requested and (compact_pages or story_only)):
        return "client_story", False
    dual_story = has(text, r"双方向|两个方向|两种方向|两条方向|dual[- ]direction") and has(
        text, r"故事|故事线|story|客户|提案"
    )
    if dual_story and (compact_pages or has(text, r"讲清|客户可读|纯故事线")):
        return "client_story", False
    return "full_preproduction", True


def film_craft_stages(
    request: str,
    *,
    route: str,
    deliverable_layer: str | None,
    shot_matrix_allowed: bool,
    media_scope: str,
    story_context: str = "",
    motion_planning_required: bool = False,
) -> list[dict[str, Any]]:
    """Expose the existing stage handoffs without selecting or executing providers.

    These are deferred reads/selector inputs, not extra first-response reads.
    Revisit conditional craft against the developed script: a short brief cannot
    enumerate all later blocking, action or environment requirements.
    """
    if route != "film_development":
        return []
    assets = requested_asset_components(request)
    spatial_only = deliverable_layer == "spatial_discussion"
    if not shot_matrix_allowed and not any(assets.values()) and not spatial_only:
        return []
    # Current shot-card facts can inform craft even inside quotation marks.
    # They never enter route selection or the original-request authorization pass.
    text = action_text(request) + " " + story_context
    clauses = re.split(r"[。；;!?！？\n，,]", text)

    def requested(pattern: str) -> bool:
        return any(explicit_action_match(clause, pattern) for clause in clauses)

    action_required = requested(
        r"武侠|打斗|打戏|对打|搏斗|格斗|追逐|挥刀|格挡|刀剑交击|拳击|交接|递给|接住|动作(?:戏|片|短片)|"
        r"\b(?:wuxia|fight|combat|chase)\b|action\s+(?:film|scene|short)"
    )
    motion_required = action_required or motion_planning_required or requested(
        r"交接|递给|递向|接住|换手|绕过|穿过|跨越|翻越|撞击|躲避|走位变化|"
        r"黑白.*(?:分镜|草图|线稿)|动作草图|动势|人物移位|运镜标注|九宫格.*分镜|"
        r"\b(?:handoff|contact|dodge)\b|passes?\s+.+\s+to\b|moves?\s+around\b|"
        r"motion\s+board|annotated\s+storyboard"
    )
    spatial_required = motion_required or requested(
        r"两人|二人|三人|多人|反打|过肩|机位|走位|动线|遮挡|"
        r"blocking|staging|reverse[ -]?shot|multiple\s+characters"
    )
    effects_required = requested(
        r"环境(?:破碎|破坏)|爆裂|爆炸|碎裂|飞石|法术|异能|"
        r"\b(?:destruction|explosion|shattering|magic|vfx)\b"
    )

    def selection(scenario_id: str, **fields: Any) -> dict[str, Any]:
        return {
            "scenario_id": scenario_id,
            "mode": "studio",
            "route_id": "film_development",
            "media": "storyboard",
            "gaps": [],
            "needs_validation": False,
            "real_side_effect": False,
            **fields,
        }

    stages: list[dict[str, Any]] = []
    if shot_matrix_allowed:
        stages.append({
            "stage": "shot_design", "task_reference": "skills/dircreative/references/shot-development.md",
            "selection_intent": selection("technical_storyboard"), "status": "pending",
        })
    if action_required and (shot_matrix_allowed or spatial_only):
        stages.append({"stage": "action", "selection_intent": selection("action_choreography"), "status": "pending"})
    if effects_required and shot_matrix_allowed:
        stages.append({"stage": "environment_effects", "selection_intent": selection("vfx_design"), "status": "pending"})
    if (spatial_required or spatial_only) and not assets["camera_geography"] and (shot_matrix_allowed or spatial_only):
        stages.append({
            "stage": "camera_geography",
            "task_reference": "skills/dircreative/references/spatial-discussion.md",
            "selection_intent": selection("master_camera"),
            "status": "pending",
        })
    asset_gaps = {"identity_state": "character_continuity", "production_design": "production_design", "camera_geography": "camera_geography"}
    for pass_id, gap in asset_gaps.items():
        if assets[pass_id]:
            stages.append({
                "stage": pass_id,
                "task_reference": "skills/dircreative/references/character-master-sheet.md" if pass_id == "identity_state" else "skills/dircreative/references/asset-foundation-pass.md",
                "selection_intent": selection("asset_foundation", media="image_series", active_stage=pass_id,
                    asset_pass_id=pass_id, asset_pass_scope="initial_design", asset_pass_status="in_progress", gaps=[gap]),
                "status": "pending",
            })
    if assets["mechanical_transformation"] or (shot_matrix_allowed and requested(r"机械.{0,20}(?:展开|变形)|铰链|锁止")):
        stages.append({"stage": "mechanical_transformation", "selection_intent": selection("mechanical_transformation"), "status": "pending"})
    if assets["reuse"]:
        stages.append({"stage": "asset_readback", "task_reference": "skills/dircreative/references/image-execution.md",
            "selection_intent": selection("constraint_input", media="image_series"), "status": "pending"})
    if any(assets[pass_id] for pass_id in asset_gaps):
        stages.append({"stage": "asset_compile", "task_reference": "skills/dircreative/references/visual-asset-to-jingzao.md",
            "selection_intent": selection("visual_asset_compile", media="image_series"), "status": "pending"})
    full_frames = shot_matrix_allowed and (deliverable_layer == "full_preproduction" or media_scope == "pre_video_assets")
    if full_frames:
        stages.append({"stage": "panel_coverage", "task_reference": "skills/dircreative/references/storyboard-coverage.md", "selection_intent": selection("technical_storyboard"), "status": "pending"})
        if motion_required:
            stages.append({
                "stage": "motion_board",
                "task_reference": "skills/dircreative/references/storyboard-motion-planning.md",
                "selection_intent": selection("cinematic_storyboard_frames", downstream_use="rough_planning", active_stage="motion_board"),
                "status": "pending",
            })
        stages.append({
                "stage": "frame_compile",
                "task_reference": "skills/dircreative/references/storyboard-frame-to-jingzao.md",
                "selection_intent": selection("cinematic_storyboard_frames", downstream_use="full_preproduction"),
                "status": "pending",
            })
    return stages


def route_request(
    request: str,
    handoff: dict[str, Any] | None = None,
    *,
    project_root: Path | None = None,
    descriptor: dict[str, Any] | None = None,
    handoff_path: Path | None = None,
) -> dict[str, Any]:
    policy = load_policy()
    media_scope = classify_media_scope(request)
    route, reason_codes = classify_route(
        request,
        handoff,
        project_root=project_root,
        descriptor=descriptor,
        handoff_path=handoff_path,
    )
    if route == "invalid_specialist_exchange":
        return {
            "execution_context": None,
            "mode": None,
            "route": route,
            "required_files": [],
            "optional_files": [],
            "external_user_gate": None,
            "action": "stop_skill_runtime",
            "first_response_contract": "not_applicable",
            "reuse_known_brief": False,
            "state_persistence": "none",
            "threads_allowed": False,
            "collaboration": collaboration_contract(request, route, "stop_skill_runtime", policy),
            "full_receipt_required": False,
            "deliverable_layer": None,
            "shot_matrix_allowed": False,
            **media_scope,
            "reason_codes": [*reason_codes, "skill_runtime_forbidden"],
        }
    config = policy["routes"][route]
    execution_context = (
        "orchestrated_worker"
        if route == "adco_specialist_exchange"
        else "repository_maintenance"
        if route == "source_maintenance"
        else "standalone_chat"
    )
    external_user_gate = config["external_user_gate"]
    if route == "film_development" and "incompatible_creative_directions" not in reason_codes:
        external_user_gate = None
        reason_codes = [*reason_codes, "no_material_blocker"]
    if route == "generation_authorization" and generation_authorized(request):
        external_user_gate = None
        reason_codes = [*reason_codes, "authorization_satisfied_by_current_request"]
    if route == "client_delivery" and client_delivery_authorized(request):
        external_user_gate = None
        reason_codes = [*reason_codes, "approval_satisfied_by_current_request"]
    action = (
        "stop_skill_runtime"
        if route == "source_maintenance"
        else "stop_for_external_gate"
        if external_user_gate
        else "continue"
    )
    if media_scope["media_scope"] == "scope_conflict":
        action = "stop_for_scope_conflict"
        reason_codes = [*reason_codes, "forwarded_media_scope_conflict"]
    persistence = policy["interaction_contract"]["state_persistence"][config["mode"]]
    deliverable_layer, shot_matrix_allowed = classify_deliverable_layer(request, route)
    required_files = list(config["required_files"])
    if "identity_state_contract_required" in reason_codes:
        required_files = ["skills/dircreative/references/character-master-sheet.md"]
    elif deliverable_layer == "spatial_discussion":
        required_files = ["skills/dircreative/references/spatial-discussion.md"]
    elif deliverable_layer == "client_story":
        required_files = ["skills/dircreative/references/client-story.md"]
    collaboration = collaboration_contract(request, route, action, policy)
    return {
        "execution_context": execution_context,
        "mode": config["mode"],
        "route": route,
        "required_files": required_files,
        "optional_files": config["optional_files"],
        "external_user_gate": external_user_gate,
        "action": action,
        "first_response_contract": (
            "not_applicable"
            if action == "stop_skill_runtime"
            else "scope_conflict_report"
            if action == "stop_for_scope_conflict"
            else "gate_question"
            if action == "stop_for_external_gate"
            else "useful_artifact_first"
        ),
        "reuse_known_brief": True,
        "state_persistence": persistence,
        "threads_allowed": collaboration["threads_allowed"],
        "collaboration": collaboration,
        "full_receipt_required": config["full_receipt_required"],
        "deliverable_layer": deliverable_layer,
        "shot_matrix_allowed": shot_matrix_allowed,
        "craft_stages": film_craft_stages(
            request,
            route=route,
            deliverable_layer=deliverable_layer,
            shot_matrix_allowed=shot_matrix_allowed,
            media_scope=media_scope["media_scope"],
        ),
        "spatial_discussion": {
            "requested": deliverable_layer == "spatial_discussion",
            "interaction": "presentation_only" if deliverable_layer == "spatial_discussion" else None,
            "host_visualize_contract": "read_current_host_contract" if deliverable_layer == "spatial_discussion" else None,
            "scene_state_owner": "existing_scene_shot_artifacts" if deliverable_layer == "spatial_discussion" else None,
            "adoption": "explicit_user_intent_required" if deliverable_layer == "spatial_discussion" else None,
            "generation": "requires_existing_generation_authorization" if deliverable_layer == "spatial_discussion" else None,
        },
        **media_scope,
        "reason_codes": reason_codes,
    }


def self_test() -> list[str]:
    failures: list[str] = []
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        result = route_request(case["input"])
        for field in (
            "mode",
            "route",
            "required_files",
            "external_user_gate",
            "action",
            "first_response_contract",
            "state_persistence",
            "deliverable_layer",
            "shot_matrix_allowed",
            "media_scope",
            "image_generation_authorized",
            "video_generation_authorized",
            "minimum_evidence",
        ):
            if field not in case:
                continue
            if result[field] != case[field]:
                failures.append(f"{case['id']}: {field}={result[field]} expected={case[field]}")
        if case["id"] == "sepia_explicit_inspect_article" and "layered_humanization" not in result["reason_codes"]:
            failures.append("explicit Sepia inspection did not activate layered diagnosis")
        if case["id"] == "spear_story_is_not_sepia_alias" and "layered_humanization" in result["reason_codes"]:
            failures.append("ordinary English spear was treated as the Sepia provider")
    handoff_path = ROOT / "tests/fixtures/activation-policy/valid-adco-v2-handoff.json"
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    descriptor = json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))
    unverified = route_request("", handoff)
    if unverified["route"] != "invalid_specialist_exchange" or "project_validation_required" not in unverified["reason_codes"]:
        failures.append(f"schema-only ADCO handoff did not fail closed: {unverified}")
    with tempfile.TemporaryDirectory(prefix="dircreative-route-adco-") as raw:
        from dircreative_adco_native_exchange import register_v2_fixture_handoff

        project = Path(raw)
        validated_handoff = copy.deepcopy(handoff)
        brief_path = project / str(validated_handoff["brief_snapshot"])
        brief_path.parent.mkdir(parents=True, exist_ok=True)
        brief_path.write_text("Evidence-bound routing fixture.\n", encoding="utf-8")
        validated_handoff["locked_decisions"][0]["sha256"] = hashlib.sha256(
            brief_path.read_bytes()
        ).hexdigest()
        validated_handoff_path = project / "exchange/v2-handoff.json"
        validated_handoff_path.parent.mkdir(parents=True, exist_ok=True)
        validated_handoff_path.write_text(
            json.dumps(validated_handoff, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        output_parent = Path(str(validated_handoff["requested_outputs"][0]["path_root"])).parent
        register_v2_fixture_handoff(
            project,
            validated_handoff,
            validated_handoff_path,
            descriptor,
            receipt_path=(output_parent / "receipt.json").as_posix(),
        )
        result = route_request(
            "",
            validated_handoff,
            project_root=project,
            descriptor=descriptor,
            handoff_path=validated_handoff_path,
        )
        if result["execution_context"] != "orchestrated_worker" or result["route"] != "adco_specialist_exchange":
            failures.append(f"valid ADCO handoff route mismatch: {result}")
        invalid = dict(validated_handoff, execution_mode="codex_thread")
        invalid_shapes = [
            invalid,
            dict(validated_handoff, requested_outputs=[]),
            dict(validated_handoff, locked_decisions=[1]),
            dict(validated_handoff, quality_targets=[""]),
            dict(validated_handoff, requested_outputs=[validated_handoff["requested_outputs"][0]] * 2),
            dict(
                validated_handoff,
                requested_outputs=[
                    validated_handoff["requested_outputs"][0],
                    {**validated_handoff["requested_outputs"][0], "output_id": "OUT-02"},
                ],
            ),
        ]
        for index, invalid_shape in enumerate(invalid_shapes, start=1):
            invalid_result = route_request(
                "",
                invalid_shape,
                project_root=project,
                descriptor=descriptor,
                handoff_path=validated_handoff_path,
            )
            if (
                invalid_result["execution_context"] is not None
                or invalid_result["route"] != "invalid_specialist_exchange"
                or invalid_result["action"] != "stop_skill_runtime"
            ):
                failures.append(f"invalid ADCO handoff {index} did not fail closed: {invalid_result}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve one DIRcreative v2 route as stable JSON.")
    parser.add_argument("request", nargs="?", default="", help="User request text.")
    parser.add_argument("--handoff", type=Path, help="Specialist Exchange handoff JSON.")
    parser.add_argument("--project-root", type=Path, help="Project root required for a real handoff.")
    parser.add_argument("--descriptor", type=Path, default=DESCRIPTOR_PATH)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        failures = self_test()
        if failures:
            print("DIRCREATIVE_ROUTE_SELF_TEST: FAIL")
            for failure in failures:
                print(f"- {failure}")
            return 1
        print("DIRCREATIVE_ROUTE_SELF_TEST: PASS")
        return 0
    handoff = json.loads(args.handoff.read_text(encoding="utf-8")) if args.handoff else None
    descriptor = json.loads(args.descriptor.read_text(encoding="utf-8")) if handoff and args.project_root else None
    project_root = args.project_root.expanduser().resolve() if args.project_root else None
    print(
        json.dumps(
            route_request(
                args.request,
                handoff,
                project_root=project_root,
                descriptor=descriptor,
                handoff_path=args.handoff.expanduser().resolve() if args.handoff else None,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
