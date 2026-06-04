from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent.runtime import ChatRequest, run_agent

router = APIRouter(tags=["chat"])


class ChatBody(BaseModel):
    question: str
    scope_mode: str = "all"
    scope_id: str | None = None
    scope_name: str | None = None
    session_id: str | None = None


@router.post("/chat")
async def chat(body: ChatBody, request: Request):
    req = ChatRequest(
        question=body.question.strip(),
        scope_mode=body.scope_mode,
        scope_id=body.scope_id,
        scope_name=body.scope_name,
        session_id=body.session_id,
    )

    async def gen():
        async for chunk in run_agent(req):
            if await request.is_disconnected():
                break
            yield chunk

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
