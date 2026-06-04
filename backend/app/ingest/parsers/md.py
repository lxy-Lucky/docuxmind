"""Markdown parser. Builds heading tree + segments at H1/H2 boundaries."""
import re
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def parse(path: str) -> tuple[dict, list[dict]]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    headings: list[dict] = []
    for i, line in enumerate(lines):
        m = HEADING_RE.match(line)
        if m:
            headings.append(
                {"level": len(m.group(1)), "title": m.group(2).strip(), "line": i + 1}
            )

    outline = {"kind": "md", "headings": headings}

    # Segment boundaries = every H1/H2 line; trailing sentinel = len+1
    bounds = [h["line"] for h in headings if h["level"] <= 2]
    if not bounds or bounds[0] != 1:
        bounds.insert(0, 1)
    bounds.append(len(lines) + 1)

    # Title for each segment = the heading that opens it (if any)
    title_by_line = {h["line"]: h["title"] for h in headings}

    segments: list[dict] = []
    for a, b in zip(bounds, bounds[1:]):
        chunk = "\n".join(lines[a - 1 : b - 1]).strip()
        if not chunk:
            continue
        title = title_by_line.get(a, "")
        locator = f"heading={title}" if title else f"L{a}-L{b-1}"
        segments.append({"locator": locator, "content": chunk})

    return outline, segments
