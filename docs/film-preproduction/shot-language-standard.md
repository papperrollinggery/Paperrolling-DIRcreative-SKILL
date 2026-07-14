# Shot Language Standard

Verified: 2026-05-16

Purpose: prevent DIRcreative from outputting generic, low-value shot descriptions.

## Core Rule

A DIRcreative shot list is a production-facing shot card, not a story summary.

Every shot must tell a director, DP, editor, image prompt compiler, and video model adapter exactly what must be seen, how the camera behaves, how the subject moves, what continuity is locked, and which details are unsafe to leave implicit.

## Professional Shot Card

Each shot must include these fields before the shot can be approved:

| Field | Requirement |
| --- | --- |
| `shot_id` | Stable ID used by storyboard, prompt, and video manifests. |
| `timecode` | Start-end time, not only duration. |
| `duration` | Seconds. |
| `story_beat` | What changes in story, emotion, or information. |
| `narrative_purpose` | Why this shot exists in the edit. |
| `shot_type` | Functional type: establishing, insert, macro proof, reaction, transition, hero packshot, etc. |
| `shot_size` | Professional size term such as WS, MS, MCU, CU, ECU, insert, or packshot. |
| `camera_angle` | Viewpoint with physical relation to subject. |
| `lens` | Focal length or lens family. |
| `lens_reason` | Why this lens supports the shot. |
| `camera_support` | Tripod, handheld, slider, dolly, vehicle mount, crane, drone, locked-off, etc. |
| `camera_motion` | One motivated camera move, with start and end target. |
| `focus` | Focus target, depth of field, rack focus, or locked focus. |
| `composition` | Foreground, midground, background, negative space, product/face placement, readable text zone. |
| `subject_action` | One primary action that can be generated clearly. |
| `blocking` | Start position, end position, path, eyeline, screen direction, and axis note. |
| `scene` | Location plus foreground, midground, background, weather/environment, and lighting. |
| `continuity` | Character, prop, wardrobe, product state, lighting, and state locks. |
| `audio` | Dialogue, VO, ambience, SFX, foley, music, and silence policy. |
| `transition_in` | How the shot enters. |
| `transition_out` | How the shot exits. |
| `model_notes` | Seedance, Kling, Runway, and Veo translation notes. |

## Forbidden Weak Output

Do not approve a shot if it only says:

- `slow push in`
- `cinematic close-up`
- `worker drinks`
- `warm lighting`
- `office sound`
- `product hero shot`
- `camera follows`

Those phrases can appear only inside a complete shot card that defines subject movement, camera path, depth layers, continuity locks, audio, and model translation.

## Chat Preview Format

In chat, show enough of the shot card for the user to judge the work without opening files:

```text
阶段: 分镜头确认
智能体创作内容:
S01 00:00-00:03 | Hook / MS -> CU insert | 35mm then 85mm macro
- 叙事任务: <story_beat + narrative_purpose>
- 机位/镜头: <camera_angle + lens + camera_support + camera_motion + focus>
- 主体调度: <start/end/path/eyeline/screen_direction/axis>
- 构图层次: <foreground/midground/background/lighting/readable zone>
- 声音剪辑: <ambience/SFX/music/silence/cut point>
- 模型风险: <Seedance/Kling/Runway/Veo risk or split rule>

用户确认点:
这个分镜结构是否通过？通过后我继续做视觉 bible 和参考图方案。
```

The chat explanation must include professional reasoning, not only field values. Explain why the shot count, lens/motion choice, and cut rhythm fit the channel and duration.

## Dedicated Storyboard Page

Every project that reaches reference image planning needs one dedicated professional storyboard/motion page unless the user explicitly requests script-only output.

Required page role:

```text
PROFESSIONAL STORYBOARD + MOTION MAP / 详细分镜头+镜头运动图 / PLANNING ONLY
```

This page is the core shot-review artifact. It is not a mood board, style board, or simple image strip.

Each shot cell on the page must include:

| Cell Item | Requirement |
| --- | --- |
| Shot ID | Stable ID such as `S01` or `FRC01`. |
| Duration | Exact timecode and seconds. |
| Shot Image | One readable frame region or sketch/still slot representing the shot. |
| Frame Description | Detailed screen content: who/what appears, action state, foreground/midground/background, and story information. |
| Shot Size | WS, MS, MCU, CU, ECU, insert, packshot, or other professional term. |
| Focal Length | Lens/focal length or equivalent visual compression note. |
| Camera Position | Angle, height, axis relation, and distance from subject. |
| Camera Movement | Start target, end target, support, movement speed, and motivation. |
| Subject Blocking | Character/prop start position, end position, path, eyeline, and screen direction. |
| Sound | Dialogue/VO/ambience/SFX/foley/music/silence cue for the shot. |
| Transition | Cut, match cut, sound bridge, dissolve, fade, or other edit logic. |
| Model Risk | What Seedance/Kling/Runway/Veo may misunderstand and whether the shot should be split. |

If the page lacks this information density, reject it as `storyboard_information_density_too_low`.

## Channel Notes

Commercial/product film:

- Start with hook or need state.
- Include a dedicated product proof insert.
- Include a dedicated packshot or memory frame.
- Product state must be locked per shot.
- Packaging text belongs in product boards or packshot frames, not tiny storyboard labels.

Film short:

- Establish geography before emotional or action close-ups.
- Camera movement must be motivated by character psychology, threat, discovery, or rhythm.
- Preserve axis unless breaking it is a deliberate story event.

Short drama/short video:

- First shot must be readable without context.
- Avoid wide shots that waste vertical frame.
- Put face, prop, or conflict in the first two seconds.

AI video generation:

- A shot list is not a video prompt.
- Split overloaded shots before prompt export.
- For Kling and Runway, direct I2V needs clean text-free frames.
- For Seedance and Veo, dense boards may guide shot order but must include anti-misread clauses.
- Professional terms must be paired with plain physical action.
