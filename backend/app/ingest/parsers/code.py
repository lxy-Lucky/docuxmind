"""Source code parser (JS/TS/Java). Segments by top-level declarations."""
import re
from pathlib import Path

# Patterns that mark a new segment boundary (top-level or class-level declarations).
# We match the *start* of a declaration; the segment runs until the next boundary.
_BOUNDARY_PATTERNS = [
    # Java / JS / TS — class / interface / enum
    re.compile(
        r"^(?:export\s+)?(?:public|private|protected|abstract|static|final|default)?\s*"
        r"(?:class|interface|enum)\s+\w+",
        re.MULTILINE,
    ),
    # Java method  —  <modifiers> <type> name(
    re.compile(
        r"^[ \t]*(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?"
        r"(?:(?:synchronized|native|abstract)\s+)?[\w<>\[\],\s]+\s+\w+\s*\(",
        re.MULTILINE,
    ),
    # JS/TS — function / arrow const / export function
    re.compile(
        r"^(?:export\s+)?(?:async\s+)?function\s+\w+",
        re.MULTILINE,
    ),
    re.compile(
        r"^(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?\(",
        re.MULTILINE,
    ),
    # JS/TS class method  —  async? name(  or  get/set name(
    re.compile(
        r"^[ \t]+(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?(?!if|else|for|while|switch|return|new|throw|catch)\w+\s*\(",
        re.MULTILINE,
    ),
]

BLOCK = 80  # fallback chunk size when no declarations are found


def _find_boundaries(text: str) -> list[int]:
    """Return sorted, deduplicated line numbers (0-based) that open a new segment."""
    hits: set[int] = set()
    for pat in _BOUNDARY_PATTERNS:
        for m in pat.finditer(text):
            lineno = text.count("\n", 0, m.start())
            hits.add(lineno)
    return sorted(hits)


def parse(path: str) -> tuple[dict, list[dict]]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    if not lines:
        return {"kind": "code", "line_count": 0, "declarations": []}, []

    boundaries = _find_boundaries(text)

    # If too few boundaries detected, fall back to fixed-size blocks (like txt parser).
    if len(boundaries) < 2:
        return _fallback_parse(lines)

    # Ensure line 0 is a boundary so the file header (imports etc.) forms its own segment.
    if boundaries[0] != 0:
        boundaries.insert(0, 0)
    boundaries.append(len(lines))  # sentinel

    # Build outline from boundary lines
    declarations: list[dict] = []
    for b in boundaries[:-1]:
        label = lines[b].strip() if b < len(lines) else ""
        if label:
            declarations.append({"line": b + 1, "text": label[:120]})

    outline = {
        "kind": "code",
        "line_count": len(lines),
        "declarations": declarations,
    }

    segments: list[dict] = []
    for a, b in zip(boundaries, boundaries[1:]):
        chunk = "\n".join(lines[a:b]).strip()
        if not chunk:
            continue
        # Use the first meaningful line as locator label
        first_line = lines[a].strip()[:80]
        locator = f"L{a+1}-L{b} | {first_line}" if first_line else f"L{a+1}-L{b}"
        segments.append({"locator": locator, "content": chunk})

    return outline, segments


def _fallback_parse(lines: list[str]) -> tuple[dict, list[dict]]:
    """Fixed-size block segmentation when declaration detection is sparse."""
    outline = {"kind": "code", "line_count": len(lines), "declarations": []}
    segments: list[dict] = []
    for i in range(0, len(lines), BLOCK):
        chunk = "\n".join(lines[i : i + BLOCK]).strip()
        if not chunk:
            continue
        start = i + 1
        end = min(i + BLOCK, len(lines))
        segments.append({"locator": f"L{start}-L{end}", "content": chunk})
    return outline, segments
