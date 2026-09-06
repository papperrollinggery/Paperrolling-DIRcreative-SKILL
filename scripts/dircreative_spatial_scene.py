#!/usr/bin/env python3
"""Views and model-layout references derived from one scene/shot artifact.

Coordinates and lens values are design intent, not measured reconstruction.
This helper does not adopt creative choices, authorize generation, or claim QA.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any

LAYOUT_EXCLUSIONS = ["character_identity", "prop_identity", "material", "texture", "final_art_style"]
PHASES = ("initial", "final")


def phases(scene: dict) -> list[str]:
    return ["initial", *[event["id"] for event in ordered_events(scene)], "final"]


def ordered_events(scene: dict) -> list[dict]:
    events = [
        {"id": f"{kind}-{i+1}", "kind": kind, "value": value}
        for field, kind in (("transfers", "transfer"), ("paths", "path"))
        for i, value in enumerate(scene.get(field, []))
    ]
    if any("order" in e["value"] for e in events):
        orders = [e["value"].get("order") for e in events]
        if any(not isinstance(n, int) or isinstance(n, bool) or n < 1 for n in orders) or len(set(orders)) != len(orders):
            raise ValueError("spatial_events_require_unique_explicit_orders")
        events.sort(key=lambda e: e["value"]["order"])
    return events


def apply_spatial_event(by_id: dict, event: dict) -> None:
    item = event["value"]
    if event["kind"] == "transfer":
        prop = by_id[item["prop_id"]]
        if prop.get("holder") != item["from_holder"]:
            raise ValueError("spatial_transfer_initial_holder_mismatch")
        prop.update(position=item["position"][:2], elevation=item["position"][2], holder=item["to_holder"], support=item["to_holder"], holder_hand=item.get("to_hand", "left"), visible=True)
        return
    entity = by_id[item["entity_id"]]
    if entity["position"] != item["points"][0]:
        raise ValueError(f"spatial_path_start_mismatch:{entity['id']}")
    delta = [item["points"][-1][i]-entity["position"][i] for i in (0, 1)]
    entity["position"] = item["points"][-1][:]
    if entity.get("hands"):
        entity["hands"] = {hand: [p[0]+delta[0], p[1]+delta[1], p[2]] for hand, p in entity["hands"].items()}
    if item.get("final_facing"):
        entity["facing"] = item["final_facing"][:]
    if item.get("final_gaze_target"):
        entity["gaze_target"] = item["final_gaze_target"]
    for prop in by_id.values():
        if prop.get("holder") == entity["id"]:
            prop["position"] = [prop["position"][i]+delta[i] for i in (0, 1)]
    for prop_id in item.get("stow_prop_ids", []):
        prop = by_id[prop_id]
        if prop.get("holder") != entity["id"]:
            raise ValueError("spatial_stow_owner_mismatch")
        prop["visible"] = False
        prop["position"] = entity["position"][:]
        entity.get("hands", {}).pop(prop.get("holder_hand", "right"), None)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contained(root: Path, value: str, *, exists: bool = True) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("spatial_path_must_be_project_relative")
    path = (root / relative).resolve(strict=exists)
    if not path.is_relative_to(root.resolve()):
        raise ValueError("spatial_path_escapes_project")
    return path


def point(value: Any, count: int = 2) -> bool:
    return isinstance(value, list) and len(value) == count and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value
    )


def camera_side(scene: dict, camera: dict) -> int | None:
    if not scene.get("relationship_axis"):
        return None
    entities = {e["id"]: e for e in scene["entities"]}
    a, b = (entities[i]["position"] for i in scene["relationship_axis"]["entity_ids"])
    p = camera["position"]
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    return 1 if cross > 1e-8 else -1 if cross < -1e-8 else 0


def crosses_footprint(a: list, b: list, feature: dict, margin: float = 0) -> bool:
    """Segment against an explicitly solid designed/observed floor footprint."""
    lower, upper = 0.0, 1.0
    for axis in (0, 1):
        lo = feature["position"][axis] - feature["size"][axis]/2 - margin
        hi = feature["position"][axis] + feature["size"][axis]/2 + margin
        delta = b[axis] - a[axis]
        if abs(delta) < 1e-9:
            if a[axis] <= lo or a[axis] >= hi:
                return False
        else:
            enter, leave = sorted(((lo-a[axis])/delta, (hi-a[axis])/delta))
            lower, upper = max(lower, enter), min(upper, leave)
            if lower >= upper:
                return False
    return True


def validate_scene(scene: Any) -> list[str]:
    if not isinstance(scene, dict):
        return ["spatial_scene_must_be_object"]
    errors: list[str] = []
    for key in ("scene_id", "revision", "description"):
        if not isinstance(scene.get(key), str) or not scene[key].strip():
            errors.append(f"spatial_scene_missing:{key}")
    if scene.get("coordinate_system") != "normalized_xy_design":
        errors.append("spatial_coordinates_must_declare_design_intent")
    room = scene.get("room", {})
    if not isinstance(room, dict) or not isinstance(room.get("features"), list):
        errors.append("spatial_room_features_required")
        room = {"features": []}
    entities = scene.get("entities", [])
    cameras = scene.get("cameras", [])
    if not isinstance(entities, list) or not entities:
        return errors + ["spatial_entities_required"]
    if not isinstance(cameras, list):
        return errors + ["spatial_cameras_must_be_list"]
    ids: set[str] = set()
    for entity in entities:
        if not isinstance(entity, dict):
            errors.append("spatial_entity_must_be_object")
            continue
        entity_id = entity.get("id")
        if not isinstance(entity_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", entity_id) or entity_id in ids:
            errors.append("spatial_entity_id_invalid_or_duplicate")
        ids.add(str(entity_id))
        if not point(entity.get("position")) or any(v < 0 or v > 1 for v in entity.get("position", [])):
            errors.append(f"entity_position_invalid:{entity_id}")
        if entity.get("kind") not in {"character", "prop"}:
            errors.append(f"entity_kind_invalid:{entity_id}")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(entity.get("color", ""))):
            errors.append(f"entity_color_invalid:{entity_id}")
        if entity.get("kind") == "character":
            facing = entity.get("facing")
            if (cameras or facing is not None) and (not point(facing) or math.hypot(*facing) < 1e-8):
                errors.append(f"entity_facing_invalid:{entity_id}")
            height = entity.get("height")
            if (cameras or height is not None) and (not isinstance(height, (int, float)) or not math.isfinite(height) or not 0 < height <= 1):
                errors.append(f"entity_height_invalid:{entity_id}")
        hands = entity.get("hands", {})
        if not isinstance(hands, dict) or set(hands) - {"left", "right"}:
            errors.append(f"entity_hands_invalid:{entity_id}")
            hands = {}
        for wrist in hands.values():
            if not point(wrist, 3):
                errors.append(f"entity_hand_invalid:{entity_id}")
    features = room["features"]
    feature_ids = {f.get("id") for f in features if isinstance(f, dict)}
    for f in features:
        if not isinstance(f, dict) or not point(f.get("position")) or not point(f.get("size")):
            errors.append("spatial_feature_geometry_invalid")
        elif any(v <= 0 for v in f["size"]) or not isinstance(f.get("height", 0), (int, float)) or not math.isfinite(f.get("height", 0)) or f.get("height", 0) < 0:
            errors.append("spatial_feature_dimensions_invalid")
        elif f.get("evidence") not in {"designed", "observed", "inferred", "unseen"}:
            errors.append(f"spatial_feature_evidence_missing:{f.get('id')}")
        elif f["evidence"] == "observed" and not f.get("source_ref"):
            errors.append(f"spatial_observation_source_missing:{f.get('id')}")
    for e in entities:
        if not isinstance(e, dict):
            continue
        if e.get("gaze_target") is not None and e["gaze_target"] not in ids | feature_ids:
            errors.append(f"entity_gaze_target_missing:{e.get('id')}")
        if e.get("holder") is not None and e["holder"] not in ids:
            errors.append(f"entity_holder_missing:{e.get('id')}")
        if e.get("support") not in ids | feature_ids | {"floor"}:
            errors.append(f"entity_support_missing:{e.get('id')}")
    axis = scene.get("relationship_axis", {})
    if not isinstance(axis, dict):
        axis = {}
    axis_ids = axis.get("entity_ids", [])
    if axis and (not isinstance(axis_ids, list) or len(axis_ids) != 2 or len(set(axis_ids)) != 2 or any(i not in ids for i in axis_ids)):
        errors.append("spatial_relationship_axis_invalid")
    if axis and axis.get("side") not in (-1, 1):
        errors.append("spatial_axis_side_invalid")
    shot_ids: set[str] = set()
    for camera in cameras:
        if not isinstance(camera, dict):
            errors.append("spatial_camera_must_be_object")
            continue
        shot_id = camera.get("shot_id")
        if not isinstance(shot_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", shot_id) or shot_id in shot_ids:
            errors.append("spatial_shot_id_invalid_or_duplicate")
        shot_ids.add(str(shot_id))
        if not point(camera.get("position")) or not point(camera.get("look_at")) or camera.get("position") == camera.get("look_at"):
            errors.append(f"camera_geometry_invalid:{shot_id}")
        for key, lower, upper in (("height", 0, 2), ("target_height", 0, 2), ("hfov_deg", 10, 150)):
            value = camera.get(key)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
                errors.append(f"camera_{key}_invalid:{shot_id}")
    if errors:
        return errors
    for field in ("paths", "transfers"):
        if not isinstance(scene.get(field, []), list) or any(not isinstance(e, dict) for e in scene.get(field, [])):
            errors.append(f"spatial_{field}_must_be_object_list")
    if errors:
        return errors
    by_id = {e["id"]: e for e in entities}
    for path in scene.get("paths", []):
        route = path.get("points", [])
        if path.get("entity_id") not in ids or not isinstance(route, list) or len(route) < 2 or not all(point(p) and all(0 <= v <= 1 for v in p) for p in route) or not path.get("trigger"):
            errors.append("spatial_path_invalid")
        if "final_facing" in path and (not point(path["final_facing"]) or math.hypot(*path["final_facing"]) < 1e-8):
            errors.append("spatial_path_final_facing_invalid")
        if path.get("final_gaze_target") is not None and path["final_gaze_target"] not in ids | feature_ids:
            errors.append("spatial_path_final_gaze_target_invalid")
        stow = path.get("stow_prop_ids", [])
        if not isinstance(stow, list) or any(not isinstance(i, str) or i not in by_id or by_id[i]["kind"] != "prop" for i in stow):
            errors.append("spatial_stow_props_invalid")
    for transfer in scene.get("transfers", []):
        if any(transfer.get(k) not in ids for k in ("prop_id", "from_holder", "to_holder")) or not point(transfer.get("position"), 3) or not transfer.get("trigger"):
            errors.append("spatial_transfer_invalid")
        elif transfer["from_holder"] == transfer["to_holder"] or next(e for e in entities if e["id"] == transfer["prop_id"])["kind"] != "prop":
            errors.append("spatial_transfer_ownership_invalid")
        elif any(by_id[transfer[k]]["kind"] != "character" for k in ("from_holder", "to_holder")) or transfer.get("to_hand", "left") not in {"left", "right"}:
            errors.append("spatial_transfer_hand_or_actor_invalid")
    if not errors:
        try:
            staged = copy.deepcopy(by_id)
            for event in ordered_events(scene):
                apply_spatial_event(staged, event)
                for entity in staged.values():
                    if not all(0 <= coordinate <= 1 for coordinate in entity["position"]):
                        errors.append(f"spatial_event_position_outside_scene:{event['id']}:{entity['id']}")
        except ValueError as exc:
            errors.append(str(exc))
        solid = [f for f in features if f.get("blocks_movement") is True and f["evidence"] in {"designed", "observed"}]
        for e in entities:
            if e.get("kind") != "character" or e.get("support") != "floor":
                continue
            for f in solid:
                if crosses_footprint(e["position"], e["position"], f):
                    errors.append(f"entity_inside_fixed_feature:{e['id']}:{f['id']}")
        for path in scene.get("paths", []):
            for a, b in zip(path["points"], path["points"][1:]):
                for f in solid:
                    if crosses_footprint(a, b, f):
                        errors.append(f"path_crosses_fixed_feature:{path['entity_id']}:{f['id']}")
        for camera in cameras:
            if axis and camera_side(scene, camera) != axis["side"] and not camera.get("crossing_reason"):
                errors.append(f"camera_axis_crossing_without_reason:{camera['shot_id']}")
    return errors


def require_scene(scene: dict) -> None:
    errors = validate_scene(scene)
    if errors:
        raise ValueError("; ".join(errors))


def entities_at(scene: dict, phase: str) -> list[dict]:
    if phase not in phases(scene):
        raise ValueError("spatial_phase_invalid")
    result = copy.deepcopy(scene["entities"])
    by_id = {e["id"]: e for e in result}
    for event in ordered_events(scene):
        if phase == "initial":
            break
        apply_spatial_event(by_id, event)
        if event["id"] == phase:
            break
    for prop in result:
        if prop.get("holder") in by_id and prop.get("visible", True):
            by_id[prop["holder"]].setdefault("hands", {})[prop.get("holder_hand", "right")] = [*prop["position"], prop.get("elevation", .15)]
    return result


def revise_path(scene: dict, entity_id: str, points: list, trigger: str, revision: str, *, path_id: str | None = None) -> dict:
    require_scene(scene)
    if revision == scene["revision"] or not revision:
        raise ValueError("spatial_revision_must_advance")
    result = copy.deepcopy(scene)
    result["revision"] = revision
    paths = result.setdefault("paths", [])
    matching = [path for index, path in enumerate(paths, 1)
                if path["entity_id"] == entity_id and (path_id is None or path_id == f"path-{index}")]
    if path_id is not None and not matching:
        raise ValueError("spatial_path_revision_event_not_found")
    if len(matching) > 1:
        raise ValueError("spatial_path_revision_requires_one_selected_event")
    if matching:
        matching[0].update(points=copy.deepcopy(points), trigger=trigger)
    else:
        path = {"entity_id": entity_id, "points": copy.deepcopy(points), "trigger": trigger}
        events = ordered_events(scene)
        if any("order" in event["value"] for event in events):
            path["order"] = max(event["value"]["order"] for event in events) + 1
        paths.append(path)
    require_scene(result)
    return result


def projector(camera: dict, aspect: float = 16 / 9):
    origin = [*camera["position"], camera["height"]]
    direction = [camera["look_at"][0] - origin[0], camera["look_at"][1] - origin[1], camera["target_height"] - origin[2]]
    length = math.sqrt(sum(v * v for v in direction))
    forward = [v / length for v in direction]
    horizontal = math.hypot(*forward[:2])
    right = [forward[1] / horizontal, -forward[0] / horizontal, 0]
    up = [right[1] * forward[2], -right[0] * forward[2], right[0] * forward[1] - right[1] * forward[0]]
    scale = 2 * math.tan(math.radians(camera["hfov_deg"]) / 2)

    def project(p):
        delta = [p[i] - origin[i] for i in range(3)]
        depth = sum(delta[i] * forward[i] for i in range(3))
        if depth <= .005:
            return None
        return [.5 + sum(delta[i] * right[i] for i in range(3)) / (depth * scale), .5 - sum(delta[i] * up[i] for i in range(3)) * aspect / (depth * scale), depth]
    return project


def primitive(points: list, color: str = "neutral", *, closed: bool = False, fill: bool = False, dashed: bool = False, label: str | None = None, entity_id: str | None = None) -> dict:
    return {"points": [[round(v, 6) for v in p[:2]] for p in points], "color": color, "closed": closed, "fill": fill, "dashed": dashed, "label": label, "entity_id": entity_id}


def project_scene(scene: dict, shot_id: str, phase: str = "initial") -> dict:
    require_scene(scene)
    camera = next((c for c in scene.get("cameras", []) if c["shot_id"] == shot_id), None)
    if camera is None:
        raise ValueError(f"spatial_shot_missing:{shot_id}")
    project = projector(camera)
    entities = entities_at(scene, phase)
    positions = {e["id"]: e["position"] for e in entities}
    top: list[dict] = [primitive([[0, 0], [1, 0], [1, 1], [0, 1]], closed=True)]
    layers: list[tuple[float, list[dict]]] = []
    for feature in scene["room"]["features"]:
        x, y = feature["position"]
        w, d = feature["size"]
        z = feature.get("height", 0)
        floor = [[x-w/2, y-d/2], [x+w/2, y-d/2], [x+w/2, y+d/2], [x-w/2, y+d/2]]
        top.append(primitive(floor, closed=True, dashed=feature["evidence"] in {"inferred", "unseen"}, label=feature.get("label")))
        projected = [project([*p, z]) for p in floor]
        if all(p is not None for p in projected):
            polys = [primitive(projected, closed=True, fill=True)]
            for p, q in zip(floor, projected):
                base = project([*p, 0])
                if base:
                    polys.append(primitive([base, q]))
            layers.append((sum(p[2] for p in projected) / 4, polys))
    eyelines: dict[str, float] = {}
    for index, entity in enumerate(entities):
        if entity.get("visible") is False:
            continue
        x, y = entity["position"]
        color = entity["color"]
        top.append(primitive([[x-.015, y-.015], [x+.015, y-.015], [x+.015, y+.015], [x-.015, y+.015]], color, closed=True, fill=True, label=entity.get("label", entity["id"]), entity_id=entity["id"]))
        if entity.get("gaze_target") in positions:
            target = positions[entity["gaze_target"]]
            top.append(primitive([[x, y], target], color, dashed=True))
            a, b = project([x, y, entity.get("height", .2)*.92]), project([*target, entity.get("height", .2)*.92])
            if a and b:
                eyelines[entity["id"]] = round(b[0]-a[0], 6)
        depth = project([x, y, entity.get("elevation", 0)])
        if not depth:
            continue
        shapes: list[dict] = []
        if entity["kind"] == "prop":
            z = entity.get("elevation", .15)
            world_shapes = [([[x-.008, y, z-.005], [x+.008, y, z-.005], [x+.008, y, z+.005], [x-.008, y, z+.005]], True)]
        else:
            h = entity["height"]
            facing = entity["facing"]
            norm = math.hypot(*facing)
            lateral = [facing[1]/norm, -facing[0]/norm]
            def body(u, v):
                return [x+lateral[0]*h*u, y+lateral[1]*h*u, h*v]
            outline = [(-.08, 0), (-.11, .42), (-.16, .75), (-.11, .8), (.11, .8), (.16, .75), (.11, .42), (.08, 0), (.02, 0), (0, .39), (-.02, 0)]
            world_shapes = [([body(u, v) for u, v in outline], True)]
            head = [body(.095*math.cos(t*math.pi/12), .9+.1*math.sin(t*math.pi/12)) for t in range(24)]
            world_shapes.append((head, True))
            nose = [x+facing[0]/norm*h*.07, y+facing[1]/norm*h*.07, h*.9]
            world_shapes.append(([body(0, .9), nose], False))
            for side, sign in (("left", -1), ("right", 1)):
                shoulder = body(sign*.15, .75)
                wrist = entity.get("hands", {}).get(side, body(sign*.23, .52))
                thickness = [lateral[0]*h*.025, lateral[1]*h*.025, 0]
                arm = [[p[i]+s*thickness[i] for i in range(3)] for p, s in ((shoulder, -1), (wrist, -1), (wrist, 1), (shoulder, 1))]
                world_shapes.append((arm, True))
        for world_points, closed in world_shapes:
            projected = [project(p) for p in world_points]
            if all(p is not None for p in projected):
                shapes.append(primitive(projected, color, closed=closed, fill=closed, entity_id=entity["id"]))
        layers.append((depth[2], shapes))
    for path in scene.get("paths", []):
        color = next(e["color"] for e in entities if e["id"] == path["entity_id"])
        top.append(primitive(path["points"], color, dashed=True))
    cx, cy = camera["position"]
    top.append(primitive([[cx-.02, cy-.02], [cx+.02, cy-.02], camera["look_at"]], "camera", closed=True, dashed=True))
    frame = [p for _, shapes in sorted(layers, key=lambda item: -item[0]) for p in shapes]
    return {"shot_id": shot_id, "label": camera.get("label", shot_id), "phase": phase, "top": top, "frame": frame, "axis_side": camera_side(dict(scene, entities=entities), camera), "eyelines": eyelines, "entity_positions": positions, "entity_states": entities}


def svg_image(primitives: list[dict], width: int = 1280, height: int = 720) -> str:
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="#ffffff"/>']
    for shape in primitives:
        color = shape["color"] if shape["color"].startswith("#") else "#a3a3a3"
        points = " ".join(f"{p[0]*width:.3f},{p[1]*height:.3f}" for p in shape["points"])
        tag = "polygon" if shape["closed"] else "polyline"
        parts.append(f'<{tag} points="{points}" fill="{"#ffffff" if shape["fill"] else "none"}" stroke="{color}" stroke-width="2.2" stroke-linejoin="round"/>')
    parts.append('</svg>\n')
    return "\n".join(parts)


def png_bytes(primitives: list[dict], width: int = 1280, height: int = 720) -> bytes:
    # Pillow is needed only for raster export; discussion and SVG need stdlib.
    from PIL import Image, ImageDraw
    scale = 2
    image = Image.new("RGB", (width*scale, height*scale), "white")
    draw = ImageDraw.Draw(image)
    for shape in primitives:
        coords = [(p[0]*width*scale, p[1]*height*scale) for p in shape["points"]]
        color = shape["color"] if shape["color"].startswith("#") else "#a3a3a3"
        if shape["fill"]:
            draw.polygon(coords, fill="white")
        if shape["closed"]:
            coords.append(coords[0])
        draw.line(coords, fill=color, width=4, joint="curve")
    output = io.BytesIO()
    image.resize((width, height), Image.Resampling.LANCZOS).save(output, format="PNG")
    return output.getvalue()


def write_png(path: Path, primitives: list[dict], width: int = 1280, height: int = 720) -> None:
    path.write_bytes(png_bytes(primitives, width, height))


def continuity(scene: dict, phase: str) -> dict:
    return {e["id"]: {k: e[k] for k in ("position", "facing", "gaze_target", "holder", "support", "asset_id", "visible") if k in e} for e in entities_at(scene, phase)}


def export_reference(scene_path: Path, project_root: Path, shot_id: str, phase: str, output_dir: Path) -> dict:
    root = project_root.resolve()
    scene_path = scene_path.resolve(strict=True)
    output_dir = output_dir.resolve()
    if not scene_path.is_relative_to(root) or not output_dir.is_relative_to(root):
        raise ValueError("spatial_export_must_stay_in_project")
    scene = json.loads(scene_path.read_text())
    view = project_scene(scene, shot_id, phase)
    revision_key = sha256(scene_path)[:12]
    name = f"{scene['scene_id']}-{shot_id}-{phase}-{revision_key}"
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path, png_path = output_dir / (name+".svg"), output_dir / (name+".png")
    svg_path.write_text(svg_image(view["frame"]), encoding="utf-8")
    write_png(png_path, view["frame"])
    colors = [{"entity_id": e["id"], "label": e.get("label", e["id"]), "color": e["color"], "color_name": e.get("color_name", e["color"]), "asset_id": e.get("asset_id")} for e in entities_at(scene, phase) if e.get("visible", True)]
    assignments = "；".join(f"{c['color_name']}轮廓对应{c['label']}" for c in colors)
    binding = {
        "scene_source": {"relative_path": scene_path.relative_to(root).as_posix(), "sha256": sha256(scene_path)},
        "scene_id": scene["scene_id"], "revision": scene["revision"], "shot_id": shot_id, "phase": phase,
        "reference": {"asset_id": name, "relative_path": png_path.relative_to(root).as_posix(), "sha256": sha256(png_path), "role": "layout", "media_class": "layout_reference", "primary_job": "position_pose_occlusion", "source_kind": "deterministic_render", "must_not_control": LAYOUT_EXCLUSIONS[:]},
        "svg": {"relative_path": svg_path.relative_to(root).as_posix(), "sha256": sha256(svg_path)},
        "color_binding": colors,
        "prompt_binding": f"站位参考中，{assignments}。该图提供当前机位的位置、朝向、尺度与遮挡；人物身份、服装、材质和光线由各自参考负责。",
        "continuity": continuity(scene, phase), "literal_frame_eligible": False,
        "quality_status": "deterministic_layout_not_media_quality_review",
    }
    (output_dir / (name+".json")).write_text(json.dumps(binding, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return binding


def validate_export(binding: dict, project_root: Path) -> list[str]:
    errors: list[str] = []
    try:
        source = contained(project_root, binding["scene_source"]["relative_path"])
        if sha256(source) != binding["scene_source"]["sha256"]:
            errors.append("spatial_scene_source_stale")
        scene = json.loads(source.read_text())
        errors.extend(validate_scene(scene))
        if scene.get("revision") != binding.get("revision") or scene.get("scene_id") != binding.get("scene_id"):
            errors.append("spatial_scene_revision_mismatch")
        if binding.get("shot_id") not in {c["shot_id"] for c in scene["cameras"]} or binding.get("phase") not in phases(scene):
            errors.append("spatial_export_shot_or_phase_invalid")
        for key in ("reference", "svg"):
            artifact = binding[key]
            if sha256(contained(project_root, artifact["relative_path"])) != artifact["sha256"]:
                errors.append(f"spatial_{key}_hash_mismatch")
        ref = binding["reference"]
        if ref.get("role") != "layout" or ref.get("media_class") != "layout_reference" or binding.get("literal_frame_eligible") is not False:
            errors.append("spatial_reference_role_invalid")
        if set(ref.get("must_not_control", [])) != set(LAYOUT_EXCLUSIONS):
            errors.append("spatial_reference_sovereignty_invalid")
        if not errors and binding.get("continuity") != continuity(scene, binding["phase"]):
            errors.append("spatial_continuity_mismatch")
        if not errors:
            projection = project_scene(scene, binding["shot_id"], binding["phase"])
            expected_svg = svg_image(projection["frame"]).encode("utf-8")
            if hashlib.sha256(expected_svg).hexdigest() != binding["svg"]["sha256"]:
                errors.append("spatial_svg_projection_mismatch")
            expected_png = png_bytes(projection["frame"])
            if hashlib.sha256(expected_png).hexdigest() != ref["sha256"]:
                errors.append("spatial_png_projection_mismatch")
            expected_colors = [{"entity_id": e["id"], "label": e.get("label", e["id"]), "color": e["color"], "color_name": e.get("color_name", e["color"]), "asset_id": e.get("asset_id")} for e in entities_at(scene, binding["phase"]) if e.get("visible", True)]
            if binding.get("color_binding") != expected_colors:
                errors.append("spatial_color_binding_mismatch")
            assignments = "；".join(f"{c['color_name']}轮廓对应{c['label']}" for c in expected_colors)
            if binding.get("prompt_binding") != f"站位参考中，{assignments}。该图提供当前机位的位置、朝向、尺度与遮挡；人物身份、服装、材质和光线由各自参考负责。":
                errors.append("spatial_prompt_binding_mismatch")
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        errors.append(f"spatial_export_invalid:{type(exc).__name__}")
    return errors


def read_export(path: Path, project_root: Path) -> dict:
    if not path.resolve().is_relative_to(project_root.resolve()):
        raise ValueError("spatial_export_path_escapes_project")
    binding = json.loads(path.read_text())
    errors = validate_export(binding, project_root)
    if errors:
        raise ValueError("; ".join(errors))
    return binding


def view_payload(scene: dict) -> dict:
    require_scene(scene)
    views = []
    for phase in phases(scene):
        if scene.get("cameras"):
            views.extend(project_scene(scene, c["shot_id"], phase) for c in scene["cameras"])
        else:
            entities = entities_at(scene, phase)
            views.append({"shot_id": "overview", "label": "俯视讨论", "phase": phase, "top": [], "frame": [], "axis_side": None, "eyelines": {}, "entity_positions": {e["id"]: e["position"] for e in entities}, "entity_states": entities})
    return {"scene_id": scene["scene_id"], "revision": scene["revision"], "description": scene["description"], "colors": [{"id": e["id"], "label": e.get("label", e["id"]), "color": e["color"]} for e in scene["entities"]], "views": views}


def build_spec(scene_path: Path, project_root: Path) -> dict:
    root = project_root.resolve()
    scene_path = scene_path.resolve(strict=True)
    scene = json.loads(scene_path.read_text())
    require_scene(scene)
    source = {"artifact_id": scene["scene_id"], "version": scene["revision"], "sha256": sha256(scene_path), "evidence_path": scene_path.relative_to(root).as_posix(), "lifecycle_status": "current"}
    snapshot = copy.deepcopy(scene)
    snapshot.update(source_refs=[scene["scene_id"]+"#/revision"], scene_state_sha256=source["sha256"])
    return {
        "spec_version": "1.1", "view_id": "blocking-"+source["sha256"][:12], "interaction_mode": "presentation_only",
        "execution_context": "standalone_chat", "controller": {"surface_owner": "dircreative", "user_facing": True},
        "view": {"intent": "blocking_camera", "display_mode": "inline", "customer_stage_label": "站位与镜位"},
        "source_truth": {"artifacts": [source]},
        "presentation": {"fields": [], "options": [], "recommendation": None, "downstream_effects": [], "spatial_scene": snapshot},
        "interactions": {"local": ["select"], "actions": [], "max_actions": 2, "deep_navigation": False, "nested_scroll": False},
        "write_boundary": {"preview_only": True, "confirmation_required": False, "writes_authoritative_state": False, "write_owner": "dircreative", "possible_write_targets": [], "forbidden_claims": ["lock", "readiness", "acceptance", "completion", "generation_authorization"]},
        "fallback": {"format": "markdown", "required_visible_fields": ["spatial_scene"], "content": fallback_text(scene)},
    }


def fallback_text(scene: dict) -> str:
    lines = [scene["description"]]
    labels = {e["id"]: e.get("label", e["id"]) for e in [*scene["entities"], *scene["room"]["features"]]}
    for e in scene["entities"]:
        if e.get("kind") == "prop" and e.get("holder"):
            lines.append(f"{labels[e['id']]}：当前由{labels.get(e['holder'], e['holder'])}持有。")
        else:
            gaze = f"，看向{labels.get(e['gaze_target'], e['gaze_target'])}" if e.get("gaze_target") else ""
            lines.append(f"{labels[e['id']]}：位置 {e['position']}{gaze}。")
    for c in scene.get("cameras", []):
        lines.append(f"{c.get('label', c['shot_id'])}：机位 {c['position']}，朝向 {c['look_at']}；{c.get('framing', '')}。")
    for p in scene.get("paths", []):
        lines.append(f"{labels[p['entity_id']]}：{p['trigger'].rstrip('。')}；起点 {p['points'][0]}，经过 {p['points'][1:-1]}，终点 {p['points'][-1]}。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("view", "export", "validate"):
        child = commands.add_parser(name)
        child.add_argument("--scene", type=Path, required=True)
        child.add_argument("--project-root", type=Path, required=True)
        if name == "view":
            child.add_argument("--output", type=Path, required=True)
        if name == "export":
            child.add_argument("--output-dir", type=Path, required=True)
            child.add_argument("--shot", required=True)
            child.add_argument("--phase", default="initial", help="initial, final, or transfer-N after a specific handoff")
    args = parser.parse_args()
    try:
        scene_path = args.scene.resolve(strict=True)
        if not scene_path.is_relative_to(args.project_root.resolve()):
            raise ValueError("spatial_scene_outside_project")
        scene = json.loads(scene_path.read_text())
        require_scene(scene)
        if args.command == "view":
            from dircreative_visualization_render import write_fragment
            spec = build_spec(scene_path, args.project_root)
            write_fragment(spec, args.output, test_output=True, force=False, project_root=args.project_root)
            print(json.dumps({"fragment": str(args.output.resolve()), "next_action": "read_current_host_visualize_contract_and_emit_content_reference_in_this_reply", "native_content_emitted": False, "host_mount_confirmed": False, "fallback": fallback_text(scene)}, ensure_ascii=False))
        elif args.command == "export":
            print(json.dumps(export_reference(scene_path, args.project_root, args.shot, args.phase, args.output_dir), ensure_ascii=False, indent=2))
        else:
            print("SPATIAL_SCENE: PASS (design geometry only)")
    except (OSError, ValueError, KeyError, ImportError) as exc:
        parser.exit(1, f"SPATIAL_SCENE: FAIL: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
