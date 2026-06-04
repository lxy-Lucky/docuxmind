import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.session import db

router = APIRouter(tags=["sessions"])


class SessionCreate(BaseModel):
    title: str | None = None
    scope_mode: str = "all"
    scope_id: str | None = None


class TitleUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=80)


@router.get("/sessions")
def list_sessions():
    with db() as c:
        rows = c.execute(
            """SELECT s.id, s.title, s.scope_mode, s.scope_id, s.created_at,
                      (SELECT COUNT(*) FROM chat_messages m WHERE m.session_id = s.id) AS msg_count,
                      (SELECT MAX(m.created_at) FROM chat_messages m WHERE m.session_id = s.id) AS last_at
                 FROM chat_sessions s
                ORDER BY COALESCE(
                    (SELECT MAX(m.created_at) FROM chat_messages m WHERE m.session_id = s.id),
                    s.created_at
                ) DESC
                LIMIT 100"""
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/sessions")
def create_session(body: SessionCreate):
    sid = "s_" + uuid.uuid4().hex[:12]
    with db() as c:
        c.execute(
            "INSERT INTO chat_sessions(id, title, scope_mode, scope_id) VALUES (?, ?, ?, ?)",
            (sid, body.title, body.scope_mode, body.scope_id),
        )
    return {"id": sid, "title": body.title, "scope_mode": body.scope_mode, "scope_id": body.scope_id}


@router.get("/sessions/{sid}/messages")
def get_messages(sid: str):
    with db() as c:
        sess = c.execute(
            "SELECT id, title, scope_mode, scope_id FROM chat_sessions WHERE id = ?",
            (sid,),
        ).fetchone()
        if not sess:
            raise HTTPException(404, "session not found")
        rows = c.execute(
            """SELECT id, role, content, trace_json, created_at
                 FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at ASC""",
            (sid,),
        ).fetchall()
    return {"session": dict(sess), "messages": [dict(r) for r in rows]}


@router.patch("/sessions/{sid}")
def rename(sid: str, body: TitleUpdate):
    with db() as c:
        cur = c.execute(
            "UPDATE chat_sessions SET title = ? WHERE id = ?",
            (body.title.strip(), sid),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "session not found")
    return {"ok": True}


@router.delete("/sessions/{sid}")
def remove(sid: str):
    with db() as c:
        c.execute("DELETE FROM chat_messages WHERE session_id = ?", (sid,))
        cur = c.execute("DELETE FROM chat_sessions WHERE id = ?", (sid,))
        if cur.rowcount == 0:
            raise HTTPException(404, "session not found")
    return {"ok": True}
