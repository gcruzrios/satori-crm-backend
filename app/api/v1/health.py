from fastapi import APIRouter

from app.core.database import test_db_connection

router = APIRouter(tags=["health"]) 


@router.get("/health")
async def health_check() -> dict[str, str | bool]:
    db_ok = await test_db_connection()
    return {"status": "ok", "database": db_ok}
