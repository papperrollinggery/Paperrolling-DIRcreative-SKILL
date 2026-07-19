from .base import AdapterContract, PromptAdapter, PromptBudget


class GenericAdapter(PromptAdapter):
    CONTRACT = AdapterContract(
        adapter="generic",
        reference_count="0-4 portable attached references",
        reference_syntax="ordered generic attached references without provider tokens",
        maximum_references=4,
        reference_slot_pattern=None,
        timeline_syntax="Timeline lines as SS.ss-SS.ss",
        multi_shot_support="portable explicit timeline; provider execution remains unverified",
        allowed_unit_lengths_sec=(),
        minimum_unit_sec=1,
        maximum_unit_sec=20,
        camera_handling="portable camera path and focus language",
        audio_handling="post-production unless resolved capability proves native audio",
        look_handling="portable full look block",
        negative_handling="portable positive constraints and anti-misread clauses",
        unsupported_fields=("provider_specific_parameter", "implicit_execution_claim"),
        prompt_budget=PromptBudget(10000, ("compress_repeated_continuity", "compress_look", "compress_secondary_environment")),
        native_audio_allowed=False,
    )
