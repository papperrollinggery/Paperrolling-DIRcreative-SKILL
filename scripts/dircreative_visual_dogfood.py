#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = Path("/tmp/dircreative-visual-dogfood")
sys.dont_write_bytecode = True


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> str:
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    proc_env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=proc_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{proc.stderr}\n{proc.stdout}")
    return proc.stdout


def require_terms(text: str, terms: list[str], source: str) -> None:
    missing = [term for term in terms if term not in text]
    if missing:
        raise RuntimeError(f"{source} missing terms: {missing}")


def page(title: str, badge: str, markers: list[str], body: str) -> str:
    marker_html = "\n".join(f"<div>{html.escape(marker)}</div>" for marker in markers)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color-scheme: light; }}
body {{ margin: 0; background: #f3efe7; color: #111827; }}
.shell {{ max-width: 1180px; margin: 0 auto; padding: 34px 28px 56px; }}
header {{ border-bottom: 2px solid #111827; padding-bottom: 18px; margin-bottom: 22px; display: grid; grid-template-columns: 1fr auto; gap: 24px; align-items: end; }}
h1 {{ margin: 0; font-size: 34px; line-height: 1; letter-spacing: 0; }}
.badge {{ border: 1px solid #111827; padding: 7px 10px; font-size: 13px; text-transform: uppercase; }}
.grid {{ display: grid; grid-template-columns: repeat({len(markers)}, minmax(0, 1fr)); gap: 10px; margin-bottom: 18px; }}
.grid div {{ border: 1px solid #1f2937; padding: 10px; background: #e7f0ed; font-size: 13px; min-height: 36px; }}
pre {{ white-space: pre-wrap; word-break: break-word; background: #fffaf0; border: 1px solid #1f2937; padding: 22px; font-size: 14px; line-height: 1.55; box-shadow: 8px 8px 0 #d6c7a1; }}
a {{ color: #111827; }}
</style>
</head>
<body>
<div class="shell">
<header><h1>{html.escape(title)}</h1><div class="badge">{html.escape(badge)}</div></header>
<div class="grid">
{marker_html}
</div>
<pre>{html.escape(body)}</pre>
</div>
</body>
</html>
"""


def index_page(pages: list[dict[str, str]]) -> str:
    links = "\n".join(
        f"- {item['title']}: {item['file']}\n  {item['summary']}" for item in pages
    )
    return page(
        "DIRcreative Visual Dogfood",
        "reproducible local pages",
        ["一句话想法", "完整想法", "goal rough", "goal complete", "goal audit"],
        links + "\n\nOpen each HTML file with gstack browse and check text, console, and screenshot.",
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    one_idea = run(["python3", "scripts/dircreative_demo.py", "--example", "examples/live-user-sim-noodle"])
    require_terms(
        one_idea,
        ["15秒脚本", "5镜头分镜", "出图执行建议", "QA 与重试规则", "Seedance", "Kling", "当前没有生成真实图片或视频"],
        "one idea demo",
    )

    complete_idea = run(["python3", "scripts/dircreative_demo.py", "--example", "examples/complete-idea-segmentation-test"])
    require_terms(
        complete_idea,
        ["完整想法读取", "导演组会议", "6镜头分镜", "出图执行建议", "QA 与重试规则", "Seedance", "Kling", "当前没有生成真实图片或视频"],
        "complete idea demo",
    )

    goal_simulation = (ROOT / "examples" / "goal-mode-simulation-test" / "01-chat-transcript.md").read_text(encoding="utf-8")
    require_terms(
        goal_simulation,
        ["阶段: 目标模式模拟测试", "模拟用户选择", "阶段: 出图执行建议", "阶段: 模拟测试结论", "不计入真实验收", "不生成真实图片或视频"],
        "goal-mode simulation transcript",
    )

    goal_rough_simulation = (ROOT / "examples" / "goal-mode-rough-idea-simulation-test" / "01-chat-transcript.md").read_text(encoding="utf-8")
    require_terms(
        goal_rough_simulation,
        ["阶段: 想法读取", "模拟用户选择", "阶段: 分镜头确认", "阶段: 出图执行建议", "阶段: 模拟测试结论", "不计入真实验收", "不生成真实图片或视频"],
        "goal-mode rough idea simulation transcript",
    )

    env = os.environ.copy()
    env["DIRCREATIVE_SKIP_VISUAL_DOGFOOD"] = "1"
    readiness = run(["python3", "scripts/dircreative_readiness_audit.py"], env=env)
    require_terms(
        readiness,
        ["DIRcreative Readiness Audit", "rough idea chat path is user-visible", "complete idea chat path is user-visible", "assisted-generation preflight", "READINESS: PASS"],
        "readiness audit",
    )

    goal_audit = run(["python3", "scripts/dircreative_goal_audit.py"])
    require_terms(
        goal_audit,
        ["DIRcreative Goal Completion Audit", "TECHNICAL_READINESS: PASS", "GOAL_COMPLETE:"],
        "goal completion audit",
    )

    page_specs = [
        {
            "file": "one-idea.html",
            "title": "DIRcreative 一句话想法流程可视检查",
            "summary": "rough idea -> director room -> script -> shot list -> references -> contracts -> QA/retry",
            "html": page(
                "DIRcreative 一句话想法流程可视检查",
                "prompt-only / no media generated",
                ["导演组会议", "15 秒脚本 + 5 镜头", "参考图方案", "出图执行建议", "QA 与重试规则"],
                one_idea,
            ),
        },
        {
            "file": "complete-idea.html",
            "title": "DIRcreative 完整想法流程可视检查",
            "summary": "complete idea -> validation council -> 6-shot segmentation -> V2 references -> QA/retry",
            "html": page(
                "DIRcreative 完整想法流程可视检查",
                "prompt-only / no media generated",
                ["导演组会议可见", "6 镜头动态分镜", "V2 sequential 参考锁定", "出图执行建议", "QA 与重试规则"],
                complete_idea,
            ),
        },
        {
            "file": "readiness-audit.html",
            "title": "DIRcreative Readiness Audit",
            "summary": "goal-facing evidence matrix with PASS/FAIL checks",
            "html": page(
                "DIRcreative Readiness Audit",
                "READINESS: PASS",
                ["一句话想法路径", "完整想法路径", "导演组 + 分镜", "合同 + QA/retry", "assisted-generation 拦截"],
                readiness,
            ),
        },
        {
            "file": "goal-mode-simulation.html",
            "title": "DIRcreative Goal 模式模拟测试",
            "summary": "goal_context dogfood that keeps moving with simulated choices and no live acceptance receipt",
            "html": page(
                "DIRcreative Goal 模式模拟测试",
                "simulated choices / no live acceptance",
                ["目标模式模拟测试", "模拟用户选择", "出图执行建议", "参考图职责", "不计入真实验收"],
                goal_simulation,
            ),
        },
        {
            "file": "goal-mode-rough-idea.html",
            "title": "DIRcreative Goal 模式一句话想法模拟测试",
            "summary": "goal_context dogfood for one-sentence rough idea intake with simulated choices",
            "html": page(
                "DIRcreative Goal 模式一句话想法模拟测试",
                "rough idea / simulated choices",
                ["想法读取", "模拟用户选择", "5 镜头分镜", "出图执行建议", "不计入真实验收"],
                goal_rough_simulation,
            ),
        },
        {
            "file": "goal-audit.html",
            "title": "DIRcreative Goal Completion Audit",
            "summary": "separates technical readiness from final live-user acceptance",
            "html": page(
                "DIRcreative Goal Completion Audit",
                "GOAL_COMPLETE: NO",
                ["TECHNICAL_READINESS: PASS", "live user acceptance pending", "not complete yet"],
                goal_audit,
            ),
        },
    ]

    for spec in page_specs:
        (OUT_DIR / spec["file"]).write_text(spec["html"], encoding="utf-8")

    index = index_page(
        [
            {
                "file": spec["file"],
                "title": spec["title"],
                "summary": spec["summary"],
            }
            for spec in page_specs
        ]
    )
    (OUT_DIR / "index.html").write_text(index, encoding="utf-8")
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "index": str(OUT_DIR / "index.html"),
                "pages": [spec["file"] for spec in page_specs],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("DIRcreative Visual Dogfood Pages")
    print("=" * 72)
    print(f"index: {OUT_DIR / 'index.html'}")
    for spec in page_specs:
        print(f"page: {OUT_DIR / spec['file']}")
    print("VISUAL_DOGFOOD_PAGES: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
