"""Agent tools — pure functions called by the LLM via tool-calling.

All tools return short strings (truncated). Errors are returned as text starting
with 'Error:' so the model can self-correct rather than crash the loop.
"""
import os
from typing import Any

from app.core.config import settings
from app.db.session import db

MAX_RESULT_CHARS = 3500


def _truncate(t: str, limit: int = MAX_RESULT_CHARS) -> str:
    if len(t) <= limit:
        return t
    return t[:limit] + "\n...(truncated)"


def _fts_quote(s: str) -> str:
    """Wrap user keyword as a phrase to avoid FTS5 syntax surprises."""
    return '"' + s.replace('"', '""') + '"'


# ── Navigation ────────────────────────────────────────────────

def list_folders() -> str:
    with db() as c:
        rows = c.execute(
            """SELECT f.id, f.name,
                      (SELECT COUNT(*) FROM docs d
                         WHERE d.folder_id = f.id AND d.deleted_at IS NULL) AS docs
                 FROM folders f
                WHERE f.deleted_at IS NULL
                ORDER BY f.position"""
        ).fetchall()
    if not rows:
        return "(no folders)"
    return "\n".join(f"[{r['id']}] {r['name']} ({r['docs']} docs)" for r in rows)


def list_docs(folder_id: str | None = None) -> str:
    with db() as c:
        if folder_id:
            rows = c.execute(
                """SELECT id, name, type, status, segment_count
                     FROM docs
                    WHERE folder_id = ? AND deleted_at IS NULL
                    ORDER BY created_at DESC""",
                (folder_id,),
            ).fetchall()
        else:
            rows = c.execute(
                """SELECT id, name, type, status, segment_count
                     FROM docs
                    WHERE deleted_at IS NULL
                    ORDER BY created_at DESC"""
            ).fetchall()
    if not rows:
        return "(no documents)"
    return "\n".join(
        f"[{r['id']}] {r['name']} ({r['type']}, {r['status']}, {r['segment_count']} segs)"
        for r in rows
    )


def get_doc_outline(doc_id: str) -> str:
    with db() as c:
        row = c.execute(
            "SELECT name, type, status, outline_json FROM docs WHERE id = ? AND deleted_at IS NULL",
            (doc_id,),
        ).fetchone()
    if not row:
        return "Error: doc not found"
    if not row["outline_json"]:
        return f"(no outline available; current status: {row['status']})"
    return _truncate(f"{row['name']} ({row['type']})\n{row['outline_json']}")


# ── Reading ───────────────────────────────────────────────────

def read_section(doc_id: str, locator: str) -> str:
    """locator examples:
       - 'sheet=Sheet1|rows=1-40'
       - 'L100-L180'
       - 'heading=Authentication'
       Partial substring matches are accepted; full locator list is returned on miss.
       Fallback: if locator looks like 'L<start>-L<end>' and no segment matches,
       extract the requested line range directly from overlapping segments.
    """
    with db() as c:
        rows = c.execute(
            "SELECT locator, content FROM fts_segments WHERE doc_id = ?",
            (doc_id,),
        ).fetchall()
    if not rows:
        return "Error: no segments indexed for this doc"

    # exact match wins
    for r in rows:
        if r["locator"] == locator:
            return _truncate(r["content"])

    needle = locator.lower()
    matched = [r for r in rows if needle in r["locator"].lower()]
    if matched:
        joined = "\n---\n".join(f"[{r['locator']}]\n{r['content']}" for r in matched[:3])
        return _truncate(joined)

    # ── Fallback: parse L<start>-L<end> and slice from overlapping segments ──
    result = _try_line_range_extract(locator, rows)
    if result:
        return _truncate(result)

    avail = "\n".join(r["locator"] for r in rows[:20])
    return f"Error: no segment matches '{locator}'. Available locators:\n{avail}"


_LINE_RANGE_RE = __import__("re").compile(r"L(\d+)\s*-\s*L(\d+)", __import__("re").IGNORECASE)


def _parse_seg_lines(loc: str) -> tuple[int, int] | None:
    """Extract (start, end) 1-based line numbers from a locator string."""
    m = _LINE_RANGE_RE.search(loc)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def _try_line_range_extract(locator: str, rows: list) -> str | None:
    """If locator is 'L18-L31', reconstruct text from overlapping segments."""
    req = _parse_seg_lines(locator)
    if not req:
        return None
    req_start, req_end = req

    # Collect all segments that have a parseable line range
    candidates: list[tuple[int, int, str]] = []
    for r in rows:
        seg = _parse_seg_lines(r["locator"])
        if seg:
            candidates.append((seg[0], seg[1], r["content"]))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])

    # Find overlapping segments and extract the requested lines
    collected_lines: list[str] = []
    for seg_start, seg_end, content in candidates:
        # No overlap → skip
        if seg_end < req_start or seg_start > req_end:
            continue
        seg_lines = content.splitlines()
        # Calculate which lines within this segment to take
        take_from = max(req_start, seg_start) - seg_start  # 0-based offset into seg_lines
        take_to = min(req_end, seg_end) - seg_start + 1
        collected_lines.extend(seg_lines[take_from:take_to])

    if not collected_lines:
        return None
    return "\n".join(collected_lines)


# ── Searching (FTS5, BM25 ranked) ─────────────────────────────

def _fts_query(filter_sql: str | None, args: tuple, keyword: str) -> str:
    if not keyword.strip():
        return "Error: empty keyword"
    where = ["fts_segments MATCH ?"]
    params: list[Any] = [_fts_quote(keyword)]
    if filter_sql:
        where.append(filter_sql)
        params.extend(args)
    sql = (
        "SELECT doc_id, folder_id, locator, "
        "snippet(fts_segments, 3, '<<', '>>', '...', 18) AS snip "
        "FROM fts_segments WHERE "
        + " AND ".join(where)
        + " ORDER BY rank LIMIT 20"
    )
    with db() as c:
        try:
            rows = c.execute(sql, params).fetchall()
        except Exception as e:
            return f"Error: FTS query failed: {e}"
        if not rows:
            return f"(no hits for '{keyword}')"
        ids = list({r["doc_id"] for r in rows})
        placeholders = ",".join("?" * len(ids))
        name_map = {
            r["id"]: r["name"]
            for r in c.execute(
                f"SELECT id, name FROM docs WHERE id IN ({placeholders})", ids
            ).fetchall()
        }
    lines = [
        f"[{name_map.get(r['doc_id'], r['doc_id'])}] [{r['locator']}] {r['snip']}"
        for r in rows
    ]
    return _truncate("\n".join(lines))


def search_in_doc(doc_id: str, keyword: str) -> str:
    return _fts_query("doc_id = ?", (doc_id,), keyword)


def search_in_folder(folder_id: str, keyword: str) -> str:
    return _fts_query("folder_id = ?", (folder_id,), keyword)


def search_all(keyword: str) -> str:
    return _fts_query(None, (), keyword)


# ── Output ────────────────────────────────────────────────────

def write_report(filename: str, content: str) -> str:
    if any(ch in filename for ch in ("/", "\\", "..", "\x00")):
        return "Error: invalid filename"
    if not filename.strip():
        return "Error: empty filename"
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    path = settings.reports_dir / filename
    if not os.path.realpath(path).startswith(os.path.realpath(settings.reports_dir)):
        return "Error: path traversal blocked"
    path.write_text(content, encoding="utf-8")
    return f"Report saved: {path.name} ({len(content)} chars)"


# ── Registry ──────────────────────────────────────────────────

TOOLS_IMPL = {
    "list_folders": lambda a: list_folders(),
    "list_docs": lambda a: list_docs(a.get("folder_id")),
    "get_doc_outline": lambda a: get_doc_outline(a["doc_id"]),
    "read_section": lambda a: read_section(a["doc_id"], a["locator"]),
    "search_in_doc": lambda a: search_in_doc(a["doc_id"], a["keyword"]),
    "search_in_folder": lambda a: search_in_folder(a["folder_id"], a["keyword"]),
    "search_all": lambda a: search_all(a["keyword"]),
    "write_report": lambda a: write_report(a["filename"], a["content"]),
}


TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "list_folders",
            "description": "列出所有可用文件夹（id, name, 文档数）",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_docs",
            "description": "列出文件夹下的文档（id, name, type, 状态, 段数）。不传 folder_id 则列全部。",
            "parameters": {
                "type": "object",
                "properties": {"folder_id": {"type": "string"}},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_doc_outline",
            "description": "获取文档结构大纲（sheet 列表 / 章节 / 行数）。接触任何新文档时必须先调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {"doc_id": {"type": "string"}},
                "required": ["doc_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_section",
            "description": "按定位读取文档段落。locator 必须来自 get_doc_outline 或 search 返回的真实 locator，禁止自行构造行号。示例：'sheet=Sheet1|rows=1-40' / 'L1-L17 | import React...' / 'heading=认证'",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "locator": {"type": "string"},
                },
                "required": ["doc_id", "locator"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_doc",
            "description": "在单个文档中关键词检索（FTS5 BM25 排序）",
            "parameters": {
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "keyword": {"type": "string"},
                },
                "required": ["doc_id", "keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_in_folder",
            "description": "在指定文件夹中跨文档关键词检索",
            "parameters": {
                "type": "object",
                "properties": {
                    "folder_id": {"type": "string"},
                    "keyword": {"type": "string"},
                },
                "required": ["folder_id", "keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_all",
            "description": "在所有文档中跨文件关键词检索",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string"}},
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_report",
            "description": "将最终分析结果写入报告文件（保存到 reports 目录）。完成任务前必须调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["filename", "content"],
            },
        },
    },
]
