from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings
from app.llm.provider import get_provider, set_provider

router = APIRouter(tags=["settings"])


class SettingsView(BaseModel):
    llm_provider: str
    mimo_model: str
    lmstudio_model: str
    mimo_base_url: str
    lmstudio_base_url: str


@router.get("/settings")
def view():
    return SettingsView(
        llm_provider=settings.llm_provider,
        mimo_model=settings.mimo_model,
        lmstudio_model=settings.lmstudio_model,
        mimo_base_url=settings.mimo_base_url,
        lmstudio_base_url=settings.lmstudio_base_url,
    )


class ProviderSwitch(BaseModel):
    provider: str


@router.post("/settings/provider")
def switch(body: ProviderSwitch):
    if body.provider not in ("mimo", "lmstudio"):
        raise HTTPException(422, "invalid provider")
    p = set_provider(body.provider)
    return {"ok": True, "current": p.name, "model": p.model}


@router.post("/settings/llm_check")
async def llm_check():
    """Tiny capability test: ask the model to invoke list_folders.

    For local LM Studio with weaker base models this often surfaces silently —
    we want a single button that flips green/red.
    """
    provider = get_provider()
    try:
        resp = await provider.chat(
            messages=[
                {"role": "system", "content": "你必须通过调用工具完成任务，不能直接回答。"},
                {"role": "user", "content": "调用 list_folders 看一下当前的文件夹列表。"},
            ],
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "list_folders",
                        "description": "list folders",
                        "parameters": {
                            "type": "object",
                            "properties": {},
                            "required": [],
                        },
                    },
                }
            ],
        )
        tc = resp.choices[0].message.tool_calls or []
        return {"ok": bool(tc), "tool_calls": len(tc), "model": provider.model}
    except Exception as e:
        return {"ok": False, "error": str(e), "model": provider.model}
