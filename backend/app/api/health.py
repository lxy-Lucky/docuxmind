from fastapi import APIRouter

from app.core.config import settings
from app.llm.provider import get_provider

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health():
    provider = get_provider()
    llm_ok = await provider.health()
    return {
        "ok": True,
        "llm": {
            "provider": provider.name,
            "model": provider.model,
            "ready": llm_ok,
        },
        "data_dir": str(settings.data_dir.resolve()),
    }
