from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookPayload(BaseModel):
    provider: str
    event_id: str | None = None
    payload: dict | None = None


@router.post("/email")
async def webhook_email(payload: WebhookPayload):
    if payload.provider != "email":
        raise HTTPException(status_code=400, detail="Invalid provider")
    return {"status": "received"}


@router.post("/whatsapp")
async def webhook_whatsapp(payload: WebhookPayload):
    if payload.provider != "whatsapp":
        raise HTTPException(status_code=400, detail="Invalid provider")
    return {"status": "received"}
