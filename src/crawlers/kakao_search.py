# -*- coding: utf-8 -*-
"""
카카오 로컬 API를 사용한 장소 검색
"""
import os
import requests
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()


class KakaoSearch:
    """카카오 로컬 API 검색"""

    def __init__(self):
        self.api_key = os.getenv("KAKAO_API_KEY")
        if not self.api_key:
            raise ValueError("KAKAO_API_KEY environment variable is required")

        self.base_url = "https://dapi.kakao.com/v2/local/search"
        self.headers = {"Authorization": f"KakaoAK {self.api_key}"}

    def search_keyword(
        self,
        query: str,
        category_group_code: Optional[str] = None,
        x: Optional[str] = None,
        y: Optional[str] = None,
        radius: Optional[int] = None,
        size: int = 15,
        page: int = 1
    ) -> Dict:
        """
        키워드로 장소 검색

        Args:
            query: 검색 키워드
            category_group_code: 카테고리 그룹 코드 (FD6: 음식점, AD5: 숙박)
            x: 중심 좌표의 X값 (경도)
            y: 중심 좌표의 Y값 (위도)
            radius: 중심 좌표부터의 반경 거리 (미터, 최대 20000)
            size: 한 페이지에 보여질 문서의 개수 (1~15)
            page: 결과 페이지 번호 (1~45)

        Returns:
            Dict: 검색 결과
        """
        url = f"{self.base_url}/keyword.json"

        params = {
            "query": query,
            "size": min(size, 15),
            "page": page
        }

        if category_group_code:
            params["category_group_code"] = category_group_code
        if x:
            params["x"] = x
        if y:
            params["y"] = y
        if radius:
            params["radius"] = min(radius, 20000)

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()

        return response.json()

    def search_category(
        self,
        category_group_code: str,
        x: str,
        y: str,
        radius: int = 5000,
        size: int = 15,
        page: int = 1
    ) -> Dict:
        """
        카테고리로 장소 검색

        Args:
            category_group_code: 카테고리 그룹 코드 (FD6: 음식점, AD5: 숙박)
            x: 중심 좌표의 X값 (경도)
            y: 중심 좌표의 Y값 (위도)
            radius: 중심 좌표부터의 반경 거리 (미터, 최대 20000)
            size: 한 페이지에 보여질 문서의 개수 (1~15)
            page: 결과 페이지 번호 (1~45)

        Returns:
            Dict: 검색 결과
        """
        url = f"{self.base_url}/category.json"

        params = {
            "category_group_code": category_group_code,
            "x": x,
            "y": y,
            "radius": min(radius, 20000),
            "size": min(size, 15),
            "page": page
        }

        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()

        return response.json()

    def extract_place_ids(self, search_result: Dict) -> List[str]:
        """
        검색 결과에서 place_id 추출

        Args:
            search_result: search_keyword 또는 search_category의 반환값

        Returns:
            List[str]: place_id 리스트
        """
        place_ids = []
        documents = search_result.get("documents", [])

        for doc in documents:
            place_id = doc.get("id")
            if place_id:
                place_ids.append(str(place_id))

        return place_ids

    def search_and_extract_ids(
        self,
        query: str,
        category_group_code: Optional[str] = None,
        max_results: int = 15
    ) -> List[Dict]:
        """
        검색 후 place_id와 기본 정보 추출

        Args:
            query: 검색 키워드
            category_group_code: 카테고리 그룹 코드
            max_results: 최대 결과 수

        Returns:
            List[Dict]: place_id와 기본 정보를 포함한 리스트
        """
        results = []
        page = 1
        total_collected = 0

        while total_collected < max_results:
            size = min(15, max_results - total_collected)

            search_result = self.search_keyword(
                query=query,
                category_group_code=category_group_code,
                size=size,
                page=page
            )

            documents = search_result.get("documents", [])
            if not documents:
                break

            for doc in documents:
                results.append({
                    "id": str(doc.get("id", "")),
                    "place_name": doc.get("place_name", ""),
                    "category_name": doc.get("category_name", ""),
                    "address_name": doc.get("address_name", ""),
                    "road_address_name": doc.get("road_address_name", ""),
                    "phone": doc.get("phone", ""),
                    "x": doc.get("x", ""),
                    "y": doc.get("y", "")
                })
                total_collected += 1

                if total_collected >= max_results:
                    break

            # 더 이상 결과가 없거나 마지막 페이지면 종료
            meta = search_result.get("meta", {})
            if meta.get("is_end", True):
                break

            page += 1

        return results


# 카테고리 그룹 코드 상수
CATEGORY_RESTAURANT = "FD6"  # 음식점
CATEGORY_ACCOMMODATION = "AD5"  # 숙박
CATEGORY_CAFE = "CE7"  # 카페
