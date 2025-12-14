# -*- coding: utf-8 -*-
"""
Milvus 데이터 삽입 API 라우터
"""
import json
import os
from pathlib import Path
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from pymilvus import MilvusClient, DataType
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/milvus", tags=["Milvus"])

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CRAWLED_DIR = BASE_DIR / "volumes" / "crawled"

# Milvus 설정
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
COLLECTION_NAME = "kakao_places"

# OpenAI 설정
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

# 삽입 상태 저장
insert_status = {
    "is_running": False,
    "current_category": None,
    "progress": 0,
    "total": 0,
    "inserted_count": 0
}


class MilvusInsertRequest(BaseModel):
    category: str = Field(..., description="'accommodation' 또는 'restaurant' 또는 'all'")
    recreate_collection: bool = Field(default=False, description="컬렉션 재생성 여부")

    class Config:
        json_schema_extra = {
            "example": {
                "category": "accommodation",
                "recreate_collection": False
            }
        }


class MilvusInsertResponse(BaseModel):
    message: str
    category: str
    status: str


class MilvusStatusResponse(BaseModel):
    is_running: bool
    current_category: Optional[str]
    progress: int
    total: int
    inserted_count: int


class MilvusSearchRequest(BaseModel):
    query: str = Field(..., description="검색 쿼리")
    limit: int = Field(default=5, description="결과 개수", ge=1, le=20)
    place_type: Optional[str] = Field(default=None, description="'accommodation' 또는 'restaurant'")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "강남역 근처 맛있는 일식당",
                "limit": 5,
                "place_type": "restaurant"
            }
        }


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


def create_text_content(place_data: Dict) -> str:
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


def insert_data_task(category: str, recreate: bool):
    """백그라운드 데이터 삽입 작업"""
    global insert_status

    insert_status["is_running"] = True
    insert_status["current_category"] = category
    insert_status["progress"] = 0
    insert_status["total"] = 0
    insert_status["inserted_count"] = 0

    try:
        client = MilvusClient(uri=MILVUS_URI)
        create_collection(client, recreate=recreate)

        categories_to_process = []
        if category == "all":
            categories_to_process = ["accommodation", "restaurant"]
        else:
            categories_to_process = [category]

        total_inserted = 0

        for cat in categories_to_process:
            file_path = CRAWLED_DIR / f"{cat}_detailed.json"

            if not file_path.exists():
                print(f"File not found: {file_path}")
                continue

            with open(file_path, 'r', encoding='utf-8') as f:
                places = json.load(f)

            insert_status["total"] += len(places)

            data = []
            for idx, place in enumerate(places, 1):
                place_id = place.get('place_id', '')
                basic_info = place.get('basic_info', {})
                home = place.get('home', {})

                text_content = create_text_content(place)

                response = openai_client.embeddings.create(
                    input=text_content,
                    model=EMBEDDING_MODEL
                )
                embedding = response.data[0].embedding

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

                data.append(record)
                insert_status["progress"] += 1

            if data:
                client.insert(collection_name=COLLECTION_NAME, data=data)
                total_inserted += len(data)
                insert_status["inserted_count"] = total_inserted

        print(f"Total inserted: {total_inserted}")

    except Exception as e:
        print(f"Error during insertion: {e}")
        raise
    finally:
        insert_status["is_running"] = False
        insert_status["current_category"] = None


@router.post("/insert", response_model=MilvusInsertResponse)
async def insert_to_milvus(request: MilvusInsertRequest, background_tasks: BackgroundTasks):
    """
    크롤링 데이터를 Milvus에 삽입

    - **category**: 'accommodation', 'restaurant', 또는 'all'
    - **recreate_collection**: True면 기존 컬렉션 삭제 후 재생성
    """
    global insert_status

    if insert_status["is_running"]:
        raise HTTPException(
            status_code=400,
            detail="Insert operation is already in progress"
        )

    if request.category not in ["accommodation", "restaurant", "all"]:
        raise HTTPException(
            status_code=400,
            detail="Category must be 'accommodation', 'restaurant', or 'all'"
        )

    try:
        background_tasks.add_task(insert_data_task, request.category, request.recreate_collection)

        return MilvusInsertResponse(
            message="Insert operation started successfully",
            category=request.category,
            status="running"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.get("/status", response_model=MilvusStatusResponse)
async def get_insert_status():
    """
    Milvus 삽입 진행 상태 확인
    """
    return MilvusStatusResponse(
        is_running=insert_status["is_running"],
        current_category=insert_status["current_category"],
        progress=insert_status["progress"],
        total=insert_status["total"],
        inserted_count=insert_status["inserted_count"]
    )


@router.post("/search")
async def search_places(request: MilvusSearchRequest):
    """
    Milvus에서 장소 검색

    - **query**: 검색 쿼리 (자연어)
    - **limit**: 결과 개수 (1-20)
    - **place_type**: 장소 타입 필터 (optional)
    """
    try:
        client = MilvusClient(uri=MILVUS_URI)

        if not client.has_collection(COLLECTION_NAME):
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{COLLECTION_NAME}' not found"
            )

        # 쿼리 임베딩 생성
        response = openai_client.embeddings.create(
            input=request.query,
            model=EMBEDDING_MODEL
        )
        query_embedding = response.data[0].embedding

        # 검색 필터
        search_filter = None
        if request.place_type:
            search_filter = f'place_type == "{request.place_type}"'

        # 벡터 검색
        results = client.search(
            collection_name=COLLECTION_NAME,
            data=[query_embedding],
            limit=request.limit,
            filter=search_filter,
            output_fields=["id", "name", "category", "place_type", "rating", "address", "text_content"]
        )

        # 결과 포맷팅
        formatted_results = []
        for hits in results:
            for hit in hits:
                formatted_results.append({
                    "id": hit["entity"]["id"],
                    "name": hit["entity"]["name"],
                    "category": hit["entity"]["category"],
                    "place_type": hit["entity"]["place_type"],
                    "rating": hit["entity"]["rating"],
                    "address": hit["entity"]["address"],
                    "score": hit["distance"],
                    "text_preview": hit["entity"]["text_content"][:200]
                })

        return {
            "query": request.query,
            "count": len(formatted_results),
            "results": formatted_results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


@router.get("/collection/stats")
async def get_collection_stats():
    """
    Milvus 컬렉션 통계 조회
    """
    try:
        client = MilvusClient(uri=MILVUS_URI)

        if not client.has_collection(COLLECTION_NAME):
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{COLLECTION_NAME}' not found"
            )

        stats = client.get_collection_stats(COLLECTION_NAME)

        return {
            "collection_name": COLLECTION_NAME,
            "stats": stats
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
