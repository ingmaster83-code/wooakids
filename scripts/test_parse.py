#!/usr/bin/env python3
import json, sys, requests
from datetime import date
sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "9490b1d34e92aa9e25b32a4cff1438fc7b9c71e5d332413916a391e867f61e86"
PG_URL = "https://apis.data.go.kr/1741000/pfc3/getPfctInfo3"
SFTY_URL = "https://apis.data.go.kr/1741000/sfty4/getSftyInsp4"

SIDO_MAP = {
    "11":"서울","26":"부산","27":"대구","28":"인천","29":"광주",
    "30":"대전","31":"울산","36":"세종","41":"경기","42":"강원",
    "43":"충북","44":"충남","45":"전북","46":"전남","47":"경북","48":"경남","50":"제주"
}

# 놀이시설 30건
items = []
for page in range(1, 4):
    r = requests.get(PG_URL, params={"serviceKey": API_KEY, "numOfRows": 10, "pageIndex": page}, timeout=15)
    body = r.json()["response"]["body"]
    items.extend(body.get("items", []))

print(f"놀이시설 수집: {len(items)}건")
print("=== 첫 번째 필드 ===")
print(json.dumps(items[0], ensure_ascii=False, indent=2)[:800])

print("\n=== 지역 파싱 샘플 ===")
for it in items[:5]:
    rgn = str(it.get("rgnCd",""))
    sido = SIDO_MAP.get(rgn[:2], "?")
    rgn_nm = str(it.get("rgnCdNm","") or "")
    parts = rgn_nm.split()
    sigungu = parts[1] if len(parts) > 1 else ""
    name = it.get("pfctNm","")[:25]
    print(f"  {name} | {sido} {sigungu}")

# 안전검사 10건
print("\n=== 안전검사 샘플 ===")
r2 = requests.get(SFTY_URL, params={"serviceKey": API_KEY, "numOfRows": 3, "pageIndex": 1}, timeout=15)
s_items = r2.json()["response"]["body"].get("items", [])
for s in s_items:
    pfct_sn = s.get("pfctSn")
    pass_yn = s.get("passYn")
    vld_ymd = s.get("vldYmd","") or ""
    insp_knd = s.get("inspKndCdNm","")
    name = s.get("pfctNm","")[:20]
    print(f"  pfctSn={pfct_sn} | {name} | {insp_knd} | pass={pass_yn} | vld={vld_ymd}")

print("\n[완료]")
