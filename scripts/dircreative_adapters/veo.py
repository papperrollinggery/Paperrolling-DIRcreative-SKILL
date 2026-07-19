from .base import AdapterContract, PromptAdapter, PromptBudget


class VeoAdapter(PromptAdapter):
    CONTRACT = AdapterContract(
        adapter="veo",
        reference_count="0-3 asset reference images on the registered stable route",
        reference_syntax="ordered asset images; first/last roles remain explicit in capability binding",
        maximum_references=3,
        reference_slot_pattern=None,
        timeline_syntax="Timeline lines as SS.ss-SS.ss",
        multi_shot_support="timeline sequence constrained by exact endpoint duration",
        allowed_unit_lengths_sec=(4, 6, 8),
        minimum_unit_sec=None,
        maximum_unit_sec=None,
        camera_handling="explicit subject motion, camera path, focus, and composition",
        audio_handling="post-production on stable card until exact native parameter is verified",
        look_handling="full lighting optics atmosphere and grade",
        negative_handling="positive artifact and continuity exclusions",
        unsupported_fields=("unverified_native_audio_parameter", "ten_second_unit"),
        prompt_budget=PromptBudget(10000, ("compress_repeated_reference_roles", "compress_look", "compress_secondary_environment")),
        native_audio_allowed=False,
    )
