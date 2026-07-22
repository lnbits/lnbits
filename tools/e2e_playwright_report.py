from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from urllib.parse import quote

REPORT_DIR = Path("playwright-report")
RESULTS_DIR = REPORT_DIR / "test-results"
REPORT_PATH = REPORT_DIR / "index.html"


@dataclass(frozen=True)
class TestArtifacts:
    name: str
    path: Path
    screenshots: list[Path]
    traces: list[Path]
    videos: list[Path]

    @property
    def status(self) -> str:
        if any(path.name.startswith("test-failed") for path in self.screenshots):
            return "failed"
        if any(path.name.startswith("test-finished") for path in self.screenshots):
            return "finished"
        return "unknown"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    artifacts = sorted(_find_artifacts(), key=lambda item: item.name)
    REPORT_PATH.write_text(_render_report(artifacts), encoding="utf-8")


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


def _render_report(artifacts: list[TestArtifacts]) -> str:
    rows = "\n".join(_render_artifact_card(item) for item in artifacts)
    if not rows:
        rows = (
            """
      <section class="empty-state">
        <h2>No Playwright artifacts found</h2>
        <p>Run <code>make test-e2e</code> to generate screenshots, traces, """
            """and videos.</p>
      </section>
"""
        )

    total = len(artifacts)
    failed = sum(1 for item in artifacts if item.status == "failed")
    finished = sum(1 for item in artifacts if item.status == "finished")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LNbits E2E Playwright Report</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #111827;
      --panel: #1f2937;
      --panel-muted: #273244;
      --border: #374151;
      --text: #f9fafb;
      --muted: #cbd5e1;
      --accent: #f97316;
      --ok: #22c55e;
      --failed: #ef4444;
    }}
    body {{
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
    }}
    header {{
      border-bottom: 1px solid var(--border);
      padding: 28px 32px;
    }}
    h1 {{
      font-size: 28px;
      margin: 0 0 12px;
    }}
    h2 {{
      font-size: 18px;
      margin: 0;
    }}
    code {{
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 4px;
      color: #e5e7eb;
      padding: 2px 5px;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .summary span,
    .badge {{
      background: var(--panel-muted);
      border: 1px solid var(--border);
      border-radius: 999px;
      color: var(--muted);
      display: inline-flex;
      font-size: 13px;
      line-height: 1;
      padding: 7px 10px;
    }}
    .badge--finished {{
      color: var(--ok);
    }}
    .badge--failed {{
      color: var(--failed);
    }}
    main {{
      display: grid;
      gap: 18px;
      padding: 24px 32px 36px;
    }}
    .test-card,
    .empty-state {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
    }}
    .test-card__header {{
      align-items: center;
      border-bottom: 1px solid var(--border);
      display: flex;
      gap: 12px;
      justify-content: space-between;
      padding: 14px 16px;
    }}
    .test-card__name {{
      min-width: 0;
      overflow-wrap: anywhere;
    }}
    .test-card__body {{
      display: grid;
      gap: 16px;
      grid-template-columns: minmax(280px, 1fr) minmax(260px, 420px);
      padding: 16px;
    }}
    .screenshot {{
      display: block;
    }}
    .screenshots {{
      display: grid;
      gap: 14px;
    }}
    .screenshot img {{
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      display: block;
      max-width: 100%;
    }}
    .screenshot-links {{
      color: var(--muted);
      font-size: 13px;
      margin: 8px 0 0;
      overflow-wrap: anywhere;
    }}
    .artifacts {{
      align-content: start;
      display: grid;
      gap: 12px;
    }}
    .artifact-link {{
      color: var(--accent);
      overflow-wrap: anywhere;
      text-decoration: none;
    }}
    .artifact-link:hover {{
      text-decoration: underline;
    }}
    video {{
      background: #0f172a;
      border: 1px solid var(--border);
      border-radius: 6px;
      display: block;
      max-width: 100%;
    }}
    .trace-command {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      margin: 0;
      overflow-x: auto;
      white-space: pre-wrap;
    }}
    .empty-state {{
      padding: 24px;
    }}
    @media (max-width: 900px) {{
      header,
      main {{
        padding-left: 16px;
        padding-right: 16px;
      }}
      .test-card__body {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>LNbits E2E Playwright Report</h1>
    <div class="summary">
      <span>{total} tests</span>
      <span>{finished} finished</span>
      <span>{failed} failed</span>
    </div>
  </header>
  <main>
{rows}
  </main>
</body>
</html>
"""


def _render_artifact_card(artifact: TestArtifacts) -> str:
    status = escape(artifact.status)
    screenshots = _render_screenshots(artifact)
    videos = "\n".join(_render_video(path) for path in artifact.videos)
    traces = "\n".join(_render_trace(path) for path in artifact.traces)
    if not videos:
        videos = "<p>No video artifact.</p>"
    if not traces:
        traces = "<p>No trace artifact.</p>"

    return f"""
    <section class="test-card">
      <div class="test-card__header">
        <h2 class="test-card__name">{escape(artifact.name)}</h2>
        <span class="badge badge--{status}">{status}</span>
      </div>
      <div class="test-card__body">
        <div>
          {screenshots}
        </div>
        <div class="artifacts">
          <div>
            <h3>Video</h3>
            {videos}
          </div>
          <div>
            <h3>Trace</h3>
            {traces}
          </div>
        </div>
      </div>
    </section>
"""


def _render_screenshots(artifact: TestArtifacts) -> str:
    if not artifact.screenshots:
        return "<p>No screenshot artifact.</p>"

    screenshots = "\n".join(
        _render_screenshot(artifact, screenshot) for screenshot in artifact.screenshots
    )
    return f'<div class="screenshots">{screenshots}</div>'


def _render_screenshot(artifact: TestArtifacts, screenshot: Path) -> str:
    href = _href(screenshot)
    alt = escape(artifact.name)
    return (
        f'<a class="screenshot" href="{href}">'
        f'<img src="{href}" alt="{alt} screenshot"></a>'
        f'<p class="screenshot-links">'
        f"{escape(screenshot.name)} · "
        f'<a class="artifact-link" href="{href}">Open PNG</a></p>'
    )


def _render_video(path: Path) -> str:
    href = _href(path)
    size = _file_size(path)
    return (
        f'<video controls preload="metadata" src="{href}"></video>'
        f'<p><a class="artifact-link" href="{href}">{escape(path.name)}</a> '
        f"<span>({size})</span></p>"
    )


def _render_trace(path: Path) -> str:
    href = _href(path)
    size = _file_size(path)
    command = f"uv run playwright show-trace {path.as_posix()}"
    return (
        f'<p><a class="artifact-link" href="{href}">{escape(path.name)}</a> '
        f"<span>({size})</span></p>"
        f'<pre class="trace-command">{escape(command)}</pre>'
    )


def _href(path: Path) -> str:
    relative = path.relative_to(REPORT_DIR)
    return "./" + "/".join(quote(part) for part in relative.parts)


def _screenshot_sort_key(path: Path) -> tuple[int, str]:
    if path.name.startswith("url-"):
        return (0, path.name)
    return (1, path.name)


def _file_size(path: Path) -> str:
    size = path.stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


if __name__ == "__main__":
    main()
