# -*- coding: utf-8 -*-
"""로컬 JSON 파일을 서버 /pipeline/upload 엔드포인트로 업로드"""
import json
import requests
import time

SERVER_URL = "https://api.afagentpro.org"

print("Waiting for server deployment to finish...")
max_retries = 30
for i in range(max_retries):
    try:
        resp = requests.get(f"{SERVER_URL}/docs", timeout=5)
        if resp.status_code == 200:
            print("✅ Server is UP!")
            break
        else:
            print(f"[{i+1}/{max_retries}] Server returned {resp.status_code}. Waiting 5 seconds...")
    except Exception as e:
        print(f"[{i+1}/{max_retries}] Server not reachable. Waiting 5 seconds...")
    time.sleep(5)
else:
    print("❌ Server failed to start within the timeout limit.")
    exit(1)

for place_type, path in [
    ("accommodation", "volumes/crawled/accommodation_jeju.json"),
    ("restaurant", "volumes/crawled/restaurant_gangnam.json"),
]:
    print(f"\n{'='*60}")
    print(f"📤 {place_type} 업로드 중... ({path})")
    try:
        data = json.load(open(path, "r", encoding="utf-8"))
        print(f"   총 {len(data)}개 장소")
    except Exception as e:
        print(f"   ❌ 로컬 파일 읽기 실패: {e}")
        continue

    payload = {
        "place_type": place_type,
        "places": data,
        "recreate_collection": False,
    }

    try:
        resp = requests.post(
            f"{SERVER_URL}/pipeline/upload",
            json=payload,
            timeout=300,
        )
        print(f"   HTTP Status: {resp.status_code}")
        result = resp.json()
        print(f"   전체 응답: {json.dumps(result, ensure_ascii=False, indent=2)}")
    except Exception as e:
        print(f"   ❌ 업로드 실패: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   서버 응답: {e.response.text[:1000]}")

print(f"\n{'='*60}")
print("완료!")
