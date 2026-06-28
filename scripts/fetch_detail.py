#!/usr/bin/env python3
"""
fetch_detail.py - 관광공사 상세정보 수집 (detailCommon2 + detailIntro2)

attractions.json의 각 시설에 아래 필드를 추가:
  overview, homepage, usetime, usefee, parking,
  chkbabycarriage, chkpet, expagerange, restdate

사용:
  python scripts/fetch_detail.py
  python scripts/fetch_detail.py --limit 50   # 테스트
  python scripts/fetch_detail.py --force      # 이미 있는 것도 덮어쓰기
"""

import json
import sys
import time
import argparse
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding='utf-8')

API_KEY  = "9490b1d34e92aa9e25b32a4cff1438fc7b9c71e5d332413916a391e867f61e86"
BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
DELAY    = 0.3
RAW_DIR  = Path(__file__).parent.parent / "_rawdata"


def clean(v) -> str:
    if v is None:
        return ""
    v = str(v).strip()
    return "" if v in ("null", "None", "", "0") else v


def get(endpoint: str, params: dict) -> dict | None:
    url = f"{BASE_URL}/{endpoint}"
    params = {"serviceKey": API_KEY, "_type": "json",
              "MobileOS": "ETC", "MobileApp": "wooakids", **params}
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 3:
                return None
            time.sleep(1 * (2 ** attempt))
    return None


def fetch_common(content_id: str) -> dict:
    data = get("detailCommon2", {
        "contentId": content_id,
        "overviewYN": "Y", "defaultYN": "Y",
        "firstImageYN": "N", "addrinfoYN": "N",
    })
    if not data:
        return {}
    try:
        item = data["response"]["body"]["items"]["item"]
        if isinstance(item, list):
            item = item[0]
        return {
            "overview": clean(item.get("overview")),
            "homepage": clean(item.get("homepage")),
        }
    except Exception:
        return {}


def fetch_intro(content_id: str, content_type: str) -> dict:
    data = get("detailIntro2", {
        "contentId": content_id,
        "contentTypeId": content_type,
    })
    if not data:
        return {}
    try:
        item = data["response"]["body"]["items"]["item"]
        if isinstance(item, list):
            item = item[0]

        result = {}
        # 공통 관심 필드 (contentType별로 키 이름이 다름)
        for key in ["usetime", "usetimeculture", "usetimeleports",
                    "usefee", "usefeeculture", "usefeeleports",
                    "parking", "parkingculture", "parkingleports",
                    "restdate", "restdateculture",
                    "chkbabycarriage", "chkbabycarriageculture", "chkbabycarriageleports",
                    "chkpet", "chkpetculture", "chkpetleports",
                    "expagerange", "expagerangeleports",
                    "reservation", "openperiod"]:
            val = clean(item.get(key, ""))
            if val:
                # 공통 키로 정규화
                norm = (key
                        .replace("culture", "").replace("leports", "")
                        .replace("_", ""))
                if norm not in result:
                    result[norm] = val
        return result
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    at_file = RAW_DIR / "attractions.json"
    items = json.loads(at_file.read_text(encoding="utf-8"))

    targets = [i for i in items if args.force or not i.get("overview")]
    if args.limit:
        targets = targets[:args.limit]

    total = len(targets)
    print(f"상세정보 수집: {total}건 (전체 {len(items)}건)")

    id_map = {item["contentId"]: idx for idx, item in enumerate(items)}
    done = 0

    for item in targets:
        cid  = item["contentId"]
        ctype = item["contentType"]

        common = fetch_common(cid)
        time.sleep(DELAY)
        intro  = fetch_intro(cid, ctype)
        time.sleep(DELAY)

        merged = {**common, **intro}
        item.update(merged)

        idx = id_map.get(cid)
        if idx is not None:
            items[idx].update(merged)

        done += 1
        if done % 50 == 0:
            at_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [{done}/{total}] 저장 완료")
        else:
            print(f"  [{done}/{total}] {item.get('name','')[:20]}", end="\r", flush=True)

    at_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n완료: {done}건 상세정보 추가")


if __name__ == "__main__":
    main()
