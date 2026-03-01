# -*- coding: utf-8 -*-
"""
카카오맵 검색 + 크롤링 + Milvus 삽입 완전 통합 파이프라인 API
"""
import asyncio
from typing import List, Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

# 싱글톤 패턴으로 PipelineService 인스턴스 유지
pipeline_service = PipelineService()


class PipelineRequest(BaseModel):
    category: str = Field(..., description="'accommodation', 'restaurant', 또는 'all'")
    search_queries: List[str] = Field(..., description="검색 키워드 리스트 (예: ['강남 맛집', '홍대 카페'])")
    limit_per_query: int = Field(default=10, description="쿼리당 검색할 장소 수", ge=1, le=30)
    crawl_limit: int = Field(default=5, description="실제 크롤링할 장소 수 (검색 결과 중)", ge=1, le=100)
    recreate_collection: bool = Field(default=False, description="컬렉션 재생성 여부")

    class Config:
        json_schema_extra = {
            "example": {
                "category": "restaurant",
                "search_queries": ["강남 맛집", "신사동 일식"],
                "limit_per_query": 10,
                "crawl_limit": 5,
                "recreate_collection": False
            }
        }


class PipelineResponse(BaseModel):
    message: str
    category: str
    total_places: int
    status: str


class PipelineStatusResponse(BaseModel):
    is_running: bool
    current_phase: str | None
    category: str | None
    crawl_progress: int
    crawl_total: int
    insert_progress: int
    insert_total: int
    crawled_count: int
    inserted_count: int
    errors: list


class UploadCrawledDataRequest(BaseModel):
    """로컬에서 크롤링한 데이터를 서버로 전송"""
    place_type: str = Field(..., description="'accommodation' 또는 'restaurant'")
    places: List[Dict] = Field(..., description="크롤링된 장소 데이터 리스트")
    recreate_collection: bool = Field(default=False, description="컬렉션 재생성 여부")

    class Config:
        json_schema_extra = {
            "example": {
                "place_type": "restaurant",
                "places": [
                    {
                        "place_id": "11463001",
                        "basic_info": {"name": "맛집", "category": "음식점"},
                        "home": {},
                        "menu": {},
                        "review": {},
                        "blog_review": {},
                        "photo": {},
                        "location": {}
                    }
                ],
                "recreate_collection": False
            }
        }


class UploadCrawledDataResponse(BaseModel):
    message: str
    place_type: str
    total_uploaded: int
    inserted_count: int
    errors: List[str]


@router.post("/run", response_model=PipelineResponse)
async def run_crawl_insert_pipeline(request: PipelineRequest, background_tasks: BackgroundTasks):
    """
    카카오맵 검색부터 Milvus 삽입까지 완전 통합 파이프라인 실행

    - **category**: 'accommodation', 'restaurant', 또는 'all'
    - **search_queries**: 검색 키워드 리스트 (예: ['강남 맛집', '신사동 일식'])
    - **limit_per_query**: 쿼리당 검색할 장소 수 (1-30)
    - **crawl_limit**: 실제 크롤링할 장소 수 (1-100)
    - **recreate_collection**: True면 기존 컬렉션 삭제 후 재생성

    ## 파이프라인 단계:
    1. **Searching**: 카카오 API로 장소 검색
    2. **Crawling**: 카카오맵에서 상세 정보 크롤링
    3. **Inserting**: OpenAI 임베딩 생성 및 Milvus 삽입
    4. **Completed**: 완료
    """
    status = pipeline_service.get_status()

    if status["is_running"]:
        raise HTTPException(
            status_code=400,
            detail="Pipeline is already running"
        )

    if request.category not in ["accommodation", "restaurant", "all"]:
        raise HTTPException(
            status_code=400,
            detail="Category must be 'accommodation', 'restaurant', or 'all'"
        )

    if not request.search_queries:
        raise HTTPException(
            status_code=400,
            detail="search_queries cannot be empty"
        )

    # 총 처리할 장소 수 예상
    estimated_total = len(request.search_queries) * request.limit_per_query
    if request.category == "all":
        estimated_total *= 2

    # 백그라운드 작업 시작
    background_tasks.add_task(
        pipeline_service.run_pipeline,
        request.category,
        request.search_queries,
        request.limit_per_query,
        request.crawl_limit,
        request.recreate_collection
    )

    return PipelineResponse(
        message="Pipeline started successfully. Search -> Crawl -> Insert will run automatically.",
        category=request.category,
        total_places=min(estimated_total, request.crawl_limit),
        status="running"
    )


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status():
    """
    파이프라인 진행 상태 확인
    """
    status = pipeline_service.get_status()
    return PipelineStatusResponse(
        is_running=status["is_running"],
        current_phase=status["current_phase"],
        category=status["category"],
        crawl_progress=status["crawl_progress"],
        crawl_total=status["crawl_total"],
        insert_progress=status["insert_progress"],
        insert_total=status["insert_total"],
        crawled_count=status["crawled_count"],
        inserted_count=status["inserted_count"],
        errors=status["errors"]
    )


@router.post("/upload", response_model=UploadCrawledDataResponse)
async def upload_crawled_data(request: UploadCrawledDataRequest):
    """
    로컬에서 크롤링한 JSON 데이터를 서버로 업로드하여 Milvus에 저장

    - **place_type**: 'accommodation' 또는 'restaurant'
    - **places**: 크롤링된 장소 데이터 리스트
    - **recreate_collection**: True면 기존 컬렉션 삭제 후 재생성

    ## 사용 예시:
    로컬에서 크롤링 후:
    ```python
    import requests
    with open('crawled_data.json', 'r') as f:
        data = json.load(f)

    response = requests.post(
        'http://your-server:8000/pipeline/upload',
        json={
            'place_type': 'restaurant',
            'places': data,
            'recreate_collection': False
        }
    )
    ```
    """
    if request.place_type not in ["accommodation", "restaurant"]:
        raise HTTPException(
            status_code=400,
            detail="place_type must be 'accommodation' or 'restaurant'"
        )

    if not request.places:
        raise HTTPException(
            status_code=400,
            detail="places list cannot be empty"
        )

    try:
        result = await asyncio.to_thread(
            pipeline_service.upload_crawled_data,
            request.place_type,
            request.places,
            request.recreate_collection
        )

        return UploadCrawledDataResponse(
            message=result["message"],
            place_type=result["place_type"],
            total_uploaded=result["total_uploaded"],
            inserted_count=result["inserted_count"],
            errors=result["errors"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
