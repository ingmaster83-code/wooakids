#!/usr/bin/env python3
"""
fetch_nanumteo.py - 한국건강가정진흥원_전국 공동육아나눔터 현황 CSV를
_rawdata/nanumteo.json으로 정규화한다.

원본이 연간 갱신이라 매일 돌릴 필요는 없지만, 재수집이 필요하면
python scripts/fetch_nanumteo.py 로 다시 받을 수 있다.
CSV는 data.go.kr 파일 다운로드 2단계 흐름(atchFileId 조회 후 fileDownload)으로
미리 내려받아 _rawdata/nanumteo_raw.csv에 저장해둔 걸 파싱한다.
"""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
RAW_PATH = ROOT / "_rawdata" / "nanumteo_raw.csv"
OUT_PATH = ROOT / "_rawdata" / "nanumteo.json"


def make_slug(content_id: str, name: str) -> str:
    slug = re.sub(r"[^\w가-힣\s-]", "", name).strip()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return f"{content_id}-{slug}"


def parse():
    with open(RAW_PATH, encoding="cp949") as f:
        reader = csv.reader(f)
        rows = list(reader)

    records = []
    for i, r in enumerate(rows[1:]):
        if len(r) < 6:
            continue
        _, sido, sggu, addr, org, tel = r[:6]
        sido = sido.strip()
        sggu = sggu.strip()
        addr = addr.strip()
        org = org.strip()
        tel = tel.strip()
        if not org:
            continue
        content_id = f"nt{i:04d}"
        records.append({
            "contentId": content_id,
            "slug": make_slug(content_id, org),
            "name": org,
            "sido": sido,
            "sigungu": sggu,
            "address": addr,
            "tel": tel,
            "seoDescription": f"{sido} {sggu} {org} 위치, 연락처 정보를 확인하세요. 부모와 아이가 함께 이용하는 공동육아나눔터입니다.",
        })
    return records


def main():
    if not RAW_PATH.exists():
        raise SystemExit(f"원본 CSV 없음: {RAW_PATH} (data.go.kr에서 먼저 다운로드 필요)")

    records = parse()
    print(f"총 {len(records)}건 파싱 완료")

    from collections import Counter
    sido_cnt = Counter(r["sido"] for r in records)
    for k, v in sorted(sido_cnt.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v}건")

    OUT_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"저장 완료: {OUT_PATH}")


if __name__ == "__main__":
    main()
