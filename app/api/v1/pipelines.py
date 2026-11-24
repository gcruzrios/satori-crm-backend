from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crud import apply_updates, get_active_or_404, partial_model
from app.core.database import get_db
from app.models.pipeline import Pipeline, PipelineStage

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class PipelineCreate(BaseModel):
    name: str
    description: str | None = None
    pipeline_type: str = "b2c"
    is_default: bool = False
    is_active: bool = True



PipelineUpdate = partial_model(PipelineCreate, "PipelineUpdate")

class PipelineStageCreate(BaseModel):
    name: str
    stage_order: int
    probability: int = 0
    color: str | None = None
    is_won: bool = False
    is_lost: bool = False


def _iso(v):
    return v.isoformat() if v is not None else None


def _serialize_pipeline(p: Pipeline) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "pipeline_type": p.pipeline_type,
        "is_default": p.is_default,
        "is_active": p.is_active,
        "created_at": _iso(p.created_at),
        "updated_at": _iso(p.updated_at),
    }


def _serialize_stage(st: PipelineStage) -> dict:
    return {
        "id": str(st.id),
        "pipeline_id": str(st.pipeline_id),
        "name": st.name,
        "stage_order": st.stage_order,
        "probability": st.probability,
        "color": st.color,
        "is_won": st.is_won,
        "is_lost": st.is_lost,
        "created_at": _iso(st.created_at),
    }


@router.get("")
async def list_pipelines(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pipeline))
    items = result.scalars().all()
    return {"items": [_serialize_pipeline(item) for item in items]}


@router.post("")
async def create_pipeline(payload: PipelineCreate, db: AsyncSession = Depends(get_db)):
    pipeline = Pipeline(**payload.model_dump(exclude_none=True))
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return {"id": str(pipeline.id), "status": "created"}


@router.get("/{pipeline_id}")
async def get_pipeline(pipeline_id: UUID, db: AsyncSession = Depends(get_db)):
    pipeline = await get_active_or_404(db, Pipeline, pipeline_id, "Pipeline")
    return _serialize_pipeline(pipeline)


@router.put("/{pipeline_id}")
async def update_pipeline(pipeline_id: UUID, payload: PipelineUpdate, db: AsyncSession = Depends(get_db)):
    pipeline = await get_active_or_404(db, Pipeline, pipeline_id, "Pipeline")
    apply_updates(pipeline, payload)
    await db.commit()
    return {"status": "updated"}


@router.get("/{pipeline_id}/stages")
async def list_pipeline_stages(pipeline_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PipelineStage).where(PipelineStage.pipeline_id == pipeline_id).order_by(PipelineStage.stage_order))
    items = result.scalars().all()
    return {"items": [_serialize_stage(item) for item in items]}


@router.post("/{pipeline_id}/stages")
async def create_pipeline_stage(pipeline_id: UUID, payload: PipelineStageCreate, db: AsyncSession = Depends(get_db)):
    await get_active_or_404(db, Pipeline, pipeline_id, "Pipeline")
    stage = PipelineStage(pipeline_id=pipeline_id, **payload.model_dump(exclude_none=True))
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    return {"id": str(stage.id), "status": "created"}
