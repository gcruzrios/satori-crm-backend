from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.pipeline import Pipeline, PipelineStage

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


class PipelineCreate(BaseModel):
    name: str
    description: str | None = None
    pipeline_type: str = "b2c"
    is_default: bool = False
    is_active: bool = True


class PipelineStageCreate(BaseModel):
    name: str
    stage_order: int
    probability: int = 0
    color: str | None = None
    is_won: bool = False
    is_lost: bool = False


@router.get("")
async def list_pipelines(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Pipeline))
    items = result.scalars().all()
    return {"items": [{"id": str(item.id), "name": item.name, "pipeline_type": item.pipeline_type} for item in items]}


@router.post("")
async def create_pipeline(payload: PipelineCreate, db: AsyncSession = Depends(get_db)):
    pipeline = Pipeline(**payload.model_dump(exclude_none=True))
    db.add(pipeline)
    await db.commit()
    await db.refresh(pipeline)
    return {"id": str(pipeline.id), "status": "created"}


@router.get("/{pipeline_id}")
async def get_pipeline(pipeline_id: UUID, db: AsyncSession = Depends(get_db)):
    pipeline = await db.get(Pipeline, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return {"id": str(pipeline.id), "name": pipeline.name, "pipeline_type": pipeline.pipeline_type}


@router.put("/{pipeline_id}")
async def update_pipeline(pipeline_id: UUID, payload: PipelineCreate, db: AsyncSession = Depends(get_db)):
    pipeline = await db.get(Pipeline, pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(pipeline, field, value)
    await db.commit()
    return {"status": "updated"}


@router.get("/{pipeline_id}/stages")
async def list_pipeline_stages(pipeline_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(PipelineStage).where(PipelineStage.pipeline_id == str(pipeline_id)))
    items = result.scalars().all()
    return {"items": [{"id": str(item.id), "name": item.name, "stage_order": item.stage_order} for item in items]}


@router.post("/{pipeline_id}/stages")
async def create_pipeline_stage(pipeline_id: UUID, payload: PipelineStageCreate, db: AsyncSession = Depends(get_db)):
    stage = PipelineStage(pipeline_id=pipeline_id, **payload.model_dump(exclude_none=True))
    db.add(stage)
    await db.commit()
    await db.refresh(stage)
    return {"id": str(stage.id), "status": "created"}
