from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
async def global_search(q: str = Query(..., min_length=1)):
    return {
        "query": q,
        "items": [],
        "total": 0,
    }
