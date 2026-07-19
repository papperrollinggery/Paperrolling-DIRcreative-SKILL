from .base import AdapterContract, PromptAdapter, PromptBudget


class KlingAdapter(PromptAdapter):
    CONTRACT = AdapterContract(
        adapter="kling",
        reference_count="0-4 direct element/reference images",
        reference_syntax="ordered attached reference images with element roles",
        maximum_references=4,
        reference_slot_pattern=None,
        timeline_syntax="Timeline lines as SS.ss-SS.ss",
        multi_shot_support="native multi-shot with explicit shot boundaries",
        allowed_unit_lengths_sec=(),
        minimum_unit_sec=3,
        maximum_unit_sec=15,
        camera_handling="per-shot camera movement separated from subject action",
        audio_handling="native synchronized audio and element voice binding when requested",
        look_handling="full render look",
        negative_handling="element identity and role anti-misread clauses",
        unsupported_fields=("implicit_element_owner", "more_than_four_element_references"),
        prompt_budget=PromptBudget(12000, ("compress_repeated_identity", "compress_look", "compress_secondary_environment")),
        native_audio_allowed=True,
    )
