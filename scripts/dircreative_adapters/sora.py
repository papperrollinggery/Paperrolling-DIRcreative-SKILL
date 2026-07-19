from .base import AdapterContract, PromptAdapter, PromptBudget


class SoraAdapter(PromptAdapter):
    CONTRACT = AdapterContract(
        adapter="sora",
        reference_count="0-1 first-frame image for this compiler route",
        reference_syntax="one attached first-frame image without @ slot tokens",
        maximum_references=1,
        reference_slot_pattern=None,
        timeline_syntax="Timeline lines as SS.ss-SS.ss",
        multi_shot_support="timestamped storyboard-style prompt sequence",
        allowed_unit_lengths_sec=(4, 8, 12, 16, 20),
        minimum_unit_sec=None,
        maximum_unit_sec=None,
        camera_handling="shot-by-shot camera, composition, and motivated movement",
        audio_handling="native prompt audio when requested; post-production remains valid",
        look_handling="full cinematic look block",
        negative_handling="positive exclusions and continuity constraints",
        unsupported_fields=("human_likeness_character_without_policy", "multiple_first_frame_images"),
        prompt_budget=PromptBudget(10000, ("compress_repeated_continuity", "compress_look", "compress_secondary_action")),
        native_audio_allowed=True,
    )

    def reference_label(self, item: dict[str, object], index: int) -> str:
        return "The attached first-frame image"
