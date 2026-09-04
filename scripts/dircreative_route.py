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
        before = text[max(0, match.start() - 36) : match.start()]
        after = text[match.end() : match.end() + 48]
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
    character_master_target = has(
        actionable,
        r"人物母版|角色母版|人物设定(?:图|资产)|角色设定(?:图|资产)|"
        r"character\s+(?:master|turnaround|model)\s+(?:sheet|asset)",
    )
    maintenance_target = has(
        text,
        r"(?:DIRcreative\s+Skill\s*(?:本身)?|DIR\s*(?:的)?\s*SKILL\.md|DIR\s*安装器|"
        r"DIRcreative\s*(?:源码|源代码|仓库)|Paperrolling-DIRcreative-SKILL|source\s+repo)",
    )
    maintenance_action = has(text, r"维护|优化|审查|调试|重构|测试|评估|修改|maintain|review|debug|refactor|test|evaluate|modify")
    if maintenance_target and maintenance_action:
        return "source_maintenance", ["repository_maintenance", "skill_runtime_forbidden"]


    media_scope = classify_media_scope(request)["media_scope"]
    pre_video_full_scope = media_scope == "scope_conflict" or has(
        actionable,
        r"(?:直到|完成|做到|走到).{0,16}(?:视频生成|生成视频)(?:之)?前.{0,24}(?:全部|全套|流程)|"
        r"(?:视频生成|生成视频)前.{0,20}(?:全部|全套|完整).{0,12}(?:技术)?流程",
    )

    if has(
        actionable,
        r"客户交付|客户可见|正式交付|发给客户|发送客户|client[- ]visible|"
        r"client delivery|send[- ]ready|send\s+to\s+(?:the\s+)?client",
    ):
        return "client_delivery", ["client_delivery_intent"]
    if has(
        actionable,
        r"真实生成|生成授权|授权生成|generation authorization|generation\s+authorized|"
        r"authorize (?:real )?generation",
    ) or (
        (generation_authorized(request) or denied_generation_followed_by_imperative(request))
        and not has(actionable, r"Prompt|提示词|方案|计划|plan")
    ):
        return "generation_authorization", ["real_generation_requires_authorization"]

    if character_master_target:
        return "film_development", [
            "character_master_asset",
            "identity_state_contract_required",
        ]

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

    if has(
        actionable,
        r"方向(?:互不兼容|不可兼容|冲突)|不可兼容(?:的)?(?:创意)?方向|incompatible (?:creative )?directions?|material concept conflict",
    ):
        return "film_development", ["incompatible_creative_directions", "concept_lock_required"]

    bounded = has(
        actionable,
        r"第三句|一句|一段|单镜头|这个镜头|一个镜头|少量分镜|局部分镜|局部|"
        r"one sentence|one paragraph|single shot|this shot|few storyboards|bounded",
    )
    revision = has(actionable, r"修改|优化|调整|润色|改写|评审|补充|分析|改(?:得|成|为)|revise|rewrite|polish|adjust|review|improve|analy[sz]e")
    complete = pre_video_full_scope or has(actionable, r"完整|全套|多产物|概念\s*\+|故事\s*\+|脚本\s*\+\s*分镜|full|complete|multi[- ]artifact")
    broad_scope = has(
        actionable,
        r"(?:整个|整支|整部|全片|全部|全套|逐一|每个)\s*(?:[0-9]+\s*个?)?"
        r"(?:广告片|品牌片|短片|TVC|film|commercial|脚本|镜头|分镜)|"
        r"(?:这|共|全部)?\s*[0-9]+\s*(?:个\s*)?(?:镜头|分镜|镜)|"
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

    if broad_scope or complete or has(actionable, r"广告片|品牌片|短片|film|commercial|故事|脚本|story|script"):
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
    if has(
        text,
        r"人物母版|角色母版|人物设定(?:图|资产)|角色设定(?:图|资产)|"
        r"character\s+(?:master|turnaround|model)\s+(?:sheet|asset)",
    ):
        return "technical_production", False
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
    compact_pages = has(text, r"一至两页|一到两页|一两页|1\s*(?:-|至|到)\s*2\s*页|两页")
    dual_story = has(text, r"双方向|两个方向|两种方向|两条方向|dual[- ]direction") and has(
        text, r"故事|故事线|story|客户|提案"
    )
    if dual_story and (compact_pages or has(text, r"讲清|客户可读|纯故事线")):
        return "client_story", False
    return "full_preproduction", True


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
        "threads_allowed": config["threads_allowed"],
        "full_receipt_required": config["full_receipt_required"],
        "deliverable_layer": deliverable_layer,
        "shot_matrix_allowed": shot_matrix_allowed,
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
