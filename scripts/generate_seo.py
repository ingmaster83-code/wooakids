#!/usr/bin/env python3
"""
generate_seo.py - DeepSeek API로 시설별 SEO 설명문 생성

사용법:
  python scripts/generate_seo.py                    # 전체 (빈 것만)
  python scripts/generate_seo.py --limit 50         # 50건 테스트
  python scripts/generate_seo.py --force            # 기존 것 덮어쓰기
  python scripts/generate_seo.py --file attractions # attractions.json만
"""
import json
import sys
import time
import argparse
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding='utf-8')

DEEPSEEK_KEY_PATH = Path(r"C:\개인\개인 프로젝트\blogwriter_new\blogger_seo_bot\config\deepseek_api_key.txt")
RAWDATA_DIR = Path(__file__).parent.parent / "_rawdata"
DELAY = 0.15

PG_PROMPT = """다음 시설 정보를 바탕으로 네이버/구글 검색 최적화용 한국어 소개문을 120자 이내로 작성하세요.
시설명, 위치, 유형, 안전검사 여부를 자연스럽게 담아주세요. 문장으로 끝내세요. 따옴표나 특수기호 없이.

시설명: {name}
주소: {address}
설치장소: {place}
안전검사: {safety}

소개문만 출력하세요 (설명 없이):"""

AT_PROMPT = """다음 시설 정보를 바탕으로 네이버/구글 검색 최적화용 한국어 소개문을 120자 이내로 작성하세요.
아이와 함께 방문하기 좋은 곳임을 자연스럽게 담아주세요. 문장으로 끝내세요. 따옴표나 특수기호 없이.

시설명: {name}
주소: {address}
유형: {type_label}

소개문만 출력하세요 (설명 없이):"""


def get_api_key() -> str:
    return DEEPSEEK_KEY_PATH.read_text(encoding="utf-8").strip()


def call_deepseek(prompt: str, api_key: str) -> str:
    resp = requests.post(
        "https://api.deepseek.com/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.5,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()[:155]


def make_pg_desc(item: dict) -> str:
    """놀이시설 SEO 설명문 템플릿 자동 생성 (DeepSeek 미사용)"""
    name    = item.get("name", "")
    addr    = item.get("address", "")
    place   = item.get("instlPlace", "")
    idrodr  = item.get("idrodr", "")
    safety  = "안전검사 합격 시설" if item.get("safetyPass") == "Y" else "어린이 놀이시설"
    parts   = [p for p in [addr, place, idrodr] if p]
    loc     = " ".join(parts[:2])
    desc    = f"{name} {loc} {safety}입니다. 우아키즈에서 안전검사 현황과 설치 기구 정보를 확인하세요."
    return desc[:155]


def process_playgrounds(data_file: Path, force: bool) -> None:
    """놀이시설 — 템플릿 자동 생성"""
    items = json.loads(data_file.read_text(encoding="utf-8"))
    targets = [i for i in items if force or not i.get("seoDescription")]
    print(f"\n[playgrounds.json] 템플릿 자동 생성: {len(targets)}건")

    id_map = {item["pfctSn"]: idx for idx, item in enumerate(items)}
    done = 0
    for item in targets:
        desc = make_pg_desc(item)
        item["seoDescription"] = desc
        idx = id_map.get(item["pfctSn"])
        if idx is not None:
            items[idx]["seoDescription"] = desc
        done += 1

    data_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  완료: {done}건 (DeepSeek 미사용)")


def process_attractions(data_file: Path, api_key: str, limit: int, force: bool) -> None:
    """관광지 — DeepSeek API 호출"""
    items = json.loads(data_file.read_text(encoding="utf-8"))
    targets = [i for i in items if force or not i.get("seoDescription")]
    if limit:
        targets = targets[:limit]

    total = len(targets)
    print(f"\n[attractions.json] DeepSeek 생성: {total}건")

    id_map = {item["contentId"]: idx for idx, item in enumerate(items)}
    done = 0
    for item in targets:
        try:
            prompt = AT_PROMPT.format(
                name=item.get("name", ""),
                address=item.get("address", ""),
                type_label=item.get("contentTypeLabel", "시설"),
            )
            desc = call_deepseek(prompt, api_key)
            item["seoDescription"] = desc
            idx = id_map.get(item["contentId"])
            if idx is not None:
                items[idx]["seoDescription"] = desc
            done += 1
            print(f"  [{done}/{total}] {item.get('name','')[:20]}: {desc[:45]}...")
        except Exception as e:
            print(f"  [실패] {item.get('name','')}: {e}")

        if done % 100 == 0 and done > 0:
            data_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [저장] {done}건 완료")

        time.sleep(DELAY)

    data_file.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  완료: {done}/{total}건")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--file", choices=["playgrounds", "attractions", "all"], default="all")
    args = parser.parse_args()

    api_key = get_api_key()

    if args.file in ("playgrounds", "all"):
        pg_file = RAWDATA_DIR / "playgrounds.json"
        if pg_file.exists():
            process_playgrounds(pg_file, args.force)
        else:
            print(f"[건너뜀] {pg_file} 없음")

    if args.file in ("attractions", "all"):
        at_file = RAWDATA_DIR / "attractions.json"
        if at_file.exists():
            api_key = get_api_key()
            process_attractions(at_file, api_key, args.limit, args.force)
        else:
            print(f"[건너뜀] {at_file} 없음")

    print("\n[완료]")


if __name__ == "__main__":
    main()
