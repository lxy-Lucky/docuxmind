"""Agent tools — pure functions called by the LLM via tool-calling.

All tools return short strings (truncated). Errors are returned as text starting
with 'Error:' so the model can self-correct rather than crash the loop.
"""
import os
from typing import Any

from app.core.config import settings
from app.db.session import db

MAX_RESULT_CHARS = 3500
SNIPPET_WINDOW = 40  # chars of context shown around a LIKE-matched substring


def _truncate(t: str, limit: int = MAX_RESULT_CHARS) -> str:
    if len(t) <= limit:
        return t
    return t[:limit] + "\n...(truncated)"


def _fts_quote(s: str) -> str:
    """Wrap user keyword as a phrase to avoid FTS5 syntax surprises."""
    return '"' + s.replace('"', '""') + '"'


def _like_escape(s: str) -> str:
    """Escape LIKE wildcards so the keyword is matched literally (ESCAPE '\\')."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _manual_snip(content: str, keyword: str) -> str | None:
    """Build a small <<>>-marked snippet around the first match of keyword.

    Returns None if the keyword is not present in the content (e.g. it only
    matched the locator / sheet title).
    """
    if not content:
        return None
    low = content.lower()
    k = keyword.lower()
    i = low.find(k)
    if i < 0:
        return None
    s = max(0, i - SNIPPET_WINDOW)
    e = min(len(content), i + len(keyword) + SNIPPET_WINDOW)
    body = (
        content[s:i] + "<<" + content[i : i + len(keyword)] + ">>" + content[i + len(keyword) : e]
    )
    body = body.replace("\n", " ").strip()
    return ("..." if s > 0 else "") + body + ("..." if e < len(content) else "")


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
    if not matched:
        avail = "\n".join(r["locator"] for r in rows[:20])
        return f"Error: no segment matches '{locator}'. Available locators:\n{avail}"
    joined = "\n---\n".join(f"[{r['locator']}]\n{r['content']}" for r in matched[:3])
    return _truncate(joined)


# ── Searching (FTS5 BM25, with LIKE fallback for titles / CJK substrings) ─────

def _fts_query(filter_sql: str | None, args: tuple, keyword: str) -> str:
    """Keyword search combining two passes, de-duplicated by (doc_id, locator):

      1. FTS5 MATCH over content — ranked (BM25), primary results.
      2. LIKE fallback over locator + content — catches sheet/section *titles*
         (which live in the locator, not the content) and CJK substrings that
         the FTS tokenizer can't segment (e.g. '显存' inside '剩余显存空间').

    The LIKE pass is a table scan; fine for a local KB. FTS hits are listed
    first so ranking is preserved; LIKE-only hits are appended.
    """
    if not keyword.strip():
        return "Error: empty keyword"
    keyword = keyword.strip()

    seen: set[tuple[str, str]] = set()
    hits: list[tuple[str, str, str]] = []  # (doc_id, locator, snippet)
    fts_err: str | None = None

    with db() as c:
        # ── pass 1: FTS5 MATCH (ranked) ──
        where = ["fts_segments MATCH ?"]
        params: list[Any] = [_fts_quote(keyword)]
        if filter_sql:
            where.append(filter_sql)
            params.extend(args)
        sql = (
            "SELECT doc_id, locator, "
            "snippet(fts_segments, 3, '<<', '>>', '...', 18) AS snip "
            "FROM fts_segments WHERE "
            + " AND ".join(where)
            + " ORDER BY rank LIMIT 20"
        )
        try:
            for r in c.execute(sql, params).fetchall():
                key = (r["doc_id"], r["locator"])
                if key in seen:
                    continue
                seen.add(key)
                hits.append((r["doc_id"], r["locator"], r["snip"]))
        except Exception as e:
            fts_err = str(e)  # don't bail — LIKE pass may still find it

        # ── pass 2: LIKE fallback (locator + content) ──
        if len(hits) < 20:
            pat = f"%{_like_escape(keyword)}%"
            lwhere = ["(locator LIKE ? ESCAPE '\\' OR content LIKE ? ESCAPE '\\')"]
            lparams: list[Any] = [pat, pat]
            if filter_sql:
                lwhere.append(filter_sql)
                lparams.extend(args)
            lsql = (
                "SELECT doc_id, locator, content FROM fts_segments WHERE "
                + " AND ".join(lwhere)
                + " LIMIT 40"
            )
            try:
                for r in c.execute(lsql, lparams).fetchall():
                    key = (r["doc_id"], r["locator"])
                    if key in seen:
                        continue
                    seen.add(key)
                    snip = _manual_snip(r["content"] or "", keyword)
                    if snip is None:
                        # matched the locator only → it's a sheet/section title
                        snip = "(命中表名/章节标题)"
                    hits.append((r["doc_id"], r["locator"], snip))
                    if len(hits) >= 20:
                        break
            except Exception:
                pass  # LIKE fallback is best-effort

        if not hits:
            if fts_err:
                return f"Error: FTS query failed: {fts_err}"
            return f"(no hits for '{keyword}')"

        ids = list({d for d, _, _ in hits})
        placeholders = ",".join("?" * len(ids))
        name_map = {
            r["id"]: r["name"]
            for r in c.execute(
                f"SELECT id, name FROM docs WHERE id IN ({placeholders})", ids
            ).fetchall()
        }

    lines = [f"[{name_map.get(d, d)}] [{loc}] {snip}" for d, loc, snip in hits[:20]]
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
            "description": "按定位读取文档段落。locator 示例：'sheet=Sheet1|rows=1-40' 或 'L100-L180' 或 'heading=认证'",
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
            "description": "在单个文档中关键词检索（FTS5 BM25 排序；同时匹配表名/章节标题与正文）",
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
            "description": "在指定文件夹中跨文档关键词检索（同时匹配表名/章节标题与正文）",
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
            "description": "在所有文档中跨文件关键词检索（同时匹配表名/章节标题与正文）",
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