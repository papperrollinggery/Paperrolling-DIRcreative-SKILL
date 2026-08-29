from __future__ import annotations

from typing import Any

from .base import AdapterContract, PromptAdapter, PromptBudget


class SeedanceAdapter(PromptAdapter):
    CONTRACT = AdapterContract(
        adapter="seedance",
        reference_count="0-50 total; exact typed limits remain capability-card scoped",
        reference_syntax="explicit @Image/@Video/@Audio numbered slots",
        maximum_references=50,
        reference_slot_pattern=r"@(Image|Video|Audio) [1-9][0-9]*",
        timeline_syntax="Timeline lines as SS.ss-SS.ss",
        multi_shot_support="explicit timeline multi-shot",
        allowed_unit_lengths_sec=(),
        minimum_unit_sec=None,
        maximum_unit_sec=30,
        camera_handling="full motivated camera path and focus",
        audio_handling="native or reference audio when exact card permits",
        look_handling="full lighting optics atmosphere and grade",
        negative_handling="role-bound anti-misread clauses; no generic negative dump",
        unsupported_fields=("unbound_reference_slot", "implicit_board_role"),
        prompt_budget=PromptBudget(12000, ("remove_repeated_look", "compress_continuity", "compress_secondary_environment")),
        native_audio_allowed=True,
    )

    def reference_label(self, item: dict[str, Any], index: int) -> str:
        return str(item["platform_slot"])

    def allowed_surface_slots(self, payload: dict[str, Any]) -> set[str]:
        return {
            str(item["platform_slot"])
            for item in payload["references"]
            if item["attached_to_run"]
        }
