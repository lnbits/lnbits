from __future__ import annotations

import base64
import json
import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
from io import BytesIO
from pathlib import Path
from typing import Any

import playwright

REPORT_DIR = Path("playwright-report")
RESULTS_DIR = REPORT_DIR / "test-results"
REPORT_PATH = REPORT_DIR / "index.html"
DATA_DIR = REPORT_DIR / "data"
TRACE_DIR = REPORT_DIR / "trace"

VITE_DIR = Path(playwright.__file__).resolve().parent / "driver/package/lib/vite"
HTML_REPORT_DIR = VITE_DIR / "htmlReport"
TRACE_VIEWER_DIR = VITE_DIR / "traceViewer"

PROJECT_NAME = "chromium"
REPORT_TITLE = "LNbits E2E Playwright Report"


@dataclass(frozen=True)
class TestArtifacts:
    name: str
    path: Path
    screenshots: list[Path]
    traces: list[Path]
    videos: list[Path]

    @property
    def outcome(self) -> str:
        if any(path.name.startswith("test-failed") for path in self.screenshots):
            return "unexpected"
        if any(path.name.startswith("test-finished") for path in self.screenshots):
            return "expected"
        return "unexpected"

    @property
    def status(self) -> str:
        return "passed" if self.outcome == "expected" else "failed"

    @property
    def ok(self) -> bool:
        return self.outcome == "expected"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _reset_generated_report_assets()

    artifacts = sorted(_find_artifacts(), key=lambda item: item.name)
    report, test_files, has_traces = _build_report_data(artifacts)
    if has_traces:
        _copy_trace_viewer()
    _write_native_report(report, test_files)


def _reset_generated_report_assets() -> None:
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    if TRACE_DIR.exists():
        shutil.rmtree(TRACE_DIR)
    for stale_asset in (REPORT_DIR / "report.js", REPORT_DIR / "report.css"):
        stale_asset.unlink(missing_ok=True)


def _find_artifacts() -> list[TestArtifacts]:
    if not RESULTS_DIR.is_dir():
        return []

    artifacts: list[TestArtifacts] = []
    for path in sorted(item for item in RESULTS_DIR.iterdir() if item.is_dir()):
        artifacts.append(
            TestArtifacts(
                name=path.name,
                path=path,
                screenshots=sorted(path.glob("*.png"), key=_screenshot_sort_key),
                traces=sorted(path.glob("*.zip")),
                videos=sorted(path.glob("*.webm")),
            )
        )
    return artifacts


def _build_report_data(
    artifacts: list[TestArtifacts],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], bool]:
    start_time = _report_start_time(artifacts)
    test_files: dict[str, dict[str, Any]] = {}
    file_summaries: dict[str, dict[str, Any]] = {}
    report_errors: list[str] = []
    has_traces = False

    for artifact in artifacts:
        file_name, test_title = _test_identity(artifact.name)
        file_id = _stable_id(file_name)
        test_id = _stable_id(artifact.name)
        location = {"file": file_name, "line": 1, "column": 1}
        duration = _duration_ms(artifact)
        test_start_time = _start_time(artifact).isoformat().replace("+00:00", "Z")
        attachments, has_artifact_traces = _serialize_attachments(artifact)
        has_traces = has_traces or has_artifact_traces

        errors = []
        if not artifact.ok:
            errors.append(
                {
                    "message": (
                        "Pytest reported this test as failed or did not write a "
                        "test-finished screenshot. See screenshots, video, and trace."
                    )
                }
            )

        result = {
            "duration": duration,
            "startTime": test_start_time,
            "retry": 0,
            "steps": [],
            "errors": errors,
            "status": artifact.status,
            "annotations": [],
            "attachments": attachments,
            "workerIndex": 0,
        }
        summary_result = {
            "attachments": [
                {
                    "name": attachment["name"],
                    "contentType": attachment["contentType"],
                    "path": attachment.get("path"),
                }
                for attachment in attachments
            ],
            "startTime": test_start_time,
            "workerIndex": 0,
        }

        test_case = {
            "testId": test_id,
            "title": test_title,
            "projectName": PROJECT_NAME,
            "location": location,
            "duration": duration,
            "annotations": [],
            "tags": [],
            "outcome": artifact.outcome,
            "path": [],
            "results": [result],
            "ok": artifact.ok,
        }
        test_case_summary = {
            "testId": test_id,
            "title": test_title,
            "projectName": PROJECT_NAME,
            "location": location,
            "duration": duration,
            "annotations": [],
            "tags": [],
            "outcome": artifact.outcome,
            "path": [],
            "ok": artifact.ok,
            "results": [summary_result],
        }

        test_file = test_files.setdefault(
            file_id, {"fileId": file_id, "fileName": file_name, "tests": []}
        )
        test_file["tests"].append(test_case)

        file_summary = file_summaries.setdefault(
            file_id,
            {
                "fileId": file_id,
                "fileName": file_name,
                "tests": [],
                "stats": _empty_stats(),
            },
        )
        file_summary["tests"].append(test_case_summary)
        _record_outcome(file_summary["stats"], artifact.outcome)

        if errors:
            report_errors.append(f"{test_title}: {errors[0]['message']}")

    report_stats = _empty_stats()
    for file_summary in file_summaries.values():
        _merge_stats(report_stats, file_summary["stats"])

    duration = _report_duration_ms(artifacts)
    report = {
        "metadata": {},
        "startTime": int(start_time.timestamp() * 1000),
        "duration": duration,
        "files": _sort_file_summaries(list(file_summaries.values())),
        "projectNames": [PROJECT_NAME] if artifacts else [],
        "stats": report_stats,
        "errors": report_errors,
        "options": {"title": REPORT_TITLE},
        "machines": (
            [
                {
                    "duration": duration,
                    "startTime": int(start_time.timestamp() * 1000),
                    "tag": [PROJECT_NAME],
                }
            ]
            if artifacts
            else []
        ),
    }
    return report, test_files, has_traces


def _serialize_attachments(
    artifact: TestArtifacts,
) -> tuple[list[dict[str, Any]], bool]:
    attachments: list[dict[str, Any]] = []
    has_traces = False

    for screenshot in artifact.screenshots:
        attachments.append(
            _copy_attachment(
                screenshot,
                name=_screenshot_name(screenshot),
                content_type="image/png",
            )
        )
    for video in artifact.videos:
        attachments.append(
            _copy_attachment(video, name="video", content_type="video/webm")
        )
    for trace in artifact.traces:
        has_traces = True
        attachments.append(
            _copy_attachment(trace, name="trace", content_type="application/zip")
        )

    return attachments, has_traces


def _copy_attachment(path: Path, name: str, content_type: str) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    content = path.read_bytes()
    target_name = f"{sha1(content, usedforsecurity=False).hexdigest()}{path.suffix}"
    target = DATA_DIR / target_name
    if not target.exists():
        target.write_bytes(content)
    return {"name": name, "contentType": content_type, "path": f"data/{target_name}"}


def _write_native_report(
    report: dict[str, Any], test_files: dict[str, dict[str, Any]]
) -> None:
    html = (HTML_REPORT_DIR / "index.html").read_text(encoding="utf-8")
    script = (HTML_REPORT_DIR / "report.js").read_text(encoding="utf-8")
    stylesheet = (HTML_REPORT_DIR / "report.css").read_text(encoding="utf-8")

    html = re.sub(
        r'<script type="module"[^>]*></script>',
        lambda _: f'<script type="module">{script}</script>',
        html,
    )
    html = re.sub(
        r'<link rel="stylesheet"[^>]*>',
        lambda _: f"<style type='text/css'>{stylesheet}</style>",
        html,
    )
    html += (
        '<template id="playwrightReportBase64">data:application/zip;base64,'
        f"{_zip_report_payload(report, test_files)}</template>"
    )
    REPORT_PATH.write_text(html, encoding="utf-8")


def _zip_report_payload(
    report: dict[str, Any], test_files: dict[str, dict[str, Any]]
) -> str:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("report.json", json.dumps(report, separators=(",", ":")))
        for file_id, test_file in test_files.items():
            zip_file.writestr(
                f"{file_id}.json", json.dumps(test_file, separators=(",", ":"))
            )
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _copy_trace_viewer() -> None:
    assets_target = TRACE_DIR / "assets"
    assets_target.mkdir(parents=True, exist_ok=True)

    for path in TRACE_VIEWER_DIR.iterdir():
        if path.name.endswith(".map") or "watch" in path.name or path.name == "assets":
            continue
        target = TRACE_DIR / path.name
        if path.is_dir():
            shutil.copytree(path, target, dirs_exist_ok=True)
        else:
            shutil.copy2(path, target)

    for path in (TRACE_VIEWER_DIR / "assets").iterdir():
        if path.name.endswith(".map") or "xtermModule" in path.name:
            continue
        shutil.copy2(path, assets_target / path.name)


def _test_identity(artifact_name: str) -> tuple[str, str]:
    name = artifact_name
    project_suffix = f"-{PROJECT_NAME}"
    if name.endswith(project_suffix):
        name = name[: -len(project_suffix)]

    match = re.match(r"^tests-e2e-(?P<module>.+)-py-(?P<test>.+)$", name)
    if not match:
        return artifact_name, artifact_name

    module = match.group("module").replace("-", "_")
    test_name = match.group("test").replace("-", "_")
    return f"tests/e2e/{module}.py", test_name


def _report_start_time(artifacts: list[TestArtifacts]) -> datetime:
    starts = [_start_time(artifact) for artifact in artifacts]
    return min(starts) if starts else datetime.now(tz=timezone.utc)


def _start_time(artifact: TestArtifacts) -> datetime:
    paths = _artifact_files(artifact)
    if not paths:
        return datetime.now(tz=timezone.utc)
    return datetime.fromtimestamp(
        min(path.stat().st_mtime for path in paths), tz=timezone.utc
    )


def _duration_ms(artifact: TestArtifacts) -> int:
    paths = _artifact_files(artifact)
    if len(paths) < 2:
        return 0
    starts = [path.stat().st_mtime for path in paths]
    return max(1, int((max(starts) - min(starts)) * 1000))


def _report_duration_ms(artifacts: list[TestArtifacts]) -> int:
    paths = [path for artifact in artifacts for path in _artifact_files(artifact)]
    if len(paths) < 2:
        return 0
    times = [path.stat().st_mtime for path in paths]
    return max(1, int((max(times) - min(times)) * 1000))


def _artifact_files(artifact: TestArtifacts) -> list[Path]:
    return [*artifact.screenshots, *artifact.videos, *artifact.traces]


def _sort_file_summaries(
    file_summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        file_summaries,
        key=lambda file_summary: (
            -file_summary["stats"]["unexpected"],
            file_summary["fileName"],
        ),
    )


def _empty_stats() -> dict[str, Any]:
    return {
        "total": 0,
        "expected": 0,
        "unexpected": 0,
        "flaky": 0,
        "skipped": 0,
        "ok": True,
    }


def _record_outcome(stats: dict[str, Any], outcome: str) -> None:
    stats["total"] += 1
    stats[outcome] += 1
    stats["ok"] = stats["unexpected"] + stats["flaky"] == 0


def _merge_stats(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key in ("total", "expected", "unexpected", "flaky", "skipped"):
        target[key] += source[key]
    target["ok"] = target["unexpected"] + target["flaky"] == 0


def _stable_id(value: str) -> str:
    return sha1(value.encode("utf-8"), usedforsecurity=False).hexdigest()[:20]


def _screenshot_name(path: Path) -> str:
    if path.name.startswith("url-"):
        return path.stem
    if path.name.startswith("test-failed"):
        return "screenshot"
    if path.name.startswith("test-finished"):
        return "screenshot"
    return path.stem


def _screenshot_sort_key(path: Path) -> tuple[int, str]:
    if path.name.startswith("url-"):
        return (0, path.name)
    if path.name.startswith(("dialog-", "toast-")):
        return (1, path.name)
    return (2, path.name)


if __name__ == "__main__":
    main()
