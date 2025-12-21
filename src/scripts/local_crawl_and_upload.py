# -*- coding: utf-8 -*-
"""
로컬에서 Playwright 크롤링을 실행하고 결과를 서버로 업로드하는 스크립트

사용법:
    python src/scripts/local_crawl_and_upload.py \
        --queries "강남 맛집" "신사동 일식" \
        --place_type restaurant \
        --limit 5 \
        --server_url http://your-server:8000

환경변수:
    KAKAO_REST_API_KEY: 카카오 REST API 키
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Dict
import requests
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.crawlers.kakao_map_crawler import KakaoMapCrawler
from src.crawlers.kakao_search import KakaoSearch, CATEGORY_RESTAURANT, CATEGORY_ACCOMMODATION

load_dotenv()


def search_places(
    search_queries: List[str],
    category_code: str,
    limit_per_query: int = 10
) -> List[Dict]:
    """카카오 API로 장소 검색"""
    kakao_search = KakaoSearch()
    all_places = []
    seen_ids = set()

    for query in search_queries:
        print(f"🔍 Searching for: {query}")
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

            print(f"   Found {len(places)} places for '{query}'")
        except Exception as e:
            print(f"   ❌ Error searching '{query}': {e}")
            continue

    print(f"\n✅ Total unique places found: {len(all_places)}")
    return all_places


def crawl_places(place_ids: List[str], headless: bool = True) -> List[Dict]:
    """Playwright로 장소 상세 정보 크롤링"""
    crawler = KakaoMapCrawler(headless=headless)
    crawled_data = []

    total = len(place_ids)
    for idx, place_id in enumerate(place_ids, 1):
        try:
            print(f"🕷️  Crawling {idx}/{total}: {place_id}")
            place_data = crawler.crawl_place_detail(place_id)
            crawled_data.append(place_data)
            print(f"   ✅ Success: {place_data.get('basic_info', {}).get('name', 'Unknown')}")
        except Exception as e:
            print(f"   ❌ Failed to crawl {place_id}: {e}")
            continue

    print(f"\n✅ Successfully crawled {len(crawled_data)}/{total} places")
    return crawled_data


def save_to_json(data: List[Dict], output_file: Path):
    """JSON 파일로 저장"""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 Saved to: {output_file}")


def upload_to_server(
    server_url: str,
    place_type: str,
    crawled_data: List[Dict],
    recreate_collection: bool = False
):
    """서버로 크롤링 데이터 업로드"""
    endpoint = f"{server_url}/pipeline/upload"

    payload = {
        "place_type": place_type,
        "places": crawled_data,
        "recreate_collection": recreate_collection
    }

    print(f"\n📤 Uploading {len(crawled_data)} places to {endpoint}...")

    try:
        response = requests.post(endpoint, json=payload, timeout=300)
        response.raise_for_status()

        result = response.json()
        print(f"✅ Upload successful!")
        print(f"   - Total uploaded: {result['total_uploaded']}")
        print(f"   - Inserted to Milvus: {result['inserted_count']}")
        if result.get('errors'):
            print(f"   - Errors: {len(result['errors'])}")
            for error in result['errors'][:5]:  # 처음 5개만 출력
                print(f"     • {error}")

        return result

    except requests.exceptions.RequestException as e:
        print(f"❌ Upload failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Response: {e.response.text}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="로컬에서 카카오맵 크롤링 후 서버로 업로드"
    )
    parser.add_argument(
        "--queries",
        nargs="+",
        required=True,
        help="검색 키워드 (예: '강남 맛집' '홍대 카페')"
    )
    parser.add_argument(
        "--place_type",
        choices=["restaurant", "accommodation"],
        required=True,
        help="장소 타입"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="쿼리당 검색할 최대 장소 수 (기본: 10)"
    )
    parser.add_argument(
        "--crawl_limit",
        type=int,
        default=None,
        help="실제 크롤링할 장소 수 제한 (기본: 전체)"
    )
    parser.add_argument(
        "--server_url",
        default="http://localhost:8000",
        help="서버 URL (기본: http://localhost:8000)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="로컬 JSON 파일 저장 경로 (선택사항)"
    )
    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="서버 업로드 건너뛰기 (로컬 저장만)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="헤드리스 모드로 크롤링 (기본: True)"
    )
    parser.add_argument(
        "--recreate-collection",
        action="store_true",
        help="서버의 Milvus 컬렉션 재생성"
    )

    args = parser.parse_args()

    # 카테고리 코드 결정
    category_code = CATEGORY_ACCOMMODATION if args.place_type == "accommodation" else CATEGORY_RESTAURANT

    print("=" * 60)
    print("🚀 로컬 크롤링 & 서버 업로드 스크립트")
    print("=" * 60)
    print(f"검색 키워드: {args.queries}")
    print(f"장소 타입: {args.place_type}")
    print(f"검색 제한: 쿼리당 {args.limit}개")
    print(f"서버 URL: {args.server_url}")
    print("=" * 60)

    # 1. 장소 검색
    print("\n[STEP 1] 카카오 API로 장소 검색 중...")
    search_results = search_places(args.queries, category_code, args.limit)

    if not search_results:
        print("❌ 검색 결과가 없습니다.")
        return

    # place_id 추출
    place_ids = [p["id"] for p in search_results if p.get("id")]

    # 크롤링 제한 적용
    if args.crawl_limit and args.crawl_limit < len(place_ids):
        place_ids = place_ids[:args.crawl_limit]
        print(f"⚠️  크롤링 제한 적용: {len(place_ids)}개만 크롤링")

    # 2. 크롤링
    print(f"\n[STEP 2] {len(place_ids)}개 장소 크롤링 중...")
    crawled_data = crawl_places(place_ids, headless=args.headless)

    if not crawled_data:
        print("❌ 크롤링된 데이터가 없습니다.")
        return

    # 3. 로컬 저장 (선택)
    if args.output:
        print(f"\n[STEP 3] 로컬 파일로 저장 중...")
        save_to_json(crawled_data, args.output)

    # 4. 서버 업로드
    if not args.no_upload:
        print(f"\n[STEP 4] 서버로 업로드 중...")
        try:
            upload_to_server(
                server_url=args.server_url,
                place_type=args.place_type,
                crawled_data=crawled_data,
                recreate_collection=args.recreate_collection
            )
        except Exception as e:
            print(f"❌ 업로드 실패: {e}")
            if args.output:
                print(f"💡 데이터는 {args.output}에 저장되어 있습니다.")
            else:
                # 업로드 실패 시 자동으로 로컬 저장
                fallback_path = BASE_DIR / "output" / f"{args.place_type}_crawled.json"
                print(f"💾 Fallback: {fallback_path}에 저장 중...")
                save_to_json(crawled_data, fallback_path)
            return

    print("\n" + "=" * 60)
    print("✅ 모든 작업 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
