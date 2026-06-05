"""Agent loop. Emits SSE events:

  event: start         { trace_id }
  event: step          { n }
  event: tool_call     { name, args }
  event: tool_result   { name, result }   # truncated
  event: token         { text }           # intermediate model prose (rare)
  event: answer        { content, report_file? }
  event: done          { trace_id, total_tokens, steps }
  event: error         { reason, message? }

Convergence notes (added for small / weaker models):
  - Identical tool calls are de-duplicated and served from cache; repeats past a
    threshold force the loop into "finalize" mode.
  - Plain prose without [DONE] is tolerated only a few times, then accepted as
    the final answer instead of being nudged forever.
  - Near the step budget the loop enters "finalize" mode: only `write_report`
    is exposed and the model is told to write the report now.
  - If the budget is still exhausted, one last tool-free call produces a partial
    report from whatever was retrieved, so the user always gets something.
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

# --- convergence knobs (move to settings if you want them configurable) ---
REPORT_TOOL = "write_report"
FINALIZE_MARGIN = 2     # reserve the last N steps to force report writing
DUP_CALL_LIMIT = 3      # same tool+args seen this many times -> force finalize
                        # (>=3 so one legitimate re-orient retry isn't punished)
MAX_PROSE_NUDGES = 2    # plain prose w/o [DONE] tolerated before accepting it

FINALIZE_HINT = (
    "步骤预算即将用尽。请不要再检索，直接根据已获得的信息，"
    "立即调用 write_report 保存最终报告，并在正文末尾加上 [DONE] 标记。"
)
NUDGE_HINT = (
    "请继续完成任务，必要时调用工具，完成后用 write_report 保存报告并加上 [DONE] 标记。"
)
LAST_RESORT_HINT = (
    "已达到步骤上限。请立即用中文，根据以上已检索到的信息输出一份尽可能完整的"
    "最终报告，不要再调用任何工具。"
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


def _spec_name(t: Any) -> str | None:
    """Best-effort extraction of a tool's name from a spec entry (OpenAI style)."""
    if isinstance(t, dict):
        return (t.get("function") or {}).get("name") or t.get("name")
    return None


# Tools spec restricted to just the report tool, used in finalize mode so the
# model is forced to converge instead of issuing more retrieval calls.
REPORT_ONLY_SPEC = [t for t in TOOLS_SPEC if _spec_name(t) == REPORT_TOOL] or TOOLS_SPEC


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

    # --- convergence state ---
    seen_calls: dict[str, str] = {}    # signature -> cached result
    dup_counts: dict[str, int] = {}    # signature -> times seen
    prose_nudges = 0                   # consecutive prose-without-[DONE] turns
    finalize_forced = False            # set when repeats/loops are detected
    finalize_announced = False         # FINALIZE_HINT injected at most once

    for step in range(1, settings.agent_max_steps + 1):
        steps_used = step
        yield _sse("step", {"n": step})

        # Enter finalize mode near the budget, or when a loop was detected.
        remaining = settings.agent_max_steps - step
        in_finalize = finalize_forced or remaining <= FINALIZE_MARGIN

        if in_finalize and not finalize_announced:
            messages.append({"role": "user", "content": FINALIZE_HINT})
            finalize_announced = True

        step_tools = REPORT_ONLY_SPEC if in_finalize else TOOLS_SPEC

        try:
            resp = await asyncio.wait_for(
                provider.chat(messages=messages, tools=step_tools),
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
            content = (msg.content or "").strip()
            if "[DONE]" in content:
                final = content.replace("[DONE]", "").strip()
                yield _sse("answer", {"content": final})
                yield _sse(
                    "done",
                    {"trace_id": trace_id, "total_tokens": total_tokens, "steps": steps_used},
                )
                _persist_assistant(req, final, trace_id, steps_used, total_tokens, "done")
                return

            prose_nudges += 1
            force_stop = in_finalize or prose_nudges >= MAX_PROSE_NUDGES

            if force_stop and content:
                # Model keeps producing prose (or we're finalizing) and it has
                # real text — accept it as the answer instead of burning budget.
                yield _sse("answer", {"content": content})
                yield _sse(
                    "done",
                    {"trace_id": trace_id, "total_tokens": total_tokens, "steps": steps_used},
                )
                _persist_assistant(req, content, trace_id, steps_used, total_tokens, "done")
                return

            if force_stop and not content:
                # Model gave up / returned an empty message. Do NOT emit
                # "(no content)" — fall through to the last-resort salvage,
                # which forces a tool-free summary from what was retrieved.
                break

            # Still have budget: nudge and keep going.
            if content:
                messages.append({"role": "assistant", "content": content})
                yield _sse("token", {"text": content})
            messages.append({"role": "user", "content": NUDGE_HINT})
            continue

        # Has tool calls — execute each, send results back to the model.
        prose_nudges = 0  # progress was made
        messages.append(msg.model_dump(exclude_none=True))
        for tc in tool_calls:
            fn = tc.function
            fn_name = fn.name
            try:
                fn_args = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError as e:
                fn_args = {}
                result = f"Error: invalid JSON arguments: {e}"
                yield _sse("tool_call", {"name": fn_name, "args": {}, "error": "bad_json"})
                yield _sse("tool_result", {"name": fn_name, "result": result[:TOOL_RESULT_CLIP]})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                continue

            yield _sse("tool_call", {"name": fn_name, "args": fn_args})

            # De-duplicate identical retrieval calls. write_report is terminal
            # and content-dependent, so it is never cached.
            sig = f"{fn_name}:{json.dumps(fn_args, sort_keys=True, ensure_ascii=False)}"
            if fn_name != REPORT_TOOL and sig in seen_calls:
                dup_counts[sig] = dup_counts.get(sig, 1) + 1
                result = (
                    "[重复调用] 该工具已用相同参数调用过，结果见下方。"
                    "请勿重复检索，基于现有信息继续并尽快用 write_report 写报告。\n\n"
                    + seen_calls[sig]
                )
                if dup_counts[sig] >= DUP_CALL_LIMIT:
                    finalize_forced = True
            else:
                result = await _exec_tool(fn_name, fn_args)
                if fn_name != REPORT_TOOL:
                    seen_calls[sig] = result
                    dup_counts[sig] = 1

            yield _sse("tool_result", {"name": fn_name, "result": result[:TOOL_RESULT_CLIP]})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

            if fn_name == REPORT_TOOL and not result.startswith("Error"):
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

    # --- budget exhausted: salvage a partial report instead of erroring out ---
    messages.append({"role": "user", "content": LAST_RESORT_HINT})
    try:
        resp = await asyncio.wait_for(
            provider.chat(messages=messages, tools=[]),
            timeout=settings.agent_step_timeout_sec,
        )
        final = (resp.choices[0].message.content or "").replace("[DONE]", "").strip()
    except Exception as e:
        log.warning("agent.last_resort.failed", trace_id=trace_id, error=str(e))
        final = ""

    if final:
        yield _sse("answer", {"content": final})
        yield _sse(
            "done",
            {"trace_id": trace_id, "total_tokens": total_tokens, "steps": steps_used},
        )
        _persist_assistant(req, final, trace_id, steps_used, total_tokens, "partial")
        return

    yield _sse("error", {"reason": "max_steps_reached"})
    _persist_assistant(req, "(max steps reached)", trace_id, steps_used, total_tokens, "error")