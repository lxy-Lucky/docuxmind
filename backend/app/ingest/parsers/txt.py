"""Plain text parser. Segments into ~80-line blocks with line-range locators."""
from pathlib import Path

BLOCK = 80


def parse(path: str) -> tuple[dict, list[dict]]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    outline = {"kind": "txt", "line_count": len(lines)}

    segments: list[dict] = []
    for i in range(0, len(lines), BLOCK):
        chunk = "\n".join(lines[i : i + BLOCK]).strip()
        if not chunk:
            continue
        start = i + 1
        end = min(i + BLOCK, len(lines))
        segments.append({"locator": f"L{start}-L{end}", "content": chunk})
    return outline, segments
