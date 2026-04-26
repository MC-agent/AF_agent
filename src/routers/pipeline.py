# -*- coding: utf-8 -*-
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
    crawled_count: int
    inserted_count: int
    status: str
    errors: List[str]


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
    if request.category not in {"accommodation", "restaurant", "all"}:
        raise HTTPException(
            status_code=400,
            detail="category must be one of accommodation, restaurant, or all",
        )

    if not request.search_queries:
        raise HTTPException(status_code=400, detail="search_queries cannot be empty")

    if not pipeline_service.start_pipeline(request.category):
        raise HTTPException(status_code=400, detail="Pipeline is already running")

    background_tasks.add_task(
        pipeline_service.run_pipeline,
        request.category,
        request.search_queries,
        request.limit_per_query,
        request.crawl_limit,
        request.recreate_collection,
        True,
    )

    return PipelineResponse(
        message="Pipeline started",
        category=request.category,
        total_places=0,
        crawled_count=0,
        inserted_count=0,
        status="running",
        errors=[],
    )


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status() -> PipelineStatusResponse:
    status = pipeline_service.get_status()
    return PipelineStatusResponse(**status)


@router.post("/upload", response_model=UploadCrawledDataResponse)
async def upload_crawled_data(
    request: UploadCrawledDataRequest,
    background_tasks: BackgroundTasks,
) -> UploadCrawledDataResponse:
    if request.place_type not in {"accommodation", "restaurant"}:
        raise HTTPException(
            status_code=400,
            detail="place_type must be accommodation or restaurant",
        )

    if not request.places:
        raise HTTPException(status_code=400, detail="places cannot be empty")

    if not pipeline_service.start_pipeline(request.place_type):
        raise HTTPException(status_code=400, detail="Pipeline is already running")

    pipeline_service.pipeline_status["insert_total"] = len(request.places)
    background_tasks.add_task(
        pipeline_service.upload_crawled_data,
        request.place_type,
        request.places,
        request.recreate_collection,
        True,
    )

    return UploadCrawledDataResponse(
        message="Upload started",
        place_type=request.place_type,
        total_uploaded=len(request.places),
        inserted_count=0,
        errors=[],
    )
