# -*- coding: utf-8 -*-
"""
숙소 100개 + 음식점 100개 일괄 크롤링

volumes/raw/accommodation.json과 restaurants.json에서 ID를 추출하여
카카오맵 상세 정보를 크롤링합니다.

사용법:
    python crawl_all_places.py
"""
import json
import sys
import io
from pathlib import Path
from typing import List, Dict

# UTF-8 출력 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from src.crawlers.kakao_map_crawler import KakaoMapCrawler


# 경로 설정
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # /app
RAW_DIR = BASE_DIR / "volumes" / "raw"
OUTPUT_DIR = BASE_DIR / "volumes" / "crawled"


def load_json(filepath: Path) -> List[Dict]:
    """JSON 파일 로드"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_place_ids(data: List[Dict]) -> List[str]:
    """JSON 데이터에서 place_id 추출"""
    place_ids = []
    for item in data:
        place_id = item.get('id')
        if place_id:
            place_ids.append(str(place_id))
    return place_ids


def crawl_and_save(category: str, place_ids: List[str], crawler: KakaoMapCrawler):
    """
    장소 크롤링 및 저장

    Args:
        category: 'accommodation' 또는 'restaurant'
        place_ids: 크롤링할 장소 ID 리스트
        crawler: KakaoMapCrawler 인스턴스
    """
    print("\n" + "=" * 80)
    print(f"📍 {category.upper()} 크롤링 시작")
    print(f"총 {len(place_ids)}개 장소")
    print("=" * 80)

    results = []
    failed_ids = []

    for idx, place_id in enumerate(place_ids, 1):
        try:
            print(f"\n[{idx}/{len(place_ids)}] 크롤링 중: {place_id}")

            # 크롤링 실행
            place_data = crawler.crawl_place_detail(place_id)
            results.append(place_data)

            # 간단한 정보 출력
            name = place_data.get('basic_info', {}).get('name', 'N/A')
            category_name = place_data.get('basic_info', {}).get('category', 'N/A')
            rating = place_data.get('basic_info', {}).get('rating', 'N/A')

            print(f"  ✅ {name} ({category_name}) - 평점: {rating}")

            # 중간 저장 (10개마다)
            if idx % 10 == 0:
                temp_file = OUTPUT_DIR / f"{category}_temp_{idx}.json"
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"  💾 중간 저장: {temp_file}")

        except Exception as e:
            print(f"  ❌ 오류 발생: {e}")
            failed_ids.append(place_id)
            continue

    # 최종 저장
    output_file = OUTPUT_DIR / f"{category}_detailed.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print(f"✅ {category.upper()} 크롤링 완료!")
    print(f"성공: {len(results)}개")
    print(f"실패: {len(failed_ids)}개")
    print(f"저장 위치: {output_file}")

    if failed_ids:
        print(f"\n실패한 ID 목록: {failed_ids}")

        # 실패한 ID 저장
        failed_file = OUTPUT_DIR / f"{category}_failed_ids.json"
        with open(failed_file, 'w', encoding='utf-8') as f:
            json.dump(failed_ids, f, ensure_ascii=False, indent=2)
        print(f"실패 ID 저장: {failed_file}")

    print("=" * 80)

    return results, failed_ids


def main():
    print("\n" + "=" * 80)
    print("🚀 카카오맵 숙소/음식점 일괄 크롤링 시작")
    print("=" * 80)

    # 1. JSON 파일 로드
    print("\n📂 데이터 파일 로드 중...")
    accommodation_file = RAW_DIR / "accommodation.json"
    restaurants_file = RAW_DIR / "restaurants.json"

    if not accommodation_file.exists():
        print(f"❌ 숙소 데이터 파일이 없습니다: {accommodation_file}")
        print("먼저 'python src/memory/data.py'를 실행하여 데이터를 수집하세요.")
        sys.exit(1)

    if not restaurants_file.exists():
        print(f"❌ 음식점 데이터 파일이 없습니다: {restaurants_file}")
        print("먼저 'python src/memory/data.py'를 실행하여 데이터를 수집하세요.")
        sys.exit(1)

    accommodation_data = load_json(accommodation_file)
    restaurants_data = load_json(restaurants_file)

    print(f"  ✅ 숙소 데이터: {len(accommodation_data)}개")
    print(f"  ✅ 음식점 데이터: {len(restaurants_data)}개")

    # 2. Place ID 추출
    print("\n🔍 Place ID 추출 중...")
    accommodation_ids = extract_place_ids(accommodation_data)
    restaurant_ids = extract_place_ids(restaurants_data)

    # 테스트용으로 각 5개씩만 사용
    accommodation_ids = accommodation_ids[:5]
    restaurant_ids = restaurant_ids[:5]

    print(f"  ✅ 숙소 ID: {len(accommodation_ids)}개 (테스트)")
    print(f"  ✅ 음식점 ID: {len(restaurant_ids)}개 (테스트)")

    # 3. 크롤러 생성
    print("\n🔧 크롤러 초기화 중...")
    crawler = KakaoMapCrawler(headless=True)
    print("  ✅ 크롤러 준비 완료")

    # 4. 숙소 크롤링
    accommodation_results, accommodation_failed = crawl_and_save(
        "accommodation",
        accommodation_ids,
        crawler
    )

    # 5. 음식점 크롤링
    restaurant_results, restaurant_failed = crawl_and_save(
        "restaurant",
        restaurant_ids,
        crawler
    )

    # 6. 전체 요약
    print("\n" + "=" * 80)
    print("🎉 전체 크롤링 완료!")
    print("=" * 80)
    print(f"\n📊 최종 결과:")
    print(f"  숙소:")
    print(f"    - 성공: {len(accommodation_results)}개")
    print(f"    - 실패: {len(accommodation_failed)}개")
    print(f"\n  음식점:")
    print(f"    - 성공: {len(restaurant_results)}개")
    print(f"    - 실패: {len(restaurant_failed)}개")
    print(f"\n  총계:")
    print(f"    - 성공: {len(accommodation_results) + len(restaurant_results)}개")
    print(f"    - 실패: {len(accommodation_failed) + len(restaurant_failed)}개")

    print(f"\n📂 저장 위치: {OUTPUT_DIR}")
    print("=" * 80)


if __name__ == "__main__":
    main()
