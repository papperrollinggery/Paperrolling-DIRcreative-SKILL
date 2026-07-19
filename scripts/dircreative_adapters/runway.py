from .base import AdapterContract, PromptAdapter, PromptBudget


class RunwayAdapter(PromptAdapter):
    CONTRACT = AdapterContract(
        adapter="runway",
        reference_count="0-1 direct input image",
        reference_syntax="one input image anchor without internal slot tokens",
        maximum_references=1,
        reference_slot_pattern=None,
        timeline_syntax="Timeline lines as SS.ss-SS.ss",
        multi_shot_support="prompt-sequenced motion within one generation unit",
        allowed_unit_lengths_sec=(),
        minimum_unit_sec=2,
        maximum_unit_sec=10,
        camera_handling="motion-first camera and subject instructions",
        audio_handling="post-production only for the registered Gen-4.5 card",
        look_handling="omit standalone look block; inherit from input and motion language",
        negative_handling="state positive motion constraints; no negative-prompt block",
        unsupported_fields=("native_audio", "multiple_direct_images", "standalone_look_block"),
        prompt_budget=PromptBudget(10000, ("remove_repeated_look", "compress_static_identity", "compress_secondary_environment")),
        native_audio_allowed=False,
    )

    def reference_label(self, item: dict[str, object], index: int) -> str:
        return "The input image"

    def subject_heading(self) -> str:
        return "Motion subjects:"

    def include_look(self) -> bool:
        return False
