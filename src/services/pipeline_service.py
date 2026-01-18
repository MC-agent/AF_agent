# -*- coding: utf-8 -*-
"""
Pipeline Service - 카카오맵 크롤링 파이프라인 비즈니스 로직
"""
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
from pymilvus import MilvusClient, DataType
from openai import OpenAI
from dotenv import load_dotenv

from src.crawlers.kakao_map_crawler import KakaoMapCrawler
from src.crawlers.kakao_search import KakaoSearch, CATEGORY_RESTAURANT, CATEGORY_ACCOMMODATION

load_dotenv()


class PipelineService:
    """카카오맵 크롤링 파이프라인 비즈니스 로직을 처리하는 Service"""

    # 경로 설정
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    RAW_DIR = BASE_DIR / "volumes" / "raw"
    CRAWLED_DIR = BASE_DIR / "volumes" / "crawled"

    # Milvus 설정
    MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
    COLLECTION_NAME = "kakao_places"

    # OpenAI 설정
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIM = 1536

    def __init__(self):
        """PipelineService 초기화"""
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.milvus_client: Optional[MilvusClient] = None

        # 파이프라인 상태 저장
        self.pipeline_status = {
            "is_running": False,
            "current_phase": None,
            "category": None,
            "crawl_progress": 0,
            "crawl_total": 0,
            "insert_progress": 0,
            "insert_total": 0,
            "crawled_count": 0,
            "inserted_count": 0,
            "errors": []
        }

    def get_status(self) -> Dict:
        """
        파이프라인 진행 상태 조회

        Returns:
            파이프라인 상태 딕셔너리
        """
        return self.pipeline_status.copy()

    def search_places_with_kakao(
        self,
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
            검색된 장소 정보 리스트 (id 포함)
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

    def create_milvus_collection(self, recreate: bool = False) -> None:
        """
        Milvus 컬렉션 생성

        Args:
            recreate: True면 기존 컬렉션 삭제 후 재생성
        """
        if not self.milvus_client:
            self.milvus_client = MilvusClient(uri=self.MILVUS_URI)

        if self.milvus_client.has_collection(self.COLLECTION_NAME):
            if recreate:
                print(f"Dropping existing collection: {self.COLLECTION_NAME}")
                self.milvus_client.drop_collection(self.COLLECTION_NAME)
            else:
                print(f"Collection already exists: {self.COLLECTION_NAME}")
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
        schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=self.EMBEDDING_DIM)

        index_params = self.milvus_client.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128}
        )

        self.milvus_client.create_collection(
            collection_name=self.COLLECTION_NAME,
            schema=schema,
            index_params=index_params
        )

        print(f"Collection created: {self.COLLECTION_NAME}")

    def create_text_content(self, place_data: dict) -> str:
        """
        검색을 위한 텍스트 컨텐츠 생성

        Args:
            place_data: 장소 데이터 딕셔너리

        Returns:
            검색용 텍스트 컨텐츠
        """
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
        self,
        category: str,
        search_queries: List[str],
        limit_per_query: int,
        crawl_limit: int,
        recreate_collection: bool
    ) -> None:
        """
        카카오맵 검색 + 크롤링 + Milvus 삽입 완전 통합 파이프라인

        Args:
            category: 'accommodation', 'restaurant', 또는 'all'
            search_queries: 검색 키워드 리스트
            limit_per_query: 쿼리당 검색할 장소 수
            crawl_limit: 실제 크롤링할 장소 수
            recreate_collection: 컬렉션 재생성 여부
        """
        self.pipeline_status["is_running"] = True
        self.pipeline_status["current_phase"] = "initializing"
        self.pipeline_status["category"] = category
        self.pipeline_status["errors"] = []
        self.pipeline_status["crawl_progress"] = 0
        self.pipeline_status["crawl_total"] = 0
        self.pipeline_status["insert_progress"] = 0
        self.pipeline_status["insert_total"] = 0
        self.pipeline_status["crawled_count"] = 0
        self.pipeline_status["inserted_count"] = 0

        try:
            # 1. 카테고리 결정
            categories_to_process = []
            if category == "all":
                categories_to_process = ["accommodation", "restaurant"]
            else:
                categories_to_process = [category]

            # 2. Milvus 클라이언트 생성 및 컬렉션 생성
            print(f"Connecting to Milvus: {self.MILVUS_URI}")
            self.create_milvus_collection(recreate=recreate_collection)

            total_crawled = 0
            total_inserted = 0

            # 3. 각 카테고리별 처리
            for cat in categories_to_process:
                print(f"\n=== Processing category: {cat} ===")

                # 3-1. 카카오 API로 장소 검색
                self.pipeline_status["current_phase"] = "searching"

                # 카테고리 코드 결정
                category_code = CATEGORY_ACCOMMODATION if cat == "accommodation" else CATEGORY_RESTAURANT

                try:
                    print(f"Searching places with queries: {search_queries}")
                    search_results = self.search_places_with_kakao(
                        search_queries=search_queries,
                        category_code=category_code,
                        limit_per_query=limit_per_query
                    )

                    print(f"Found {len(search_results)} unique places from search")

                    # raw 디렉토리에 검색 결과 저장
                    self.RAW_DIR.mkdir(parents=True, exist_ok=True)
                    raw_file = self.RAW_DIR / f"{cat}.json"

                    with open(raw_file, 'w', encoding='utf-8') as f:
                        json.dump(search_results, f, ensure_ascii=False, indent=2)

                    print(f"Saved search results to {raw_file}")

                    # place_id 추출
                    place_ids = [p["id"] for p in search_results if p.get("id")]
                    place_ids = place_ids[:crawl_limit]

                    self.pipeline_status["crawl_total"] = len(place_ids)
                    self.pipeline_status["crawl_progress"] = 0

                    print(f"Will crawl {len(place_ids)} places")
                except Exception as e:
                    error_msg = f"Failed to search places for {cat}: {str(e)}"
                    print(error_msg)
                    self.pipeline_status["errors"].append(error_msg)
                    continue

                # 3-2. 크롤링
                self.pipeline_status["current_phase"] = "crawling"
                crawler = KakaoMapCrawler(headless=True)
                crawled_places = []

                for idx, place_id in enumerate(place_ids, 1):
                    try:
                        print(f"Crawling {idx}/{len(place_ids)}: {place_id}")
                        place_data = crawler.crawl_place_detail(place_id)
                        crawled_places.append(place_data)
                        self.pipeline_status["crawl_progress"] = idx
                    except Exception as e:
                        error_msg = f"Failed to crawl {place_id}: {str(e)}"
                        print(error_msg)
                        self.pipeline_status["errors"].append(error_msg)
                        continue

                # 3-3. 크롤링 결과 저장
                if crawled_places:
                    output_file = self.CRAWLED_DIR / f"{cat}_detailed.json"
                    self.CRAWLED_DIR.mkdir(parents=True, exist_ok=True)

                    with open(output_file, 'w', encoding='utf-8') as f:
                        json.dump(crawled_places, f, ensure_ascii=False, indent=2)

                    total_crawled += len(crawled_places)
                    self.pipeline_status["crawled_count"] = total_crawled
                    print(f"Saved {len(crawled_places)} places to {output_file}")

                # 3-4. Milvus에 삽입
                self.pipeline_status["current_phase"] = "inserting"
                self.pipeline_status["insert_total"] = len(crawled_places)
                self.pipeline_status["insert_progress"] = 0

                data_to_insert = []
                for idx, place in enumerate(crawled_places, 1):
                    try:
                        place_id = place.get('place_id', '')
                        basic_info = place.get('basic_info', {})
                        home = place.get('home', {})

                        # 텍스트 컨텐츠 생성
                        text_content = self.create_text_content(place)

                        # OpenAI 임베딩 생성
                        response = self.openai_client.embeddings.create(
                            input=text_content,
                            model=self.EMBEDDING_MODEL
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
                        self.pipeline_status["insert_progress"] = idx

                        print(f"Prepared embedding {idx}/{len(crawled_places)}: {basic_info.get('name', '')}")

                    except Exception as e:
                        error_msg = f"Failed to create embedding for {place.get('place_id', 'unknown')}: {str(e)}"
                        print(error_msg)
                        self.pipeline_status["errors"].append(error_msg)
                        continue

                # Milvus에 일괄 삽입
                if data_to_insert:
                    try:
                        self.milvus_client.insert(collection_name=self.COLLECTION_NAME, data=data_to_insert)
                        total_inserted += len(data_to_insert)
                        self.pipeline_status["inserted_count"] = total_inserted
                        print(f"Inserted {len(data_to_insert)} records to Milvus")
                    except Exception as e:
                        error_msg = f"Failed to insert data to Milvus: {str(e)}"
                        print(error_msg)
                        self.pipeline_status["errors"].append(error_msg)

            # 4. 완료
            self.pipeline_status["current_phase"] = "completed"
            print(f"\n=== Pipeline completed ===")
            print(f"Total crawled: {total_crawled}")
            print(f"Total inserted: {total_inserted}")
            print(f"Errors: {len(self.pipeline_status['errors'])}")

        except Exception as e:
            error_msg = f"Pipeline failed: {str(e)}"
            print(error_msg)
            self.pipeline_status["errors"].append(error_msg)
            self.pipeline_status["current_phase"] = "failed"
        finally:
            self.pipeline_status["is_running"] = False

    def upload_crawled_data(
        self,
        place_type: str,
        places: List[Dict],
        recreate_collection: bool
    ) -> Dict:
        """
        로컬에서 크롤링한 JSON 데이터를 서버로 업로드하여 Milvus에 저장

        Args:
            place_type: 'accommodation' 또는 'restaurant'
            places: 크롤링된 장소 데이터 리스트
            recreate_collection: 컬렉션 재생성 여부

        Returns:
            Dict: 업로드 결과 정보
        """
        errors = []
        inserted_count = 0

        try:
            # Milvus 클라이언트 생성 및 컬렉션 생성
            print(f"Connecting to Milvus: {self.MILVUS_URI}")
            self.create_milvus_collection(recreate=recreate_collection)

            # 데이터 준비
            data_to_insert = []

            for idx, place in enumerate(places, 1):
                try:
                    place_id = place.get('place_id', '')
                    basic_info = place.get('basic_info', {})
                    home = place.get('home', {})

                    # 텍스트 컨텐츠 생성
                    text_content = self.create_text_content(place)

                    # OpenAI 임베딩 생성
                    response = self.openai_client.embeddings.create(
                        input=text_content,
                        model=self.EMBEDDING_MODEL
                    )
                    embedding = response.data[0].embedding

                    # 데이터 레코드
                    record = {
                        "id": f"{place_type}_{place_id}",
                        "place_id": place_id,
                        "name": basic_info.get('name', ''),
                        "category": basic_info.get('category', ''),
                        "place_type": place_type,
                        "rating": basic_info.get('rating', ''),
                        "address": home.get('address_detail', ''),
                        "text_content": text_content[:65535],
                        "full_data": json.dumps(place, ensure_ascii=False)[:65535],
                        "embedding": embedding
                    }

                    data_to_insert.append(record)
                    print(f"Prepared embedding {idx}/{len(places)}: {basic_info.get('name', '')}")

                except Exception as e:
                    error_msg = f"Failed to process {place.get('place_id', 'unknown')}: {str(e)}"
                    print(error_msg)
                    errors.append(error_msg)
                    continue

            # Milvus에 일괄 삽입
            if data_to_insert:
                try:
                    self.milvus_client.insert(collection_name=self.COLLECTION_NAME, data=data_to_insert)
                    inserted_count = len(data_to_insert)
                    print(f"Inserted {inserted_count} records to Milvus")
                except Exception as e:
                    error_msg = f"Failed to insert data to Milvus: {str(e)}"
                    print(error_msg)
                    errors.append(error_msg)
                    raise Exception(error_msg)

            return {
                "message": f"Successfully uploaded and inserted {inserted_count} places to Milvus",
                "place_type": place_type,
                "total_uploaded": len(places),
                "inserted_count": inserted_count,
                "errors": errors
            }

        except Exception as e:
            error_msg = f"Upload failed: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)
