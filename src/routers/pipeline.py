# -*- coding: utf-8 -*-
"""
카카오맵 검색 + 크롤링 + Milvus 삽입 완전 통합 파이프라인 API
"""
import json
import os
from pathlib import Path
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from pymilvus import MilvusClient, DataType
from openai import OpenAI
from dotenv import load_dotenv

from src.crawlers.kakao_map_crawler import KakaoMapCrawler
from src.crawlers.kakao_search import KakaoSearch, CATEGORY_RESTAURANT, CATEGORY_ACCOMMODATION

load_dotenv()

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "volumes" / "raw"
CRAWLED_DIR = BASE_DIR / "volumes" / "crawled"

# Milvus 설정
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
COLLECTION_NAME = "kakao_places"

# OpenAI 설정
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# 파이프라인 상태 저장
pipeline_status = {
    "is_running": False,
    "current_phase": None,  # "crawling", "inserting", "completed"
    "category": None,
    "crawl_progress": 0,
    "crawl_total": 0,
    "insert_progress": 0,
    "insert_total": 0,
    "crawled_count": 0,
    "inserted_count": 0,
    "errors": []
}


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
    current_phase: Optional[str]
    category: Optional[str]
    crawl_progress: int
    crawl_total: int
    insert_progress: int
    insert_total: int
    crawled_count: int
    inserted_count: int
    errors: list


def search_places_with_kakao(
    search_queries: List[str],
    category_code: str,
    limit_per_query: int = 10
) -> List[Dict]:
    """
    카카오 API로 장소 검색 및 place_id 수집

    Args:
        search_queries: 검색 키워드 리스트
        category_code: 카테고리 코드 (FD6: 음식점, AD5: 숙박)
        limit_per_query: 쿼리당 검색할 장소 수

    Returns:
        List[Dict]: 검색된 장소 정보 리스트 (id 포함)
    """
    kakao_search = KakaoSearch()
    all_places = []
    seen_ids = set()

    for query in search_queries:
        print(f"Searching for: {query}")
        try:
            places = kakao_search.search_and_extract_ids(
                query=query,
                category_group_code=category_code,
                max_results=limit_per_query
            )

            # 중복 제거
            for place in places:
                place_id = place.get("id")
                if place_id and place_id not in seen_ids:
                    all_places.append(place)
                    seen_ids.add(place_id)

            print(f"Found {len(places)} places for '{query}'")
        except Exception as e:
            print(f"Error searching '{query}': {e}")
            continue

    return all_places


def create_collection(client: MilvusClient, recreate: bool = False):
    """Milvus 컬렉션 생성"""
    if client.has_collection(COLLECTION_NAME):
        if recreate:
            print(f"Dropping existing collection: {COLLECTION_NAME}")
            client.drop_collection(COLLECTION_NAME)
        else:
            print(f"Collection already exists: {COLLECTION_NAME}")
            return

    schema = MilvusClient.create_schema(
        auto_id=False,
        enable_dynamic_field=True,
    )

    schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=100, is_primary=True)
    schema.add_field(field_name="place_id", datatype=DataType.VARCHAR, max_length=100)
    schema.add_field(field_name="name", datatype=DataType.VARCHAR, max_length=500)
    schema.add_field(field_name="category", datatype=DataType.VARCHAR, max_length=100)
    schema.add_field(field_name="place_type", datatype=DataType.VARCHAR, max_length=50)
    schema.add_field(field_name="rating", datatype=DataType.VARCHAR, max_length=50)
    schema.add_field(field_name="address", datatype=DataType.VARCHAR, max_length=500)
    schema.add_field(field_name="text_content", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="full_data", datatype=DataType.VARCHAR, max_length=65535)
    schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="IVF_FLAT",
        metric_type="COSINE",
        params={"nlist": 128}
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params
    )

    print(f"Collection created: {COLLECTION_NAME}")


def create_text_content(place_data: dict) -> str:
    """검색을 위한 텍스트 컨텐츠 생성"""
    parts = []

    basic_info = place_data.get('basic_info', {})
    if basic_info.get('name'):
        parts.append(f"가게명: {basic_info['name']}")
    if basic_info.get('category'):
        parts.append(f"카테고리: {basic_info['category']}")

    home = place_data.get('home', {})
    if home.get('address_detail'):
        parts.append(f"주소: {home['address_detail']}")

    if home.get('services'):
        parts.append(f"서비스: {', '.join(home['services'])}")

    menus = place_data.get('menu', {}).get('menus', [])
    if menus:
        menu_names = [m.get('name', '') for m in menus if m.get('name')]
        if menu_names:
            parts.append(f"메뉴: {', '.join(menu_names[:5])}")

    reviews = place_data.get('review', {}).get('reviews', [])
    for i, review in enumerate(reviews[:3]):
        if review.get('content'):
            parts.append(f"리뷰{i+1}: {review['content']}")

    blog_reviews = place_data.get('blog_review', {}).get('blog_reviews', [])
    for i, blog in enumerate(blog_reviews[:3]):
        if blog.get('title'):
            parts.append(f"블로그{i+1}: {blog['title']}")
        if blog.get('content'):
            parts.append(blog['content'][:100])

    return " | ".join(parts)


def run_pipeline(
    category: str,
    search_queries: List[str],
    limit_per_query: int,
    crawl_limit: int,
    recreate_collection: bool
):
    """카카오맵 검색 + 크롤링 + Milvus 삽입 완전 통합 파이프라인"""
    global pipeline_status

    pipeline_status["is_running"] = True
    pipeline_status["current_phase"] = "initializing"
    pipeline_status["category"] = category
    pipeline_status["errors"] = []
    pipeline_status["crawl_progress"] = 0
    pipeline_status["crawl_total"] = 0
    pipeline_status["insert_progress"] = 0
    pipeline_status["insert_total"] = 0
    pipeline_status["crawled_count"] = 0
    pipeline_status["inserted_count"] = 0

    try:
        # 1. 카테고리 결정
        categories_to_process = []
        if category == "all":
            categories_to_process = ["accommodation", "restaurant"]
        else:
            categories_to_process = [category]

        # 2. Milvus 클라이언트 생성 및 컬렉션 생성
        print(f"Connecting to Milvus: {MILVUS_URI}")
        milvus_client = MilvusClient(uri=MILVUS_URI)
        create_collection(milvus_client, recreate=recreate_collection)

        total_crawled = 0
        total_inserted = 0

        # 3. 각 카테고리별 처리
        for cat in categories_to_process:
            print(f"\n=== Processing category: {cat} ===")

            # 3-1. 카카오 API로 장소 검색
            pipeline_status["current_phase"] = "searching"

            # 카테고리 코드 결정
            category_code = CATEGORY_ACCOMMODATION if cat == "accommodation" else CATEGORY_RESTAURANT

            try:
                print(f"Searching places with queries: {search_queries}")
                search_results = search_places_with_kakao(
                    search_queries=search_queries,
                    category_code=category_code,
                    limit_per_query=limit_per_query
                )

                print(f"Found {len(search_results)} unique places from search")

                # raw 디렉토리에 검색 결과 저장
                RAW_DIR.mkdir(parents=True, exist_ok=True)
                raw_file = RAW_DIR / f"{cat}.json"

                with open(raw_file, 'w', encoding='utf-8') as f:
                    json.dump(search_results, f, ensure_ascii=False, indent=2)

                print(f"Saved search results to {raw_file}")

                # place_id 추출
                place_ids = [p["id"] for p in search_results if p.get("id")]
                place_ids = place_ids[:crawl_limit]  # 크롤링 제한 적용

                pipeline_status["crawl_total"] = len(place_ids)
                pipeline_status["crawl_progress"] = 0

                print(f"Will crawl {len(place_ids)} places")
            except Exception as e:
                error_msg = f"Failed to search places for {cat}: {str(e)}"
                print(error_msg)
                pipeline_status["errors"].append(error_msg)
                continue

            # 3-2. 크롤링
            pipeline_status["current_phase"] = "crawling"
            crawler = KakaoMapCrawler(headless=True)
            crawled_places = []

            for idx, place_id in enumerate(place_ids, 1):
                try:
                    print(f"Crawling {idx}/{len(place_ids)}: {place_id}")
                    place_data = crawler.crawl_place_detail(place_id)
                    crawled_places.append(place_data)
                    pipeline_status["crawl_progress"] = idx
                except Exception as e:
                    error_msg = f"Failed to crawl {place_id}: {str(e)}"
                    print(error_msg)
                    pipeline_status["errors"].append(error_msg)
                    continue

            # 3-3. 크롤링 결과 저장
            if crawled_places:
                output_file = CRAWLED_DIR / f"{cat}_detailed.json"
                CRAWLED_DIR.mkdir(parents=True, exist_ok=True)

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(crawled_places, f, ensure_ascii=False, indent=2)

                total_crawled += len(crawled_places)
                pipeline_status["crawled_count"] = total_crawled
                print(f"Saved {len(crawled_places)} places to {output_file}")

            # 3-4. Milvus에 삽입
            pipeline_status["current_phase"] = "inserting"
            pipeline_status["insert_total"] = len(crawled_places)
            pipeline_status["insert_progress"] = 0

            data_to_insert = []
            for idx, place in enumerate(crawled_places, 1):
                try:
                    place_id = place.get('place_id', '')
                    basic_info = place.get('basic_info', {})
                    home = place.get('home', {})

                    # 텍스트 컨텐츠 생성
                    text_content = create_text_content(place)

                    # OpenAI 임베딩 생성
                    response = openai_client.embeddings.create(
                        input=text_content,
                        model=EMBEDDING_MODEL
                    )
                    embedding = response.data[0].embedding

                    # 데이터 레코드
                    record = {
                        "id": f"{cat}_{place_id}",
                        "place_id": place_id,
                        "name": basic_info.get('name', ''),
                        "category": basic_info.get('category', ''),
                        "place_type": cat,
                        "rating": basic_info.get('rating', ''),
                        "address": home.get('address_detail', ''),
                        "text_content": text_content[:65535],
                        "full_data": json.dumps(place, ensure_ascii=False)[:65535],
                        "embedding": embedding
                    }

                    data_to_insert.append(record)
                    pipeline_status["insert_progress"] = idx

                    print(f"Prepared embedding {idx}/{len(crawled_places)}: {basic_info.get('name', '')}")

                except Exception as e:
                    error_msg = f"Failed to create embedding for {place.get('place_id', 'unknown')}: {str(e)}"
                    print(error_msg)
                    pipeline_status["errors"].append(error_msg)
                    continue

            # Milvus에 일괄 삽입
            if data_to_insert:
                try:
                    milvus_client.insert(collection_name=COLLECTION_NAME, data=data_to_insert)
                    total_inserted += len(data_to_insert)
                    pipeline_status["inserted_count"] = total_inserted
                    print(f"Inserted {len(data_to_insert)} records to Milvus")
                except Exception as e:
                    error_msg = f"Failed to insert data to Milvus: {str(e)}"
                    print(error_msg)
                    pipeline_status["errors"].append(error_msg)

        # 4. 완료
        pipeline_status["current_phase"] = "completed"
        print(f"\n=== Pipeline completed ===")
        print(f"Total crawled: {total_crawled}")
        print(f"Total inserted: {total_inserted}")
        print(f"Errors: {len(pipeline_status['errors'])}")

    except Exception as e:
        error_msg = f"Pipeline failed: {str(e)}"
        print(error_msg)
        pipeline_status["errors"].append(error_msg)
        pipeline_status["current_phase"] = "failed"
    finally:
        pipeline_status["is_running"] = False


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
    global pipeline_status

    if pipeline_status["is_running"]:
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
        run_pipeline,
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
    return PipelineStatusResponse(
        is_running=pipeline_status["is_running"],
        current_phase=pipeline_status["current_phase"],
        category=pipeline_status["category"],
        crawl_progress=pipeline_status["crawl_progress"],
        crawl_total=pipeline_status["crawl_total"],
        insert_progress=pipeline_status["insert_progress"],
        insert_total=pipeline_status["insert_total"],
        crawled_count=pipeline_status["crawled_count"],
        inserted_count=pipeline_status["inserted_count"],
        errors=pipeline_status["errors"]
    )
