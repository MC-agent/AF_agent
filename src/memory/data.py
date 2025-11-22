import requests
import json
from pathlib import Path
from typing import List, Dict


KAKAO_API_KEY = "42d92ccdf88326f8f0e6aca63f5f26a8"
RAW_DIR = Path(__file__).resolve().parent.parent.parent / "volumes" / "raw"

def search_category(
    category_code: str,
    x: float,
    y: float,
    radius: int = 2000,
    target_count: int = 100
) -> List[Dict]:
    """
    카테고리 코드로 음식점(FD6) / 숙박(AD5) 검색
    """
    url = "https://dapi.kakao.com/v2/local/search/category.json"
    headers = {
        "Authorization": f"KakaoAK {KAKAO_API_KEY}"
    }

    page = 1
    size = 15
    results: List[Dict] = []

    while len(results) < target_count and page <= 45:
        params = {
            "category_group_code": category_code,
            "x": x,      # 경도 (longitude)
            "y": y,      # 위도 (latitude)
            "radius": radius,
            "page": page,
            "size": size,
        }

        resp = requests.get(url, headers=headers, params=params, timeout=5)
        print(f"[Kakao] {category_code} page={page}, status={resp.status_code}")
        resp.raise_for_status()

        data = resp.json()
        docs = data.get("documents", [])
        meta = data.get("meta", {})

        if not docs:
            break

        results.extend(docs)

        if meta.get("is_end", True):
            break

        page += 1

    return results[:target_count]


def save_json(data, filename):
    RAW_DIR.mkdir(parents=True, exist_ok=True)   # 폴더 없으면 생성

    filepath = RAW_DIR / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[JSON] Saved {len(data)} → {filepath}")

def main():
    # ⚠️ 위도/경도 제대로 넣기 (x=경도, y=위도)
    x = 127.027619  # 강남역 경도
    y = 37.497946  # 강남역 위도

    radius = 2000  # 예: 반경 2km

    # ------ 숙소 ------
    accommodation = search_category("AD5", x=x, y=y, radius=radius, target_count=100)
    save_json(accommodation, "accommodation.json")

    # ------ 식당 ------
    restaurants = search_category("FD6", x=x, y=y, radius=radius, target_count=100)
    save_json(restaurants, "restaurants.json")

    print("숙소:", len(accommodation), "개")
    print("식당:", len(restaurants), "개")


if __name__ == "__main__":
    main()