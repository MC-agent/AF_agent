# -*- coding: utf-8 -*-
from playwright.sync_api import sync_playwright, Page
import time
from typing import Dict, List, Optional
import json


class KakaoMapCrawler:
    """카카오맵 가게 상세페이지 크롤러"""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.base_url = "https://place.map.kakao.com"

    def crawl_place_detail(self, place_id: str) -> Dict:
        """
        특정 가게의 상세 정보를 크롤링합니다.

        Args:
            place_id: 카카오맵 장소 ID (예: "11463001")

        Returns:
            Dict: 크롤링된 가게 정보
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()

            try:
                # 기본 정보 크롤링
                place_data = {
                    "place_id": place_id,
                    "basic_info": self._crawl_basic_info(page, place_id),
                    "home": self._crawl_home_tab(page, place_id),
                    "menu": self._crawl_menu_tab(page, place_id),
                    "review": self._crawl_review_tab(page, place_id),
                    "blog_review": self._crawl_blog_review_tab(page, place_id),
                    "photo": self._crawl_photo_tab(page, place_id),
                    "location": self._crawl_location_tab(page, place_id),
                }

                return place_data

            finally:
                browser.close()

    def _crawl_basic_info(self, page: Page, place_id: str) -> Dict:
        """기본 정보 크롤링 (상단 정보)"""
        url = f"{self.base_url}/{place_id}"
        page.goto(url)
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        basic_info = {}

        try:
            # 자바스크립트로 기본 정보 추출
            info = page.evaluate("""() => {
                const result = {};

                // 가게명
                const nameEl = document.querySelector('.tit_place');
                if (nameEl) result.name = nameEl.textContent.replace('장소명', '').trim();

                // 카테고리
                const categoryEl = document.querySelector('.info_cate');
                if (categoryEl) result.category = categoryEl.textContent.replace('장소 카테고리', '').trim();

                // 별점 (메인 별점만)
                const ratingEl = document.querySelector('.info_main .num_star');
                if (ratingEl) result.rating = ratingEl.textContent.trim();

                // 후기 수
                const reviewEls = document.querySelectorAll('.info_main .info_num');
                if (reviewEls.length > 0) {
                    result.review_count = reviewEls[0].textContent.trim();
                }

                // 블로그 수
                if (reviewEls.length > 1) {
                    result.blog_count = reviewEls[1].textContent.trim();
                }

                return result;
            }""")

            basic_info.update(info)

        except Exception as e:
            print(f"기본 정보 크롤링 중 오류: {e}")

        return basic_info

    def _crawl_home_tab(self, page: Page, place_id: str) -> Dict:
        """홈 탭 정보 크롤링"""
        # 홈 탭은 기본 페이지와 동일하므로 추가 정보만 수집
        home_data = {}

        try:
            # URL 정보
            if page.locator('.info_suggest a').count() > 0:
                home_data['homepage'] = page.locator('.info_suggest a').first.get_attribute('href')

            # 주소 상세 정보
            if page.locator('.txt_detail').count() > 0:
                home_data['address_detail'] = page.locator('.txt_detail').first.inner_text()

            # 서비스 태그
            if page.locator('.txt_svc').count() > 0:
                services = []
                service_elements = page.locator('.txt_svc').all()
                for elem in service_elements:
                    services.append(elem.inner_text())
                home_data['services'] = services

        except Exception as e:
            print(f"홈 탭 크롤링 중 오류: {e}")

        return home_data

    def _crawl_menu_tab(self, page: Page, place_id: str) -> Dict:
        """메뉴 탭 정보 크롤링"""
        url = f"{self.base_url}/{place_id}#menu"
        page.goto(url)
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        menu_data = {"menus": []}

        try:
            # 자바스크립트로 메뉴 데이터 추출
            menus = page.evaluate("""() => {
                const menuElements = document.querySelectorAll('.list_menu li, [class*="menu_item"]');
                const menus = [];

                menuElements.forEach(el => {
                    const menu = {};

                    // 메뉴명
                    const nameEl = el.querySelector('[class*="tit"], [class*="name"]');
                    if (nameEl) menu.name = nameEl.textContent.trim();

                    // 가격
                    const priceEl = el.querySelector('[class*="price"]');
                    if (priceEl) menu.price = priceEl.textContent.trim();

                    // 설명
                    const descEl = el.querySelector('[class*="desc"]');
                    if (descEl) menu.description = descEl.textContent.trim();

                    if (menu.name || menu.price) {
                        menus.push(menu);
                    }
                });

                return menus;
            }""")

            menu_data['menus'] = menus

        except Exception as e:
            print(f"메뉴 탭 크롤링 중 오류: {e}")

        return menu_data

    def _crawl_review_tab(self, page: Page, place_id: str) -> Dict:
        """리뷰 탭 정보 크롤링"""
        url = f"{self.base_url}/{place_id}#comment"
        page.goto(url)
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        review_data = {"reviews": []}

        try:
            # 자바스크립트로 리뷰 데이터 추출 (최대 10개)
            reviews = page.evaluate("""() => {
                const reviewElements = document.querySelectorAll('.info_review, .list_evaluation li, [class*="review_item"]');
                const reviews = [];

                for (let i = 0; i < Math.min(reviewElements.length, 10); i++) {
                    const el = reviewElements[i];
                    const review = {};

                    // 작성자
                    const authorEl = el.querySelector('[class*="user"], [class*="author"]');
                    if (authorEl) review.author = authorEl.textContent.trim();

                    // 별점
                    const ratingEl = el.querySelector('[class*="star"], [class*="grade"], [class*="rate"]');
                    if (ratingEl) review.rating = ratingEl.textContent.trim();

                    // 날짜
                    const dateEl = el.querySelector('[class*="date"], [class*="time"]');
                    if (dateEl) review.date = dateEl.textContent.trim();

                    // 리뷰 내용
                    const contentEl = el.querySelector('[class*="comment"], [class*="content"], [class*="review"]');
                    if (contentEl) review.content = contentEl.textContent.trim();

                    if (review.content || review.rating) {
                        reviews.push(review);
                    }
                }

                return reviews;
            }""")

            review_data['reviews'] = reviews

        except Exception as e:
            print(f"리뷰 탭 크롤링 중 오류: {e}")

        return review_data

    def _crawl_blog_review_tab(self, page: Page, place_id: str) -> Dict:
        """블로그 리뷰 탭 정보 크롤링"""
        url = f"{self.base_url}/{place_id}#blogreview"
        page.goto(url)
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        blog_review_data = {"blog_reviews": []}

        try:
            # 자바스크립트로 블로그 리뷰 데이터 추출 (최대 10개)
            blog_reviews = page.evaluate("""() => {
                const blogItems = document.querySelectorAll('.info_blog');
                const blogs = [];

                for (let i = 0; i < Math.min(blogItems.length, 10); i++) {
                    const item = blogItems[i];
                    const blog = {};

                    // 제목
                    const titleEl = item.querySelector('.tit_review');
                    if (titleEl) {
                        blog.title = titleEl.textContent.replace('블로그 타이틀 ', '').trim();
                    }

                    // 내용 미리보기 (200자까지만)
                    const allText = item.textContent.trim();
                    if (blog.title) {
                        // 제목 이후의 텍스트를 내용으로
                        const titleIndex = allText.indexOf(blog.title);
                        if (titleIndex >= 0) {
                            blog.content = allText.substring(titleIndex + blog.title.length).trim().substring(0, 200);
                        }
                    }

                    // 실제 블로그 URL 찾기 (카카오맵이 아닌 외부 링크)
                    const links = item.querySelectorAll('a');
                    for (let link of links) {
                        if (link.href && !link.href.includes('place.map.kakao.com')) {
                            blog.url = link.href;
                            break;
                        }
                    }

                    if (blog.title) {
                        blogs.push(blog);
                    }
                }

                return blogs;
            }""")

            blog_review_data['blog_reviews'] = blog_reviews

        except Exception as e:
            print(f"블로그 리뷰 탭 크롤링 중 오류: {e}")

        return blog_review_data

    def _crawl_photo_tab(self, page: Page, place_id: str) -> Dict:
        """사진 탭 정보 크롤링"""
        url = f"{self.base_url}/{place_id}#photo"
        page.goto(url)
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        photo_data = {"photos": []}

        try:
            # 자바스크립트로 사진 URL 수집 (최대 20개)
            photos = page.evaluate("""() => {
                const imgElements = document.querySelectorAll('img[src*="kakaocdn"], img[src*="cloudfront"]');
                const photos = [];

                for (let i = 0; i < Math.min(imgElements.length, 20); i++) {
                    let url = imgElements[i].src;
                    if (url && !url.includes('favicon') && !url.includes('logo')) {
                        // 상대 경로면 절대 경로로 변환
                        if (url.startsWith('//')) {
                            url = 'https:' + url;
                        }
                        photos.push(url);
                    }
                }

                return photos;
            }""")

            photo_data['photos'] = photos

        except Exception as e:
            print(f"사진 탭 크롤링 중 오류: {e}")

        return photo_data

    def _crawl_location_tab(self, page: Page, place_id: str) -> Dict:
        """위치 탭 정보 크롤링"""
        url = f"{self.base_url}/{place_id}#location"
        page.goto(url)
        page.wait_for_load_state('networkidle')
        time.sleep(2)

        location_data = {}

        try:
            # 자바스크립트로 위치 정보 추출
            location = page.evaluate("""() => {
                const result = {};

                // 도로명 주소
                const roadAddrEl = document.querySelector('[class*="addrroad"], [class*="road"]');
                if (roadAddrEl) result.road_address = roadAddrEl.textContent.trim();

                // 지번 주소
                const lotAddrEl = document.querySelector('[class*="addrnum"], [class*="lot"]');
                if (lotAddrEl) result.lot_address = lotAddrEl.textContent.trim();

                // 교통 정보
                const trafficEls = document.querySelectorAll('[class*="traffic"] li, [class*="transport"] li');
                if (trafficEls.length > 0) {
                    result.traffic_info = Array.from(trafficEls).map(el => el.textContent.trim());
                }

                return result;
            }""")

            location_data.update(location)

        except Exception as e:
            print(f"위치 탭 크롤링 중 오류: {e}")

        return location_data

    def crawl_multiple_places(self, place_ids: List[str]) -> List[Dict]:
        """
        여러 가게의 정보를 크롤링합니다.

        Args:
            place_ids: 카카오맵 장소 ID 리스트

        Returns:
            List[Dict]: 크롤링된 가게 정보 리스트
        """
        results = []

        for place_id in place_ids:
            print(f"크롤링 중: {place_id}")
            try:
                place_data = self.crawl_place_detail(place_id)
                results.append(place_data)
                print(f"완료: {place_id}")
            except Exception as e:
                print(f"오류 발생 ({place_id}): {e}")
                continue

            # 요청 간 대기
            time.sleep(3)

        return results

    def save_to_json(self, data: Dict | List[Dict], filename: str):
        """
        크롤링 데이터를 JSON 파일로 저장합니다.

        Args:
            data: 저장할 데이터
            filename: 저장할 파일명
        """
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"데이터 저장 완료: {filename}")
