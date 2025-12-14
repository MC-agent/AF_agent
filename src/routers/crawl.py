# -*- coding: utf-8 -*-
"""
크롤링 API 라우터
"""
import json
from pathlib import Path
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.crawlers.kakao_map_crawler import KakaoMapCrawler

router = APIRouter(prefix="/crawl", tags=["Crawling"])

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "volumes" / "raw"
OUTPUT_DIR = BASE_DIR / "volumes" / "crawled"

# 크롤링 상태 저장
crawl_status = {
    "is_running": False,
    "current_category": None,
    "progress": 0,
    "total": 0,
    "results": []
}


class CrawlRequest(BaseModel):
    category: str = Field(..., description="'accommodation' 또는 'restaurant'")
    limit: int = Field(default=5, description="크롤링할 장소 수", ge=1, le=100)

    class Config:
        json_schema_extra = {
            "example": {
                "category": "accommodation",
                "limit": 5
            }
        }


class CrawlResponse(BaseModel):
    message: str
    category: str
    total_places: int
    status: str


class CrawlStatusResponse(BaseModel):
    is_running: bool
    current_category: Optional[str]
    progress: int
    total: int
    success_count: int


def load_place_ids(category: str) -> List[str]:
    """JSON 파일에서 place ID 추출"""
    if category == "accommodation":
        filepath = RAW_DIR / "accommodation.json"
    elif category == "restaurant":
        filepath = RAW_DIR / "restaurants.json"
    else:
        raise ValueError(f"Invalid category: {category}")

    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    place_ids = []
    for item in data:
        place_id = item.get('id')
        if place_id:
            place_ids.append(str(place_id))

    return place_ids


def crawl_places_task(category: str, place_ids: List[str]):
    """백그라운드 크롤링 작업"""
    global crawl_status

    crawl_status["is_running"] = True
    crawl_status["current_category"] = category
    crawl_status["progress"] = 0
    crawl_status["total"] = len(place_ids)
    crawl_status["results"] = []

    crawler = KakaoMapCrawler(headless=True)
    results = []

    try:
        for idx, place_id in enumerate(place_ids, 1):
            try:
                place_data = crawler.crawl_place_detail(place_id)
                results.append(place_data)
                crawl_status["progress"] = idx
                crawl_status["results"] = results
            except Exception as e:
                print(f"Error crawling {place_id}: {e}")
                continue

        # 결과 저장
        output_file = OUTPUT_DIR / f"{category}_detailed.json"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    finally:
        crawl_status["is_running"] = False
        crawl_status["current_category"] = None


@router.post("/start", response_model=CrawlResponse)
async def start_crawling(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    크롤링 시작

    - **category**: 'accommodation' 또는 'restaurant'
    - **limit**: 크롤링할 장소 수 (1-100)
    """
    global crawl_status

    if crawl_status["is_running"]:
        raise HTTPException(
            status_code=400,
            detail="Crawling is already in progress"
        )

    if request.category not in ["accommodation", "restaurant"]:
        raise HTTPException(
            status_code=400,
            detail="Category must be 'accommodation' or 'restaurant'"
        )

    try:
        place_ids = load_place_ids(request.category)
        place_ids = place_ids[:request.limit]

        # 백그라운드 작업 시작
        background_tasks.add_task(crawl_places_task, request.category, place_ids)

        return CrawlResponse(
            message="Crawling started successfully",
            category=request.category,
            total_places=len(place_ids),
            status="running"
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/status", response_model=CrawlStatusResponse)
async def get_crawl_status():
    """
    크롤링 진행 상태 확인
    """
    return CrawlStatusResponse(
        is_running=crawl_status["is_running"],
        current_category=crawl_status["current_category"],
        progress=crawl_status["progress"],
        total=crawl_status["total"],
        success_count=len(crawl_status["results"])
    )


@router.get("/results/{category}")
async def get_crawl_results(category: str):
    """
    크롤링 결과 조회

    - **category**: 'accommodation' 또는 'restaurant'
    """
    if category not in ["accommodation", "restaurant"]:
        raise HTTPException(
            status_code=400,
            detail="Category must be 'accommodation' or 'restaurant'"
        )

    output_file = OUTPUT_DIR / f"{category}_detailed.json"

    if not output_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No results found for category: {category}"
        )

    with open(output_file, 'r', encoding='utf-8') as f:
        results = json.load(f)

    return {
        "category": category,
        "count": len(results),
        "data": results
    }
