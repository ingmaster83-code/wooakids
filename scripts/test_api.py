#!/usr/bin/env python3
"""
test_api.py - wooakids API 4개 샘플 검증 (각 10건)
"""
import json
import sys
import requests
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "9490b1d34e92aa9e25b32a4cff1438fc7b9c71e5d332413916a391e867f61e86"

APIS = {
    "놀이시설_기본정보": {
        "url": "https://apis.data.go.kr/1741000/pfc3/getPfctInfo3",
        "params": {},
        "type": "mois",
    },
    "놀이시설_기구정보": {
        "url": "https://apis.data.go.kr/1741000/ride4/getRide4",
        "params": {},
        "type": "mois",
    },
    "놀이시설_안전검사": {
        "url": "https://apis.data.go.kr/1741000/sfty4/getSftyInsp4",
        "params": {},
        "type": "mois",
    },
    "관광공사_관광정보": {
        "url": "https://apis.data.go.kr/B551011/KorService2/areaBasedList2",
        "params": {
            "contentTypeId": "12",
            "areaCode": "1",
            "arrange": "A",
            "MobileOS": "ETC",
            "MobileApp": "wooakids",
            "_type": "json",
        },
        "type": "tour",
    },
}


def test_mois_api(name, url):
    """행안부 놀이시설 API 테스트"""
    params = {
        "serviceKey": API_KEY,
        "numOfRows": 5,
        "pageIndex": 1,
    }
    print(f"\n{'='*55}")
    print(f"[{name}]  {url}")
    try:
        resp = requests.get(url, params=params, timeout=15)
        print(f"Status: {resp.status_code}")
        ct = resp.headers.get("Content-Type", "")
        print(f"Content-Type: {ct}")

        if resp.text.strip().startswith('<'):
            print(f"XML 응답 (첫 500자):\n{resp.text[:500]}")
            return None

        data = resp.json()
        print(f"최상위 키: {list(data.keys())}")

        # 공통 구조 파싱
        result = data.get("result") or data.get("response", {})
        if isinstance(result, dict):
            items = result.get("list") or result.get("items", {})
        else:
            items = data.get("list") or []

        # 다른 구조 시도
        if not items:
            for k, v in data.items():
                if isinstance(v, list) and v:
                    items = v
                    print(f"  (items found under key '{k}')")
                    break
                elif isinstance(v, dict):
                    sub = v.get("list") or v.get("item") or []
                    if sub:
                        items = sub if isinstance(sub, list) else [sub]
                        print(f"  (items found under '{k}.list/item')")
                        break

        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]

        print(f"items 수: {len(items)}")
        if items:
            first = items[0]
            print(f"첫 번째 키: {list(first.keys())[:12]}")
            for k, v in list(first.items())[:6]:
                print(f"  {k}: {str(v)[:70]}")
        return items
    except Exception as e:
        print(f"오류: {e}")
        print(f"응답 내용: {resp.text[:400] if 'resp' in dir() else 'N/A'}")
        return None


def test_tour_api(name, url, extra_params):
    """관광공사 API 테스트"""
    params = {"serviceKey": API_KEY, "numOfRows": 5, "pageNo": 1}
    params.update(extra_params)
    print(f"\n{'='*55}")
    print(f"[{name}]  {url}")
    try:
        resp = requests.get(url, params=params, timeout=15)
        print(f"Status: {resp.status_code}")

        if resp.text.strip().startswith('<'):
            print(f"XML 응답:\n{resp.text[:500]}")
            return None

        data = resp.json()
        response = data.get("response", data)
        header = response.get("header", {})
        body = response.get("body", {})
        print(f"resultCode: {header.get('resultCode')} / {header.get('resultMsg')}")
        print(f"totalCount: {body.get('totalCount', '?')}")

        items = body.get("items", {})
        if isinstance(items, dict):
            items = items.get("item", [])
        if isinstance(items, dict):
            items = [items]

        print(f"items 수: {len(items)}")
        if items:
            print(f"첫 번째 키: {list(items[0].keys())[:12]}")
            for k, v in list(items[0].items())[:6]:
                print(f"  {k}: {str(v)[:70]}")
        return items
    except Exception as e:
        print(f"오류: {e}")
        print(f"응답: {resp.text[:400] if 'resp' in dir() else 'N/A'}")
        return None


if __name__ == "__main__":
    results = {}
    for name, cfg in APIS.items():
        if cfg["type"] == "mois":
            items = test_mois_api(name, cfg["url"])
        else:
            items = test_tour_api(name, cfg["url"], cfg["params"])
        results[name] = items

    print("\n" + "="*55)
    print("[매칭 분석] 놀이시설 기본 vs 안전검사 공통 키 확인")
    pg = results.get("놀이시설_기본정보")
    sf = results.get("놀이시설_안전검사")
    if pg and pg[0]:
        print(f"  기본정보 전체 키: {list(pg[0].keys())}")
    if sf and sf[0]:
        print(f"  안전검사 전체 키: {list(sf[0].keys())}")
    print("\n[완료]")
