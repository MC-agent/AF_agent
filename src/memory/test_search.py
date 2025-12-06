# -*- coding: utf-8 -*-
"""
Milvus 벡터 검색 테스트
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
import json
from pymilvus import MilvusClient
from sentence_transformers import SentenceTransformer

# Milvus 설정
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530")
COLLECTION_NAME = "kakao_places"

# 임베딩 모델
model = SentenceTransformer('jhgan/ko-sroberta-multitask')


def search_places(query: str, top_k: int = 3):
    """벡터 유사도 검색"""

    print(f"\n🔍 검색 쿼리: '{query}'")
    print("=" * 80)

    # Milvus 클라이언트
    client = MilvusClient(uri=MILVUS_URI)

    # 쿼리 임베딩
    query_embedding = model.encode(query).tolist()

    # 검색
    results = client.search(
        collection_name=COLLECTION_NAME,
        data=[query_embedding],
        limit=top_k,
        output_fields=["place_id", "name", "category", "place_type", "rating", "address", "text_content"]
    )

    # 결과 출력
    if not results or not results[0]:
        print("❌ 검색 결과가 없습니다.")
        return

    print(f"\n✅ 상위 {len(results[0])}개 결과:\n")

    for i, hit in enumerate(results[0], 1):
        entity = hit['entity']
        distance = hit['distance']

        print(f"📍 {i}. {entity.get('name', 'N/A')}")
        print(f"   카테고리: {entity.get('category', 'N/A')}")
        print(f"   타입: {entity.get('place_type', 'N/A')}")
        print(f"   평점: {entity.get('rating', 'N/A')}")
        print(f"   주소: {entity.get('address', 'N/A')}")
        print(f"   유사도: {distance:.4f}")
        print(f"   내용: {entity.get('text_content', '')[:200]}...")
        print()


def main():
    print("=" * 80)
    print("🔍 Milvus 벡터 검색 테스트")
    print("=" * 80)

    # 테스트 쿼리들
    queries = [
        "강남에 있는 호텔 추천해줘",
        "무료 주차 가능한 숙소",
        "중국 요리 맛집",
        "닭갈비 먹을 수 있는 곳",
        "가성비 좋은 한정식"
    ]

    for query in queries:
        search_places(query, top_k=3)
        print("\n" + "-" * 80)

    print("\n✅ 테스트 완료!")


if __name__ == "__main__":
    main()
