# -*- coding: utf-8 -*-
import asyncio
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])
pipeline_service = PipelineService()


class PipelineRequest(BaseModel):
    category: str = Field(..., description="accommodation, restaurant, or all")
    search_queries: List[str] = Field(..., description="Kakao search queries")
    limit_per_query: int = Field(default=10, ge=1, le=30)
    crawl_limit: int = Field(default=5, ge=1, le=100)
    recreate_collection: bool = Field(default=False, description="Reset the pgvector table before insert")


class PipelineResponse(BaseModel):
    message: str
    category: str
    total_places: int
    status: str


class PipelineStatusResponse(BaseModel):
    is_running: bool
    current_phase: Optional[str]
    category: Optional[str]
    crawl_progress: int
    crawl_total: int
    insert_progress: int
    insert_total: int
    crawled_count: int
    inserted_count: int
    errors: List[str]


class UploadCrawledDataRequest(BaseModel):
    place_type: str = Field(..., description="accommodation or restaurant")
    places: List[Dict] = Field(..., description="Crawled place payloads")
    recreate_collection: bool = Field(default=False, description="Reset the pgvector table before insert")


class UploadCrawledDataResponse(BaseModel):
    message: str
    place_type: str
    total_uploaded: int
    inserted_count: int
    errors: List[str]


@router.post("/run", response_model=PipelineResponse)
async def run_crawl_insert_pipeline(
    request: PipelineRequest,
    background_tasks: BackgroundTasks,
) -> PipelineResponse:
    status = pipeline_service.get_status()
    if status["is_running"]:
        raise HTTPException(status_code=400, detail="Pipeline is already running")

    if request.category not in {"accommodation", "restaurant", "all"}:
        raise HTTPException(
            status_code=400,
            detail="category must be one of accommodation, restaurant, or all",
        )

    if not request.search_queries:
        raise HTTPException(status_code=400, detail="search_queries cannot be empty")

    estimated_total = len(request.search_queries) * request.limit_per_query
    if request.category == "all":
        estimated_total *= 2

    background_tasks.add_task(
        pipeline_service.run_pipeline,
        request.category,
        request.search_queries,
        request.limit_per_query,
        request.crawl_limit,
        request.recreate_collection,
    )

    return PipelineResponse(
        message="Pipeline started successfully. Search, crawl, and insert will continue in the background.",
        category=request.category,
        total_places=min(estimated_total, request.crawl_limit),
        status="running",
    )


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status() -> PipelineStatusResponse:
    status = pipeline_service.get_status()
    return PipelineStatusResponse(**status)


@router.post("/upload", response_model=UploadCrawledDataResponse)
async def upload_crawled_data(
    request: UploadCrawledDataRequest,
) -> UploadCrawledDataResponse:
    if request.place_type not in {"accommodation", "restaurant"}:
        raise HTTPException(
            status_code=400,
            detail="place_type must be accommodation or restaurant",
        )

    if not request.places:
        raise HTTPException(status_code=400, detail="places cannot be empty")

    try:
        result = await asyncio.to_thread(
            pipeline_service.upload_crawled_data,
            request.place_type,
            request.places,
            request.recreate_collection,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return UploadCrawledDataResponse(**result)
