#!/usr/bin/env python3
from __future__ import annotations

from dircreative_validation_harness import Check, add_check, read, require_terms


def main() -> int:
    checks: list[Check] = []

    quality_doc = "docs/film-preproduction/film-commercial-quality-standard.md"
    professional_voice_doc = "docs/film-preproduction/professional-agent-voice-standard.md"
    director_room = "\n".join(
        [
            read("docs/film-preproduction/director-room-council-protocol.md"),
            read("docs/film-preproduction/customer-visible-production-gates.md"),
            read("examples/live-user-sim-noodle/02-director-room-notes.md"),
            read("examples/complete-idea-segmentation-test/02-director-room-notes.md"),
        ]
    )
    commercial_evidence = "\n".join(
        [
            read("examples/product-ad-raincoat/01-idea-intake.md"),
            read("examples/product-ad-raincoat/02-director-room-notes.md"),
            read("examples/product-ad-raincoat/05-ad-structure.md"),
            read("examples/product-ad-raincoat/06-shot-list.yaml"),
            read("examples/live-user-sim-noodle/01-idea-intake.md"),
            read("examples/live-user-sim-noodle/07-shot-list.yaml"),
            read("examples/goal-mode-autorun-commercial-cp-test/01-chat-transcript.md"),
        ]
    )
    qa_docs = "\n".join(
        [
            read("docs/film-preproduction/qa/failure-taxonomy.yaml"),
            read("docs/film-preproduction/qa/retry-rules.md"),
            read("docs/film-preproduction/production-demo-retrospective.md"),
        ]
    )
    humanized_copy_wiring = "\n".join(
        [
            read("skills/dircreative/SKILL.md"),
            read("skills/dircreative/routes/fast-task.md"),
            read("skills/dircreative/routes/studio-development.md"),
            read("skills/dircreative/routes/delivery-audit.md"),
            read("docs/film-preproduction/chat-co-creation-interface.md"),
            read(professional_voice_doc),
        ]
    )

    add_check(
        checks,
        "film and commercial quality standard exists",
        quality_doc,
        lambda: require_terms(
            read(quality_doc),
            [
                "Film-Grade Dimensions",
                "Commercial-Grade Dimensions",
                "story_conflict",
                "emotional_turn",
                "business_objective",
                "audience_context",
                "product_proof",
                "brand_assets",
                "product_lock",
                "human_strategy",
                "delivery_priority",
                "QUALITY_AUDIT: PASS",
            ],
            quality_doc,
        ),
    )
    add_check(
        checks,
        "director-room exposes film and commercial tradeoff",
        "director-room docs and fixtures",
        lambda: require_terms(
            director_room,
            [
                "producer",
                "creative_director",
                "director",
                "cinematographer",
                "production_designer",
                "editor",
                "model_prompt_engineer",
                "continuity_qa",
                "disagreement",
                "产品",
                "商业",
            ],
            "director-room tradeoff evidence",
        ),
    )
    add_check(
        checks,
        "commercial proof and product safeguards are present",
        "product fixtures and autorun transcript",
        lambda: require_terms(
            commercial_evidence,
            [
                "commercial_product_film",
                "product",
                "benefit",
                "proof",
                "PRODUCT IDENTITY REFERENCE",
                "business_objective",
                "audience_context",
                "product_proof",
                "brand_assets",
                "product_lock",
                "human_strategy",
                "delivery_priority",
            ],
            "commercial quality evidence",
            case_sensitive=False,
        ),
    )
    add_check(
        checks,
        "quality failure ids have retry surface",
        "failure taxonomy and retry rules",
        lambda: require_terms(
            qa_docs + "\n" + read(quality_doc),
            [
                "weak_story_idea",
                "script_depth_insufficient",
                "product_benefit_not_visible",
                "storyboard_information_density_too_low",
                "generated_candidate_locked_without_self_qa",
                "creative_production_widget_used_as_truth",
                "goal_autorun_claimed_live_acceptance",
                "product proof",
                "smallest artifact",
            ],
            "quality failure and retry evidence",
            case_sensitive=False,
        ),
    )
    add_check(
        checks,
        "quality audit is wired into validation text",
        "scripts/validate_project.py + release gate",
        lambda: require_terms(
            read("scripts/validate_project.py") + "\n" + read("scripts/dircreative_release_gate.py"),
            [
                "dircreative_quality_audit.py",
                "QUALITY_AUDIT: PASS",
            ],
            "quality wiring evidence",
        ),
    )
    add_check(
        checks,
        "quality audit does not close goal",
        "live acceptance boundary docs",
        lambda: require_terms(
            read("docs/film-preproduction/live-user-acceptance-gate.md")
            + "\n"
            + read("docs/film-preproduction/current-project-progress.md"),
            [
                "real user acceptance",
                "OBJECTIVE_COMPLETE: NO",
                "Creative Production widgets",
                "Goal autorun dry-runs",
            ],
            "live acceptance boundary docs",
        ),
    )
    add_check(
        checks,
        "humanized copy gate covers user-visible outputs",
        professional_voice_doc,
        lambda: require_terms(
            read(professional_voice_doc),
            [
                "Humanized Copy Requirements",
                "humanizer",
                "humanizer-zh",
                "user-visible output standard",
                "Chinese creative directions",
                "Chinese production plans",
                "Chinese stage summaries",
                "English prompt handoff text",
                "Required output self-check before delivery",
                "Remove chatbot pleasantries",
                "Remove inflated significance language",
                "Remove formulaic structures",
                "Remove fake-candid openers",
                "Remove em dashes and en dashes",
                "Replace vague praise",
                "forced three-part lists",
                "generic positive closers",
                "Certainly",
                "Here is",
                "let me know",
                "不仅仅是...而是...",
                "标志着",
                "彰显",
                "vibrant",
                "pivotal",
                "showcase",
                "cinematic",
                "masterpiece",
                "concrete camera, blocking, lighting, material, story, product, or model-risk information",
            ],
            professional_voice_doc,
        ),
    )
    add_check(
        checks,
        "humanized copy gate is wired into skill and chat surface",
        "skills/dircreative/SKILL.md + chat co-creation interface",
        lambda: require_terms(
            humanized_copy_wiring,
            [
                "Before user-visible creative output",
                "professional-agent-voice-standard.md",
                "humanizer check",
                "humanizer / humanizer-zh diagnostic review",
                "Frontstage Copy Hygiene",
                "Every visible gate must follow `docs/film-preproduction/professional-agent-voice-standard.md` and run a humanizer pass",
                "The point is not to sound friendlier",
                "Prompt-only handoffs need an extra boundary",
                "Do not frame a prompt-only handoff as a finished creative win",
            ],
            "humanized copy wiring evidence",
        ),
    )

    print("DIRcreative Quality Audit")
    print("=" * 72)
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.label}")
        print(f"       evidence: {check.evidence}")
    failures = [check for check in checks if not check.ok]
    if failures:
        print("QUALITY_AUDIT: FAIL")
        return 1
    print("film_grade_ready: true")
    print("commercial_grade_ready: true")
    print("humanized_copy_ready: true")
    print("live_acceptance_required: true")
    print("QUALITY_AUDIT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
