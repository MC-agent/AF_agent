# -*- coding: utf-8 -*-
"""
크롤링 데이터를 Milvus 벡터 DB에 저장하는 스크립트
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import json
import os
from pathlib import Path
from typing import List, Dict
from pymilvus import MilvusClient, DataType
from openai import OpenAI
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent
CRAWLED_DIR = BASE_DIR / "volumes" / "crawled"

# Milvus 설정
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
COLLECTION_NAME = "kakao_places"

# OpenAI 클라이언트
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536  # text-embedding-3-small의 차원


def create_collection(client: MilvusClient):
    """Milvus 컬렉션 생성"""

    # 기존 컬렉션 삭제 (개발 중에만)
    if client.has_collection(COLLECTION_NAME):
        print(f"⚠️  기존 컬렉션 '{COLLECTION_NAME}' 삭제 중...")
        client.drop_collection(COLLECTION_NAME)

    # 스키마 정의
    schema = MilvusClient.create_schema(
        auto_id=False,
        enable_dynamic_field=True,
    )

    # 필드 정의
    schema.add_field(field_name="id", datatype=DataType.VARCHAR, max_length=100, is_primary=True)
    schema.add_field(field_name="place_id", datatype=DataType.VARCHAR, max_length=100)
    schema.add_field(field_name="name", datatype=DataType.VARCHAR, max_length=500)
    schema.add_field(field_name="category", datatype=DataType.VARCHAR, max_length=100)
    schema.add_field(field_name="place_type", datatype=DataType.VARCHAR, max_length=50)  # accommodation or restaurant
    schema.add_field(field_name="rating", datatype=DataType.VARCHAR, max_length=50)
    schema.add_field(field_name="address", datatype=DataType.VARCHAR, max_length=500)
    schema.add_field(field_name="text_content", datatype=DataType.VARCHAR, max_length=65535)  # 검색용 텍스트
    schema.add_field(field_name="full_data", datatype=DataType.VARCHAR, max_length=65535)  # 전체 JSON 데이터
    schema.add_field(field_name="embedding", datatype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)  # OpenAI embedding 차원

    # 인덱스 파라미터
    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="IVF_FLAT",
        metric_type="COSINE",
        params={"nlist": 128}
    )

    # 컬렉션 생성
    client.create_collection(
        collection_name=COLLECTION_NAME,
        schema=schema,
        index_params=index_params
    )

    print(f"✅ 컬렉션 '{COLLECTION_NAME}' 생성 완료")


def extract_place_features(place_data: Dict) -> str:
    """LLM을 사용해 리뷰에서 장소의 감성/특징을 추출"""
    basic_info = place_data.get('basic_info', {})
    name = basic_info.get('name', '')
    category = basic_info.get('category', '')

    # 리뷰 수집 (최대 10개)
    review_texts = []
    reviews = place_data.get('review', {}).get('reviews', [])
    for r in reviews[:10]:
        content = r.get('content', '').strip()
        if content and len(content) > 10:
            review_texts.append(content)

    # 블로그 리뷰 수집 (최대 5개)
    blog_reviews = place_data.get('blog_review', {}).get('blog_reviews', [])
    for b in blog_reviews[:5]:
        title = b.get('title', '').strip()
        content = b.get('content', '').strip()
        if title:
            review_texts.append(title)
        if content:
            review_texts.append(content[:300])

    if not review_texts:
        return ""

    reviews_joined = "\n".join(f"- {r}" for r in review_texts)

    prompt = f"""다음은 '{name}'({category}) 에 대한 리뷰들입니다.
리뷰를 분석해서 이 장소의 특징을 한국어로 간결하게 서술해주세요.

포함할 내용:
- 분위기/인테리어 (예: 아늑함, 모던함, 캐주얼, 고급스러움, 따뜻함, 시끌벅적함)
- 음식 특징 (예: 자극적, 담백함, 푸짐함, 정갈함)
- 어떤 상황에 어울리는지 (예: 데이트, 가족 모임, 혼밥, 회식, 술자리)
- 서비스/분위기 특징

리뷰:
{reviews_joined}

특징 (3~5문장으로):"""

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Feature extraction failed for {name}: {e}")
        return ""


def create_text_content(place_data: Dict) -> str:
    """검색을 위한 텍스트 컨텐츠 생성 (기본정보 + LLM 특징 추출 + 리뷰 원문)"""
    parts = []

    # 1. 기본 정보
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
            parts.append(f"메뉴: {', '.join(menu_names[:10])}")

    # 2. LLM으로 추출한 감성/특징
    features = extract_place_features(place_data)
    if features:
        parts.append(f"특징: {features}")

    # 3. 리뷰 원문 (더 많이, 더 길게)
    reviews = place_data.get('review', {}).get('reviews', [])
    for i, review in enumerate(reviews[:10]):
        content = review.get('content', '').strip()
        if content and len(content) > 10:
            parts.append(f"리뷰{i+1}: {content[:200]}")

    blog_reviews = place_data.get('blog_review', {}).get('blog_reviews', [])
    for i, blog in enumerate(blog_reviews[:5]):
        if blog.get('title'):
            parts.append(f"블로그제목{i+1}: {blog['title']}")
        if blog.get('content'):
            parts.append(f"블로그{i+1}: {blog['content'][:200]}")

    return " | ".join(parts)


def insert_data(client: MilvusClient, file_path: Path, place_type: str):
    """크롤링 데이터를 Milvus에 삽입"""

    print(f"\n📂 파일 로드 중: {file_path.name}")

    with open(file_path, 'r', encoding='utf-8') as f:
        places = json.load(f)

    print(f"  총 {len(places)}개 장소 발견")

    # 데이터 준비
    data = []
    for place in places:
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
            "id": f"{place_type}_{place_id}",
            "place_id": place_id,
            "name": basic_info.get('name', ''),
            "category": basic_info.get('category', ''),
            "place_type": place_type,
            "rating": basic_info.get('rating', ''),
            "address": home.get('address_detail', ''),
            "text_content": text_content[:65535],  # 최대 길이 제한
            "full_data": json.dumps(place, ensure_ascii=False)[:65535],  # 전체 JSON
            "embedding": embedding
        }

        data.append(record)

    # Milvus에 삽입
    if data:
        client.insert(
            collection_name=COLLECTION_NAME,
            data=data
        )
        print(f"  ✅ {len(data)}개 레코드 삽입 완료")

    return len(data)


def main():
    print("=" * 80)
    print("🚀 크롤링 데이터를 Milvus에 저장")
    print("=" * 80)

    # Milvus 클라이언트 생성
    print(f"\n🔌 Milvus 연결 중: {MILVUS_URI}")
    client = MilvusClient(uri=MILVUS_URI)

    # 컬렉션 생성
    print("\n📋 컬렉션 생성 중...")
    create_collection(client)

    # 데이터 파일
    accommodation_file = CRAWLED_DIR / "accommodation_detailed.json"
    restaurant_file = CRAWLED_DIR / "restaurant_detailed.json"

    # 데이터 삽입
    total_inserted = 0

    if accommodation_file.exists():
        count = insert_data(client, accommodation_file, "accommodation")
        total_inserted += count
    else:
        print(f"⚠️  파일 없음: {accommodation_file}")

    if restaurant_file.exists():
        count = insert_data(client, restaurant_file, "restaurant")
        total_inserted += count
    else:
        print(f"⚠️  파일 없음: {restaurant_file}")

    # 결과 출력
    print("\n" + "=" * 80)
    print("✅ 완료!")
    print("=" * 80)
    print(f"총 {total_inserted}개 레코드가 Milvus에 저장되었습니다.")
    print(f"컬렉션명: {COLLECTION_NAME}")

    # 컬렉션 통계
    stats = client.get_collection_stats(COLLECTION_NAME)
    print(f"\n컬렉션 통계: {stats}")


if __name__ == "__main__":
    main()
