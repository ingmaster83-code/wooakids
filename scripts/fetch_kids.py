#!/usr/bin/env python3
"""
fetch_kids.py - wooakids 데이터 수집 (ThreadPool 병렬)

출력:
  _rawdata/playgrounds.json  - 놀이시설 (기본정보 + 안전검사 병합)
  _rawdata/attractions.json  - 관광지/문화시설/레포츠

사용:
  python scripts/fetch_kids.py
  python scripts/fetch_kids.py --limit 200
  python scripts/fetch_kids.py --pg-only
  python scripts/fetch_kids.py --tour-only
"""

import json
import sys
import time
import argparse
import re
from pathlib import Path
from datetime import date
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.stdout.reconfigure(encoding='utf-8')

API_KEY  = "9490b1d34e92aa9e25b32a4cff1438fc7b9c71e5d332413916a391e867f61e86"
PG_URL   = "https://apis.data.go.kr/1741000/pfc3/getPfctInfo3"
SFTY_URL = "https://apis.data.go.kr/1741000/sfty4/getSftyInsp4"
TOUR_URL = "https://apis.data.go.kr/B551011/KorService2/areaBasedList2"

TOUR_TYPES  = ["12", "14", "28"]
AREA_CODES  = list(range(1, 18))
BATCH       = 100
DELAY       = 1.0   # 1초 딜레이 (분당 60req)
WORKERS     = 1
OUT_DIR     = Path(__file__).parent.parent / "_rawdata"
TODAY       = date.today().isoformat()


# ──────────────────────────────────────────
# 공통 유틸
# ──────────────────────────────────────────

def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s가-힣]", "", str(text))
    text = re.sub(r"\s+", "-", text.strip())
    return text[:60].strip("-").lower()


def clean(v) -> str:
    if v is None:
        return ""
    v = str(v).strip()
    return "" if v in ("null", "None", "") else v


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def fetch_page_sync(session: requests.Session, url: str, params: dict) -> dict | None:
    for attempt in range(10):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = 90 + attempt * 30
                print(f"  [429] page {params.get('pageIndex', params.get('pageNo'))} → {wait}초 대기...", flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if attempt == 9:
                print(f"  [포기] page {params.get('pageIndex', params.get('pageNo'))}: {e}")
                return None
            time.sleep(2 * (2 ** attempt))
    return None


def fetch_mois_all(url: str, extra: dict = None, limit: int = 0) -> list:
    """행안부 API 전체 수집 — ThreadPool 병렬"""
    base = {"serviceKey": API_KEY, "numOfRows": BATCH, "pageIndex": 1}
    if extra:
        base.update(extra)

    session = make_session()

    # 1페이지로 total 파악
    first = fetch_page_sync(session, url, base)
    if not first:
        return []
    body = first["response"]["body"]
    total = int(body.get("totalCnt", 0))
    if limit:
        total = min(total, limit)

    first_items = body.get("items") or []
    if isinstance(first_items, dict):
        first_items = [first_items]
    all_items = list(first_items)

    actual_batch = len(first_items) if first_items else BATCH
    total_pages  = (total + actual_batch - 1) // actual_batch
    print(f"  총 {total}건 / {total_pages}페이지 (페이지당 {actual_batch}건, 스레드 {WORKERS})")

    if total_pages <= 1:
        return all_items[:limit] if limit else all_items

    ckpt_file = OUT_DIR / "_ckpt_pg.json"

    # 체크포인트에서 이어받기
    start_page = 2
    if ckpt_file.exists() and not limit:
        try:
            ckpt = json.loads(ckpt_file.read_text(encoding="utf-8"))
            if ckpt.get("url") == url:
                all_items = ckpt["items"]
                start_page = ckpt["next_page"]
                print(f"  [체크포인트] {len(all_items)}건, page {start_page}부터 재개")
        except Exception:
            pass

    for page_idx in range(start_page, total_pages + 1):
        p = dict(base)
        p["pageIndex"] = page_idx
        data = fetch_page_sync(session, url, p)
        if data:
            items = data["response"]["body"].get("items") or []
            if isinstance(items, dict):
                items = [items]
            all_items.extend(items)
        done = min(len(all_items), total)
        if page_idx % 100 == 0:
            print(f"  수집 {done:6d} / {total} (page {page_idx})", flush=True)
            # 체크포인트 저장
            if not limit:
                ckpt_file.write_text(
                    json.dumps({"url": url, "items": all_items, "next_page": page_idx + 1}, ensure_ascii=False),
                    encoding="utf-8"
                )
        if limit and len(all_items) >= limit:
            break
        time.sleep(DELAY)

    if ckpt_file.exists():
        ckpt_file.unlink()

    return all_items[:limit] if limit else all_items


def fetch_tour_all(content_type: str, area_code: int, limit: int = 0) -> list:
    """관광공사 API 수집"""
    params = {
        "serviceKey": API_KEY, "numOfRows": BATCH, "pageNo": 1,
        "MobileOS": "ETC", "MobileApp": "wooakids", "_type": "json",
        "contentTypeId": content_type, "areaCode": area_code, "arrange": "A",
    }
    session = make_session()
    items = []
    page = 1
    while True:
        params["pageNo"] = page
        data = fetch_page_sync(session, TOUR_URL, params)
        if not data:
            break
        body = data["response"]["body"]
        batch = body.get("items", {})
        if isinstance(batch, dict):
            batch = batch.get("item", [])
        if isinstance(batch, dict):
            batch = [batch]
        if not batch:
            break
        items.extend(batch)
        total = int(body.get("totalCount", 0))
        if limit and len(items) >= limit:
            break
        if len(items) >= total:
            break
        page += 1
        time.sleep(0.1)
    return items[:limit] if limit else items


# ──────────────────────────────────────────
# 놀이시설 처리
# ──────────────────────────────────────────

SIDO_MAP = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천",
    "29": "광주", "30": "대전", "31": "울산", "36": "세종",
    "41": "경기", "42": "강원", "43": "충북", "44": "충남",
    "45": "전북", "46": "전남", "47": "경북", "48": "경남", "50": "제주",
}


def parse_region(rgn_cd: str, rgn_nm: str, rona_addr: str):
    sido = ""
    sigungu = ""
    if rgn_cd and len(str(rgn_cd)) >= 2:
        sido_cd = str(rgn_cd)[:2]
        sido = SIDO_MAP.get(sido_cd, "")
    if not sido and rona_addr:
        parts = rona_addr.split()
        if parts:
            sido = (parts[0]
                    .replace("특별시", "").replace("광역시", "")
                    .replace("특별자치시", "").replace("특별자치도", "")
                    .replace("도", ""))
            if len(parts) > 1:
                sigungu = parts[1]
    if rgn_nm and not sigungu:
        parts = str(rgn_nm).split()
        if len(parts) >= 2:
            sigungu = parts[1]
    return sido, sigungu


def build_playground_record(item: dict) -> dict:
    pfct_sn = clean(item.get("pfctSn"))
    name    = clean(item.get("pfctNm"))
    addr    = clean(item.get("ronaAddr")) or clean(item.get("lotnoAddr"))
    rgn_cd  = clean(item.get("rgnCd"))
    rgn_nm  = clean(item.get("rgnCdNm"))
    sido, sigungu = parse_region(rgn_cd, rgn_nm, addr)
    return {
        "pfctSn":        pfct_sn,
        "slug":          f"{pfct_sn}-{slugify(name)}",
        "name":          name,
        "address":       addr,
        "sido":          sido,
        "sigungu":       sigungu,
        "lat":           clean(item.get("latCrtsVl")),
        "lng":           clean(item.get("lotCrtsVl")),
        "instlPlace":    clean(item.get("instlPlaceCdNm")),
        "instlYmd":      clean(item.get("instlYmd")),
        "operYn":        clean(item.get("operYnCdNm")),
        "idrodr":        clean(item.get("idrodrCdNm")),
        "safetyPass":    "",
        "safetyInspYmd": "",
        "safetyVldYmd":  "",
        "safetyStatus":  "",
        "seoDescription": "",
    }


def calc_safety_status(pass_yn: str, vld_ymd: str) -> str:
    if pass_yn != "Y":
        return "red"
    if not vld_ymd or len(vld_ymd) < 8:
        return "red"
    try:
        vld = date(int(vld_ymd[:4]), int(vld_ymd[4:6]), int(vld_ymd[6:8]))
        days_left = (vld - date.today()).days
        return "red" if days_left < 0 else "yellow" if days_left <= 30 else "green"
    except Exception:
        return "red"


def merge_safety(playgrounds: list, sfty_items: list) -> None:
    print("  안전검사 병합 중...")
    sfty_map: dict[str, dict] = {}
    for s in sfty_items:
        sn = clean(s.get("pfctSn"))
        if not sn:
            continue
        insp_knd = clean(s.get("inspKndCd"))
        insp_ymd = clean(s.get("inspYmd")) or ""
        prev = sfty_map.get(sn)
        if prev is None:
            sfty_map[sn] = s
        else:
            prev_knd = clean(prev.get("inspKndCd"))
            prev_ymd = clean(prev.get("inspYmd")) or ""
            if insp_knd == "E002" and prev_knd != "E002":
                sfty_map[sn] = s
            elif insp_knd == prev_knd and insp_ymd > prev_ymd:
                sfty_map[sn] = s

    merged = 0
    for pg in playgrounds:
        s = sfty_map.get(pg["pfctSn"])
        if s:
            pass_yn = clean(s.get("passYn"))
            vld_ymd = clean(s.get("vldYmd"))
            pg["safetyPass"]    = pass_yn
            pg["safetyInspYmd"] = clean(s.get("inspYmd"))
            pg["safetyVldYmd"]  = vld_ymd
            pg["safetyStatus"]  = calc_safety_status(pass_yn, vld_ymd)
            merged += 1
    print(f"  안전검사 병합: {merged} / {len(playgrounds)}개")


# ──────────────────────────────────────────
# 관광지 처리
# ──────────────────────────────────────────

AREA_CODE_TO_SIDO = {
    "1": "서울", "2": "인천", "3": "대전", "4": "대구", "5": "광주",
    "6": "부산", "7": "울산", "8": "세종", "31": "경기", "32": "강원",
    "33": "충북", "34": "충남", "35": "전북", "36": "전남",
    "37": "경북", "38": "경남", "39": "제주",
}

CONTENT_TYPE_LABEL = {"12": "관광지", "14": "문화시설", "28": "레포츠"}


def build_attraction_record(item: dict, content_type: str) -> dict:
    content_id   = clean(item.get("contentid"))
    name         = clean(item.get("title"))
    area_code    = clean(item.get("areacode"))
    sigungu_code = clean(item.get("sigungucode"))
    sido         = AREA_CODE_TO_SIDO.get(area_code, "")
    addr         = clean(item.get("addr1"))
    return {
        "contentId":        content_id,
        "slug":             f"{content_id}-{slugify(name)}",
        "name":             name,
        "contentType":      content_type,
        "contentTypeLabel": CONTENT_TYPE_LABEL.get(content_type, "기타"),
        "sido":             sido,
        "areaCode":         area_code,
        "sigunguCode":      sigungu_code,
        "address":          addr,
        "tel":              clean(item.get("tel")),
        "firstImage":       clean(item.get("firstimage")),
        "cat1":             clean(item.get("cat1")),
        "cat2":             clean(item.get("cat2")),
        "cat3":             clean(item.get("cat3")),
        "seoDescription":   "",
    }


# ──────────────────────────────────────────
# 메인
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit",     type=int, default=0)
    parser.add_argument("--pg-only",   action="store_true")
    parser.add_argument("--tour-only", action="store_true")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── 놀이시설 ──────────────────────────────
    if not args.tour_only:
        print("\n[Step 1] 놀이시설 기본정보 수집...")
        pg_raw = fetch_mois_all(PG_URL, limit=args.limit)
        print(f"  → {len(pg_raw)}개")

        playgrounds = [build_playground_record(i) for i in pg_raw]

        print("\n[Step 2] 안전검사 정보 수집...")
        sfty_raw = fetch_mois_all(SFTY_URL, limit=0)
        print(f"  → {len(sfty_raw)}개")
        merge_safety(playgrounds, sfty_raw)

        pg_file = OUT_DIR / "playgrounds.json"
        pg_file.write_text(json.dumps(playgrounds, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [저장] {len(playgrounds)}개 ({pg_file.stat().st_size/1024/1024:.1f} MB)")

    # ── 관광지 ──────────────────────────────
    if not args.pg_only:
        print("\n[Step 3] 관광공사 관광정보 수집...")
        attractions = []
        for ct in TOUR_TYPES:
            for area in AREA_CODES:
                items = fetch_tour_all(ct, area, limit=args.limit or 0)
                for item in items:
                    attractions.append(build_attraction_record(item, ct))
            print(f"  contentType={ct} 누적: {len(attractions)}개")

        tour_file = OUT_DIR / "attractions.json"
        tour_file.write_text(json.dumps(attractions, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [저장] {len(attractions)}개 ({tour_file.stat().st_size/1024:.0f} KB)")

    print("\n[완료]")


if __name__ == "__main__":
    main()
