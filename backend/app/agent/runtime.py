"""Agent loop. Emits SSE events:

  event: start         { trace_id }
  event: step          { n }
  event: tool_call     { name, args }
  event: tool_result   { name, result }   # truncated
  event: token         { text }           # intermediate model prose (rare)
  event: answer        { content, report_file? }
  event: done          { trace_id, total_tokens, steps }
  event: error         { reason, message? }
"""
from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator

from app.agent.prompts import SYSTEM_PROMPT, scope_prefix
from app.agent.tools import TOOLS_IMPL, TOOLS_SPEC
from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import db
from app.llm.provider import get_provider

log = get_logger("agent")

TOOL_RESULT_CLIP = 1200  # bytes shown to the UI per tool_result event

# ── Context window management ─────────────────────────────────
# Keep the last KEEP_RECENT_TOOL_ROUNDS of tool exchanges in full.
# Older tool results are compressed to a short summary to prevent
# the messages list from growing unboundedly on long analysis runs.
KEEP_RECENT_TOOL_ROUNDS = 4          # full-detail exchanges to retain
COMPRESS_RESULT_CHARS = 200          # truncated length for old results


def _compress_old_tool_results(messages: list[dict[str, Any]]) -> None:
    """In-place: shorten tool-result content for older rounds.

    We walk backwards, count tool-result messages, and once we've passed
    the KEEP_RECENT_TOOL_ROUNDS threshold, truncate earlier ones.
    System + user messages are never touched.
    """
    tool_result_indices: list[int] = []
    for i, m in enumerate(messages):
        if m.get("role") == "tool":
            tool_result_indices.append(i)

    if len(tool_result_indices) <= KEEP_RECENT_TOOL_ROUNDS:
        return

    to_compress = tool_result_indices[: -KEEP_RECENT_TOOL_ROUNDS]
    for i in to_compress:
        content = messages[i].get("content", "")
        if len(content) > COMPRESS_RESULT_CHARS:
            messages[i]["content"] = (
                content[:COMPRESS_RESULT_CHARS] + "\n...(earlier result compressed)"
            )


@dataclass
class ChatRequest:
    question: str
    scope_mode: str = "all"          # 'all' | 'folder'
    scope_id: str | None = None
    scope_name: str | None = None
    session_id: str | None = None


async def _exec_tool(name: str, args: dict[str, Any]) -> str:
    fn = TOOLS_IMPL.get(name)
    if not fn:
        return f"Error: unknown tool '{name}'"
    try:
        return await asyncio.to_thread(fn, args)
    except KeyError as e:
        return f"Error: missing argument {e}"
    except Exception as e:
        return f"Error: tool '{name}' failed: {e}"


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _persist_user(req: ChatRequest) -> None:
    """Save the user's question immediately so refresh/cancel doesn't lose it."""
    if not req.session_id:
        return
    try:
        with db() as c:
            # auto-title from first question (≤40 chars), only set if title is NULL
            c.execute(
                "INSERT OR IGNORE INTO chat_sessions(id, title, scope_mode, scope_id) VALUES (?, ?, ?, ?)",
                (req.session_id, req.question[:40], req.scope_mode, req.scope_id),
            )
            c.execute(
                "UPDATE chat_sessions SET title = COALESCE(title, ?) WHERE id = ?",
                (req.question[:40], req.session_id),
            )
            c.execute(
                "INSERT INTO chat_messages(id, session_id, role, content) VALUES (?, ?, ?, ?)",
                (uuid.uuid4().hex[:12], req.session_id, "user", req.question),
            )
    except Exception as e:
        log.warning("persist_user.failed", error=str(e))


def _persist_assistant(
    req: ChatRequest,
    content: str,
    trace_id: str,
    steps: int,
    tokens: int,
    status: str,
    report_file: str | None = None,
) -> None:
    try:
        with db() as c:
            c.execute(
                "INSERT INTO agent_runs(id, session_id, trace_id, status, steps, total_tokens, finished_at) "
                "VALUES (?, ?, ?, ?, ?, ?, datetime('now'))",
                (uuid.uuid4().hex[:12], req.session_id, trace_id, status, steps, tokens),
            )
            if req.session_id:
                c.execute(
                    "INSERT INTO chat_messages(id, session_id, role, content, trace_json) VALUES (?, ?, ?, ?, ?)",
                    (
                        uuid.uuid4().hex[:12],
                        req.session_id,
                        "assistant",
                        content,
                        json.dumps(
                            {
                                "trace_id": trace_id,
                                "status": status,
                                "report_file": report_file,
                            }
                        ),
                    ),
                )
    except Exception as e:
        log.warning("persist_assistant.failed", error=str(e))


async def run_agent(req: ChatRequest) -> AsyncIterator[str]:
    trace_id = uuid.uuid4().hex[:12]
    log.info("agent.start", trace_id=trace_id, scope=req.scope_mode)

    # Save the user's question now — survives refresh / cancel / crash.
    _persist_user(req)

    prefix = scope_prefix(req.scope_mode, req.scope_id, req.scope_name)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prefix + req.question},
    ]

    yield _sse("start", {"trace_id": trace_id})

    provider = get_provider()
    total_tokens = 0
    steps_used = 0

    for step in range(1, settings.agent_max_steps + 1):
        steps_used = step
        yield _sse("step", {"n": step})

        # Compress old tool results to keep prompt size manageable.
        _compress_old_tool_results(messages)

        try:
            resp = await asyncio.wait_for(
                provider.chat(messages=messages, tools=TOOLS_SPEC),
                timeout=settings.agent_step_timeout_sec,
            )
        except asyncio.TimeoutError:
            yield _sse("error", {"reason": "llm_timeout", "step": step})
            _persist_assistant(req, "(LLM timeout)", trace_id, steps_used, total_tokens, "error")
            return
        except Exception as e:
            log.error("agent.llm_error", trace_id=trace_id, error=str(e))
            yield _sse("error", {"reason": "llm_error", "message": str(e), "step": step})
            _persist_assistant(req, f"(LLM error: {e})", trace_id, steps_used, total_tokens, "error")
            return

        msg = resp.choices[0].message
        usage = getattr(resp, "usage", None)
        if usage is not None:
            total_tokens += getattr(usage, "total_tokens", 0) or 0
            if total_tokens > settings.agent_total_token_limit:
                yield _sse("error", {"reason": "token_limit", "tokens": total_tokens})
                _persist_assistant(req, "(token limit)", trace_id, steps_used, total_tokens, "error")
                return

        tool_calls = msg.tool_calls or []

        if not tool_calls:
            content = msg.content or ""
            if "[DONE]" in content:
                final = content.replace("[DONE]", "").strip()
                yield _sse("answer", {"content": final})
                yield _sse(
                    "done",
                    {"trace_id": trace_id, "total_tokens": total_tokens, "steps": steps_used},
                )
                _persist_assistant(req, final, trace_id, steps_used, total_tokens, "done")
                return
            # Model gave plain prose without [DONE] — nudge it.
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": "请继续完成任务，必要时调用工具，完成后用 write_report 保存报告并加上 [DONE] 标记。",
                }
            )
            yield _sse("token", {"text": content})
            continue

        # Has tool calls — execute each, send results back to the model.
        messages.append(msg.model_dump(exclude_none=True))
        for tc in tool_calls:
            fn = tc.function
            fn_name = fn.name
            try:
                fn_args = json.loads(fn.arguments or "{}")
                yield _sse("tool_call", {"name": fn_name, "args": fn_args})
                result = await _exec_tool(fn_name, fn_args)
            except json.JSONDecodeError as e:
                fn_args = {}
                result = f"Error: invalid JSON arguments: {e}"
                yield _sse("tool_call", {"name": fn_name, "args": {}, "error": "bad_json"})

            yield _sse("tool_result", {"name": fn_name, "result": result[:TOOL_RESULT_CLIP]})
            messages.append(
                {"role": "tool", "tool_call_id": tc.id, "content": result}
            )

            if fn_name == "write_report" and not result.startswith("Error"):
                # The report content is the markdown the LLM just wrote — use it
                # as the visible answer instead of the "Report saved: ..." line.
                report_md = (fn_args.get("content") or "").strip()
                report_file = fn_args.get("filename") or ""
                final = report_md or f"报告已保存：{result}"
                yield _sse("answer", {"content": final, "report_file": report_file})
                yield _sse(
                    "done",
                    {"trace_id": trace_id, "total_tokens": total_tokens, "steps": steps_used},
                )
                _persist_assistant(
                    req, final, trace_id, steps_used, total_tokens, "done", report_file
                )
                return

    yield _sse("error", {"reason": "max_steps_reached"})
    _persist_assistant(req, "(max steps reached)", trace_id, steps_used, total_tokens, "error")
