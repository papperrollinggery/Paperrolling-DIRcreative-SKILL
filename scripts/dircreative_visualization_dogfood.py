#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import sys
from pathlib import Path

from dircreative_visualization_render import render_fragment
from dircreative_visualization_spec import load_document
from dircreative_visualization_writeback import render_confirmation_fragment

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/chat-visualization"
DEFAULT_OUTPUT = Path("/tmp/dircreative-chat-visualizations")
PAGES = [
    ("idea-brief", "valid-idea-brief-inline.json"),
    ("director-concepts", "valid-director-compare-inline.json"),
    ("story-curves", "valid-story-beat-ribbon-inline.json"),
    ("script-timing", "valid-script-timing-bands-inline.json"),
    ("shot-rhythm", "valid-shot-timeline-fullscreen.json"),
    ("visual-direction", "valid-visual-direction-compare-inline.json"),
    ("visual-locks", "valid-visual-lock-matrix-inline.json"),
    ("reference-asset-graph", "valid-reference-asset-graph-fullscreen.json"),
    ("generation-qa", "valid-generation-qa-inline.json"),
    ("image-prompt-handoff", "valid-image-prompt-handoff-inline.json"),
    ("video-route-capabilities", "valid-video-route-capability-inline.json"),
]


def host_page(title: str, fragment: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: light dark;
  --background: #ffffff;
  --foreground: #171717;
  --card: #f7f7f7;
  --card-foreground: #171717;
  --primary: #171717;
  --primary-foreground: #ffffff;
  --secondary: #eeeeee;
  --secondary-foreground: #171717;
  --muted: #eeeeee;
  --muted-foreground: #626262;
  --accent: #e8e8e8;
  --accent-foreground: #171717;
  --border: #d4d4d4;
  --ring: #696969;
  --viz-series-1: #4477cc;
  --viz-series-2: #b44a72;
  --viz-series-3: #26856a;
  --viz-series-4: #8a64c6;
  --viz-series-5: #b06b2e;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --background: #171717;
    --foreground: #f4f4f4;
    --card: #242424;
    --card-foreground: #f4f4f4;
    --primary: #f4f4f4;
    --primary-foreground: #171717;
    --secondary: #303030;
    --secondary-foreground: #f4f4f4;
    --muted: #303030;
    --muted-foreground: #bdbdbd;
    --accent: #343434;
    --accent-foreground: #f4f4f4;
    --border: #454545;
    --ring: #bdbdbd;
    --viz-series-1: #7aa2ed;
    --viz-series-2: #e48caf;
    --viz-series-3: #65c6a7;
    --viz-series-4: #b39be8;
    --viz-series-5: #dca16b;
  }}
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; padding: 16px; background: var(--background); color: var(--foreground); }}
.card {{ padding: 14px; border: 1px solid var(--border); border-radius: 12px; background: var(--card); color: var(--card-foreground); }}
.viz-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 8px; }}
.viz-badge {{ display: inline-flex; padding: 3px 8px; border-radius: 999px; background: var(--accent); color: var(--accent-foreground); }}
.btn {{ appearance: none; padding: 8px 12px; border: 1px solid var(--border); border-radius: 9px; background: var(--secondary); color: var(--secondary-foreground); font: inherit; cursor: pointer; }}
.btn:focus-visible {{ outline: 2px solid var(--ring); outline-offset: 2px; }}
.btn[aria-pressed="true"] {{ border-color: var(--ring); box-shadow: 0 0 0 2px var(--ring); }}
.btn-primary {{ background: var(--primary); color: var(--primary-foreground); }}
.btn-block {{ width: 100%; }}
.viz-tile {{ width: 100%; }}
.text-small {{ font-size: 0.82em; }}
.text-muted {{ color: var(--muted-foreground); }}
</style>
</head>
<body data-dc-test-host="1">
{fragment}
</body>
</html>
"""


def write_decision_page(output: Path, pages: list[dict[str, str]], name: str, fixture: str, document: dict) -> None:
    fragment = render_fragment(document)
    fragment_path = output / f"{name}-fragment.html"
    page_path = output / f"{name}.html"
    fragment_path.write_text(fragment, encoding="utf-8")
    page_path.write_text(host_page(document["view"]["customer_stage_label"], fragment), encoding="utf-8")
    pages.append(
        {
            "name": name,
            "fixture": fixture,
            "page": str(page_path),
            "fragment": str(fragment_path),
            "view_id": document["view_id"],
            "gate_id": document["stage_gate"]["id"],
            "surface_kind": "decision",
        }
    )


def no_media_qa_document() -> dict:
    document = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    document["view_id"] = "generation-qa-no-media"
    document["presentation"].pop("previews", None)
    document["source_truth"]["artifacts"] = [
        artifact for artifact in document["source_truth"]["artifacts"] if not artifact.get("path")
    ]
    for option in document["presentation"]["options"]:
        option["source_refs"] = [ref for ref in option["source_refs"] if not ref.startswith("candidate-")]
    qa = next(field["value"] for field in document["presentation"]["fields"] if field["id"] == "qa_delta")
    qa["media_status"] = "当前没有可显示的媒体；以下差异只来自已绑定的结构化 QA 记录。"
    return document


def placeholder_qa_document() -> dict:
    document = copy.deepcopy(load_document(FIXTURE_ROOT / "valid-generation-qa-inline.json"))
    document["view_id"] = "generation-qa-illustrative-media"
    document["view"]["decision_prompt"] = "先提供真实候选图片，还是停止当前路线？"
    demo_files = {
        "candidate-a-preview": FIXTURE_ROOT / "assets/demo-candidate-frame.svg",
        "candidate-b-preview": FIXTURE_ROOT / "assets/demo-candidate-frame-b.svg",
    }
    for artifact in document["source_truth"]["artifacts"]:
        path = demo_files.get(artifact["artifact_id"])
        if path is None:
            continue
        artifact.update(
            {
                "version": "illustrative-1",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "path": path.relative_to(ROOT).as_posix(),
                "mime_type": "image/svg+xml",
                "review_classification": "illustrative_placeholder",
                "lifecycle_status": "current",
                "source_status": "unconfirmed",
                "authorization_status": "not_applicable",
                "channel_fit_status": "not_applicable",
            }
        )
        for key in ("source_evidence_ref", "authorization_evidence_ref", "channel_fit_evidence_ref"):
            artifact.pop(key, None)
    for index, preview in enumerate(document["presentation"]["previews"]):
        preview["label"] = f"演示参考图 {'A' if index == 0 else 'B'}"
        preview["alt"] = "用于验证审阅布局的演示参考图，不是实际生成候选"
        preview["caption"] = "演示参考图；当前没有真实候选，不能据此确认使用或发起重试。"
    document["presentation"]["recommendation"] = None
    for option in document["presentation"]["options"]:
        option["summary"] = "等待来源和版本可核验的真实候选，当前不作候选判断。"
        option["tradeoff"] = "补充真实图片后才能比较和决定处理方式。"
    document["presentation"]["downstream_effects"] = [
        {"stage": "generation_qa", "effect": "提供真实候选后重新执行图片 QA。"}
    ]
    placeholder_fields = {
        "blocker": "缺少真实候选图片",
        "passed_locks": [],
        "failed_locks": [],
        "smallest_retry": "暂不重试；先提供真实候选。",
        "preserved_artifacts": ["结构化检查维度", "当前项目事实"],
    }
    for field in document["presentation"]["fields"]:
        if field["id"] in placeholder_fields:
            field["value"] = placeholder_fields[field["id"]]
    qa = next(field["value"] for field in document["presentation"]["fields"] if field["id"] == "qa_delta")
    qa["media_status"] = "当前只有演示参考图；请先提供真实候选，暂不能确认使用。"
    for candidate in qa["candidates"]:
        candidate.update(
            {
                "judgment": "当前没有真实候选，不能形成候选级专业判断。",
                "blocker": "缺少来源和版本可核验的真实候选图片",
                "retry": "先提供或定位真实候选，再重新执行 QA",
                "preserve": "现有结构化检查维度和项目事实",
                "action_label": f"提供{candidate['label']}真实图片",
                "conversation_intent": f"请先定位或提供{candidate['label']}的真实图片，再继续审阅。",
            }
        )
    for dimension in qa["dimensions"]:
        for result in dimension["results"].values():
            result.update({"status": "warn", "value": "等待真实候选"})
    document["interactions"]["actions"] = [
        {
            "id": "provide-real-candidate",
            "label": "提供真实候选",
            "kind": "request_revision",
            "target_gate_id": document["stage_gate"]["id"],
            "conversation_intent": "请先定位或提供来源和版本可核验的真实候选图片，再继续审阅。",
        },
        {
            "id": "stop",
            "label": "停止当前路线",
            "kind": "stop",
            "target_gate_id": document["stage_gate"]["id"],
            "conversation_intent": "停止当前路线，不把演示参考图当作真实候选。",
        },
    ]
    document["fallback"]["decision_question"] = "先提供真实候选图片，还是停止当前路线？"
    return document


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate standalone dogfood pages for DIRcreative chat views.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()
    output = Path(args.output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    pages = []
    for name, fixture in PAGES:
        document = load_document(FIXTURE_ROOT / fixture)
        write_decision_page(output, pages, name, fixture, document)
    write_decision_page(output, pages, "generation-qa-no-media", "derived:no-media-qa", no_media_qa_document())
    write_decision_page(output, pages, "generation-qa-placeholder", "derived:placeholder-qa", placeholder_qa_document())
    receipt_fixture = "valid-writeback-receipt.json"
    receipt = load_document(FIXTURE_ROOT / receipt_fixture)
    echo_fragment = render_confirmation_fragment(receipt, ROOT)
    echo_fragment_path = output / "confirmation-echo-fragment.html"
    echo_page_path = output / "confirmation-echo.html"
    echo_fragment_path.write_text(echo_fragment, encoding="utf-8")
    echo_page_path.write_text(host_page("写回确认", echo_fragment), encoding="utf-8")
    pages.append(
        {
            "name": "confirmation-echo",
            "fixture": receipt_fixture,
            "page": str(echo_page_path),
            "fragment": str(echo_fragment_path),
            "view_id": receipt["receipt_id"],
            "gate_id": receipt["source_view"]["gate_id"],
            "surface_kind": "confirmation",
        }
    )
    manifest = {
        "status": "generated",
        "output_dir": str(output),
        "pages": pages,
        "viewports": [320, 736],
        "themes": ["light", "dark"],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    links = "\n".join(f'<li><a href="{html.escape(Path(item["page"]).name)}">{html.escape(item["name"])}</a></li>' for item in pages)
    (output / "index.html").write_text(
        f'<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>DIRcreative chat visualizations</title><body><ul>{links}</ul></body></html>',
        encoding="utf-8",
    )
    print("DIRcreative Chat Visualization Dogfood")
    print(f"output: {output}")
    print(f"pages: {len(pages)}")
    print("CHAT_VISUALIZATION_DOGFOOD: PASS")
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
