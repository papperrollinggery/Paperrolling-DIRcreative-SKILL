from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import dircreative_video_distill as distill  # noqa: E402


class VideoDistillTests(unittest.TestCase):
    def make_video(self, root: Path) -> Path:
        video = root / "source.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=32x18:d=1", "-f", "lavfi", "-i", "anullsrc=r=8000:cl=mono", "-shortest", "-pix_fmt", "yuv420p", str(video)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        return video

    def make_workbench(self, root: Path, video: Path, *, traversal: bool = False) -> Path:
        project = root / "workbench"
        (project / "data").mkdir(parents=True)
        frame_dir = project / "assets" / "keyframes"
        frame_dir.mkdir(parents=True)
        (frame_dir / "frame.jpg").write_bytes(b"synthetic-frame")
        package = {"project_id": "test", "source": str(video), "metadata": {"media_receipt": {"master": {"sha256": distill.sha256_file(video), "size_bytes": video.stat().st_size}}}}
        shot = {"shot_id": "s1", "start_time": 0.0, "end_time": 0.5, "frame_refs": ["../outside.jpg" if traversal else "frame.jpg"], "annotation_source": "machine", "sound_design": "music-led", "dialogue": "untrusted"}
        (project / "data" / "media_package.json").write_text(json.dumps(package), encoding="utf-8")
        (project / "data" / "shots.json").write_text(json.dumps([shot]), encoding="utf-8")
        return project

    def prepare_bundle(self, root: Path, *, workbench: bool = True) -> tuple[Path, Path]:
        video = self.make_video(root)
        project = self.make_workbench(root, video) if workbench else None
        bundle = root / "bundle"
        result = distill.prepare(str(video), str(bundle), str(project) if project else None, "https://example.invalid/source")
        self.assertEqual(result["status"], "partial")
        return video, bundle

    def load_bundle(self, bundle: Path) -> tuple[dict, dict]:
        return (json.loads((bundle / "evidence.json").read_text()), json.loads((bundle / "analysis.json").read_text()))

    def write_analysis(self, bundle: Path, analysis: dict) -> None:
        (bundle / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_support(self, bundle: Path, evidence: dict, specs: list[tuple[str, str, str, bytes]]) -> dict[str, dict]:
        directory = bundle / "supporting"
        directory.mkdir(exist_ok=True)
        index = {}
        for item_id, kind, name, payload in specs:
            path = directory / name
            path.write_bytes(payload)
            item = {"id": item_id, "kind": kind, "relative_path": f"supporting/{name}", "sha256": distill.sha256_file(path), "source_media_sha256": evidence["media"]["sha256"]}
            evidence["supporting_evidence"].append(item)
            index[item_id] = item
        return index

    def make_fully_populated(self, evidence: dict, analysis: dict) -> dict:
        for name in distill.AXES:
            analysis["axes"][name] = {"status": "inferred" if name == "sound" else "observed", "observations": [{"text": "Human review note tied to an interval.", "evidence_ids": ["shot:s1", "frame:s1:frame.jpg"]}], "inference_boundary": "No production method asserted."}
        analysis["mechanisms"] = [{"evidence_ids": ["shot:s1"], "problem": "Candidate needs review", "mechanism": "Review the bound interval", "controls": "Human review", "when_to_use": "After inspection", "misuse_boundary": "Not a source fact", "review_check": "Reviewer checks frame", "validation_status": "candidate"}]
        analysis["gap_proposals"] = [{"kind": "unverified", "target": "Review coverage", "hypothesis": "More review may help", "test": "Inspect interval", "scope": "One shot"}]
        analysis["source_evidence_sha256"] = distill.json_hash(evidence)
        return analysis

    def test_prepare_imports_only_bound_workbench_evidence_and_unknown_axes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            video, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            self.assertEqual(evidence["media"]["sha256"], distill.sha256_file(video))
            self.assertEqual(evidence["workbench"]["status"], "imported")
            self.assertEqual(evidence["evidence"][0]["id"], "shot:s1")
            self.assertNotIn("sound_design", json.dumps(evidence))
            self.assertEqual(set(analysis["axes"]), set(distill.AXES))
            self.assertTrue(all(item["status"] == "unknown" for item in analysis["axes"].values()))
            result = distill.validate(str(bundle))
            self.assertEqual(result["status"], "partial")
            self.assertFalse(result["errors"])

    def test_populated_analysis_validates_and_renders_escaped_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            analysis = self.make_fully_populated(evidence, analysis)
            analysis["axes"]["narrative"]["observations"][0]["text"] = "<b>*untrusted*</b>"
            self.write_analysis(bundle, analysis)
            self.assertEqual(distill.validate(str(bundle))["status"], "valid")
            report = distill.render(str(bundle)).read_text(encoding="utf-8")
            self.assertIn("&lt;b&gt;\\*untrusted\\*&lt;/b&gt;", report)
            self.assertNotIn("<b>", report)

    def test_validation_reprobes_media_metadata_and_current_duration(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            evidence["media"].update({"duration_seconds": 999.0, "width": 9999, "height": 9999, "fps": 120.0})
            evidence["evidence"][0]["end_seconds"] = 500.0
            analysis["source_evidence_sha256"] = distill.json_hash(evidence)
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.write_analysis(bundle, analysis)
            errors = distill.validate(str(bundle))["errors"]
            self.assertIn("bound media metadata changed", errors)
            self.assertIn("invalid evidence timing: shot:s1", errors)

    def test_comparison_cycles_are_structured_and_never_quality_verdicts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            _, analysis = self.load_bundle(bundle)
            analysis["comparison_cycles"] = [{"criterion_id": "transition-clarity-v1", "reference_effect": "Transition clarity", "why_needed": "Review found an open question", "artifact_before": None, "gap": "No authorized before/after artifact", "change": "Candidate timing adjustment is not executable here", "artifact_after": None, "review_evidence": "Untestable because no authorized result artifact exists.", "outcome": "untestable"}]
            self.write_analysis(bundle, analysis)
            result = distill.validate(str(bundle))
            self.assertEqual(result["creative_quality"], "unverified")
            self.assertEqual(result["iteration_status"], "review_recorded")
            report = distill.render(str(bundle)).read_text(encoding="utf-8")
            self.assertIn("Creative quality: unverified", report)
            self.assertIn("## Comparison cycles", report)
            analysis["comparison_cycles"][0]["criterion_id"] = ""
            self.write_analysis(bundle, analysis)
            self.assertIn("invalid comparison cycle", distill.validate(str(bundle))["errors"])

    def test_bound_supporting_receipts_gate_comparison_and_render_appendix(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            supports = self.add_support(bundle, evidence, [("artifact-before", "production_artifact", "before.txt", b"before"), ("artifact-after", "production_artifact", "after.txt", b"after"), ("review-001", "review_record", "review.txt", b"human review")])
            analysis["comparison_cycles"] = [{"criterion_id": "clarity-v1", "reference_effect": "Transition clarity", "why_needed": "Compare an authorized iteration", "artifact_before": "artifact-before", "gap": "Observed gap needs review", "change": "Candidate revision", "artifact_after": "artifact-after", "review_evidence": "review-001", "outcome": "improved"}]
            analysis["source_evidence_sha256"] = distill.json_hash(evidence)
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.write_analysis(bundle, analysis)
            self.assertFalse(distill.validate(str(bundle))["errors"])
            report = distill.render(str(bundle)).read_text(encoding="utf-8")
            self.assertIn("Criterion ID: clarity-v1", report)
            self.assertIn(supports["review-001"]["sha256"], report)
            (bundle / "supporting" / "before.txt").write_bytes(b"modified")
            self.assertIn("supporting evidence changed: artifact-before", distill.validate(str(bundle))["errors"])

    def test_fake_missing_outside_supporting_receipts_and_transcript_reference(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            self.add_support(bundle, evidence, [("asr-001", "transcript", "asr.txt", b"unverified words")])
            analysis["axes"]["dialogue"] = {"status": "inferred", "observations": [{"text": "Transcript requires human verification.", "evidence_ids": ["asr-001"]}], "inference_boundary": "Transcript is not proof of heard dialogue."}
            analysis["source_evidence_sha256"] = distill.json_hash(evidence)
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.write_analysis(bundle, analysis)
            result = distill.validate(str(bundle))
            self.assertFalse(result["errors"])
            self.assertEqual(analysis["axes"]["sound"]["status"], "unknown")
            evidence["supporting_evidence"][0]["relative_path"] = "../outside.txt"
            analysis["source_evidence_sha256"] = distill.json_hash(evidence)
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.assertTrue(any("supporting evidence" in item for item in distill.validate(str(bundle))["errors"]))
            evidence["supporting_evidence"][0]["relative_path"] = "supporting/missing.txt"
            analysis["comparison_cycles"] = [{"criterion_id": "fake-v1", "reference_effect": "Test", "why_needed": "Test fake receipt", "artifact_before": "asr-001", "gap": "Test", "change": "Test", "artifact_after": "fake-id", "review_evidence": "fake-id", "outcome": "unresolved"}]
            analysis["source_evidence_sha256"] = distill.json_hash(evidence)
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.write_analysis(bundle, analysis)
            errors = distill.validate(str(bundle))["errors"]
            self.assertIn("supporting evidence is unavailable: asr-001", errors)
            self.assertIn("comparison cycle requires bound supporting evidence", errors)

    def test_json_limit_and_ffprobe_timeout_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); oversized = root / "oversized.json"
            with oversized.open("wb") as handle:
                handle.seek(distill.MAX_JSON_BYTES)
                handle.write(b"x")
            with self.assertRaisesRegex(distill.DistillError, "exceeds"):
                distill.load_json(oversized)
            huge_integer = root / "huge-integer.json"
            huge_integer.write_bytes(b'{"n":' + b"9" * 5000 + b"}")
            with self.assertRaisesRegex(distill.DistillError, "invalid JSON"):
                distill.load_json(huge_integer)
            video = self.make_video(root)
            with patch.object(distill.subprocess, "run", side_effect=subprocess.TimeoutExpired("ffprobe", 60)):
                with self.assertRaisesRegex(distill.DistillError, "timeout"):
                    distill.probe_media(video)

    def test_observed_axis_requires_compatible_evidence_modality(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            self.add_support(bundle, evidence, [("asr-001", "transcript", "asr.txt", b"unverified transcript"), ("audio-001", "audio_measurement", "audio.json", b'{"rms":-12}')])
            analysis["axes"]["narrative"] = {"status": "observed", "observations": [{"text": "Transcript-only claim.", "evidence_ids": ["asr-001"]}], "inference_boundary": "Transcript is not visual evidence."}
            analysis["source_evidence_sha256"] = distill.json_hash(evidence)
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.write_analysis(bundle, analysis)
            self.assertIn("observed narrative requires shot or frame evidence", distill.validate(str(bundle))["errors"])
            analysis["axes"]["narrative"]["status"] = "inferred"
            analysis["axes"]["sound"] = {"status": "observed", "observations": [{"text": "Machine measurement is present.", "evidence_ids": ["audio-001"]}], "inference_boundary": "Measurement is not proof of heard content."}
            self.write_analysis(bundle, analysis)
            self.assertFalse(distill.validate(str(bundle))["errors"])
            self.assertIn("not proof of heard content", distill.render(str(bundle)).read_text(encoding="utf-8"))

    def test_validation_fails_closed_for_changed_media_and_frame(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            video, bundle = self.prepare_bundle(Path(raw))
            video.write_bytes(video.read_bytes() + b"changed")
            result = distill.validate(str(bundle))
            self.assertEqual(result["status"], "invalid")
            self.assertIn("bound media changed", result["errors"])
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, _ = self.load_bundle(bundle)
            Path(evidence["workbench"]["project_path"]).joinpath("assets/keyframes/frame.jpg").write_bytes(b"changed")
            self.assertIn("bound frame changed: frame:s1:frame.jpg", distill.validate(str(bundle))["errors"])

    def test_malformed_bindings_return_invalid_without_throwing(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            evidence["media"]["duration_seconds"] = "not-a-number"
            evidence["media"]["has_audio"] = "<img src=x onerror=alert(1)>"
            evidence["workbench"] = None
            evidence["evidence"][0]["frames"] = None
            analysis["source_evidence_sha256"] = distill.json_hash(evidence)
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.write_analysis(bundle, analysis)
            result = distill.validate(str(bundle))
            self.assertEqual(result["status"], "invalid")
            self.assertTrue(result["errors"])

    def test_nan_and_missing_frame_cannot_validate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            evidence["evidence"][0]["start_seconds"] = float("nan")
            evidence["evidence"][0]["frames"] = []
            analysis = self.make_fully_populated(evidence, analysis)
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.write_analysis(bundle, analysis)
            errors = distill.validate(str(bundle))["errors"]
            self.assertIn("invalid evidence timing: shot:s1", errors)
            self.assertIn("evidence requires at least one frame: shot:s1", errors)

    def test_workbench_rejects_nonfinite_timing_during_prepare(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); video = self.make_video(root); project = self.make_workbench(root, video)
            shots_path = project / "data" / "shots.json"
            shots = json.loads(shots_path.read_text(encoding="utf-8"))
            shots[0]["start_time"] = float("nan")
            shots_path.write_text(json.dumps(shots), encoding="utf-8")
            with self.assertRaisesRegex(distill.DistillError, "timing is invalid"):
                distill.prepare(str(video), str(root / "bundle"), str(project), None)

    def test_shape_errors_are_structured_and_render_fields_required(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            evidence["workbench"]["status"] = {}
            evidence["evidence"][0]["start_seconds"] = 10 ** 1000
            analysis["axes"]["narrative"]["status"] = []
            analysis["axes"]["dialogue"]["observations"] = [{"text": "x", "evidence_ids": [{}]}]
            analysis.pop("scope")
            analysis["source_evidence_sha256"] = distill.json_hash(evidence)
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.write_analysis(bundle, analysis)
            result = distill.validate(str(bundle))
            self.assertEqual(result["status"], "invalid")
            self.assertTrue(result["errors"])

    def test_rejects_metadata_drift_interval_overlap_and_self_validated_mechanism(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            overlapping = dict(evidence["evidence"][0])
            overlapping["id"] = "shot:s2"
            overlapping["start_seconds"] = 0.25
            overlapping["end_seconds"] = 0.75
            overlapping["frames"] = [{**overlapping["frames"][0], "id": "frame:s2:frame.jpg"}]
            evidence["evidence"].append(overlapping)
            analysis = self.make_fully_populated(evidence, analysis)
            analysis["mechanisms"][0]["validation_status"] = "validated"
            project = Path(evidence["workbench"]["project_path"])
            package_path = project / "data" / "media_package.json"
            package_path.write_text(package_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            (bundle / "evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
            self.write_analysis(bundle, analysis)
            errors = distill.validate(str(bundle))["errors"]
            self.assertIn("bound workbench media package changed or mismatches media", errors)
            self.assertIn("evidence intervals are unordered or overlap: shot:s2", errors)
            self.assertIn("invalid mechanism; this helper permits candidate status only", errors)

    def test_path_and_output_handling_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); video = self.make_video(root); project = self.make_workbench(root, video, traversal=True)
            with self.assertRaisesRegex(distill.DistillError, "escapes"):
                distill.prepare(str(video), str(root / "bundle"), str(project), None)
            occupied = root / "occupied"; occupied.mkdir()
            with self.assertRaisesRegex(distill.DistillError, "output directory must be new"):
                distill.prepare(str(video), str(occupied), None, None)

    def test_without_workbench_stays_partial_without_fabricated_shots(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); video = self.make_video(root); bundle = root / "bundle"
            distill.prepare(str(video), str(bundle), None, None)
            evidence, _ = self.load_bundle(bundle)
            self.assertEqual(evidence["workbench"]["status"], "unavailable")
            self.assertEqual(evidence["evidence"], [])
            result = distill.validate(str(bundle))
            self.assertEqual(result["status"], "partial")
            self.assertIn("workbench shot evidence", result["missing_coverage"])

    def test_source_url_is_curated_and_userinfo_rejected(self) -> None:
        self.assertEqual(distill.sanitized_source_url("https://example.invalid/movie?token=private#secret"), "https://example.invalid/movie")
        for url in ("https://user:private@example.invalid/movie", "file:///private", [], "https://example.invalid/" + "x" * 4097):
            with self.assertRaises(distill.DistillError):
                distill.sanitized_source_url(url)

    def test_versioned_report_preserves_previous_and_includes_controls(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            _, bundle = self.prepare_bundle(Path(raw))
            evidence, analysis = self.load_bundle(bundle)
            self.write_analysis(bundle, self.make_fully_populated(evidence, analysis))
            first = distill.render(str(bundle)); original = first.read_bytes()
            second = distill.render(str(bundle), "report-v02.md")
            self.assertEqual(first.read_bytes(), original)
            self.assertIn("review_check", second.read_text())
            with self.assertRaises(distill.DistillError):
                distill.render(str(bundle), "../outside.md")
            with self.assertRaises(distill.DistillError):
                distill.render(str(bundle))


if __name__ == "__main__":
    unittest.main()
