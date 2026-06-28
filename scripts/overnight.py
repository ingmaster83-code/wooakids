#!/usr/bin/env python3
"""
overnight.py - 밤새 자동 수집 + SEO 생성 + Jekyll 빌드 오케스트레이터

사용:
  python scripts/overnight.py

순서:
  1. fetch_kids.py --pg-only  (죽으면 최대 5회 재시작)
  2. generate_seo.py           (놀이시설 템플릿 + 관광지 DeepSeek)
  3. jekyll build
"""

import sys
import time
import subprocess
import signal
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT    = Path(__file__).parent.parent
SCRIPTS = ROOT / "scripts"
LOG_DIR = SCRIPTS

CHECK_INTERVAL = 60   # 60초마다 프로세스 상태 확인
MAX_RETRIES    = 5


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def run_step(cmd: list, log_file: Path, label: str, max_retries: int = MAX_RETRIES) -> bool:
    for attempt in range(1, max_retries + 1):
        log(f"▶ {label} (시도 {attempt}/{max_retries})")
        log_file.parent.mkdir(parents=True, exist_ok=True)

        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"\n\n{'='*60}\n")
            lf.write(f"시작: {datetime.now().isoformat()}  시도: {attempt}\n")
            lf.write(f"{'='*60}\n")

        proc = subprocess.Popen(
            cmd,
            stdout=open(log_file, "a", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            cwd=ROOT,
        )

        start = time.time()
        while proc.poll() is None:
            elapsed = int(time.time() - start)
            mins, secs = divmod(elapsed, 60)
            print(f"  ⏱  {mins:02d}분 {secs:02d}초 경과  (PID {proc.pid})", end="\r", flush=True)
            time.sleep(CHECK_INTERVAL)

        print()  # 줄바꿈
        rc = proc.returncode
        if rc == 0:
            log(f"✅ {label} 완료 ({int(time.time()-start)//60}분 소요)")
            return True
        else:
            log(f"❌ {label} 실패 (exit {rc}). {'재시작...' if attempt < max_retries else '포기.'}")
            if attempt < max_retries:
                cooldown = 60 * attempt
                log(f"   {cooldown}초 대기 후 재시도...")
                time.sleep(cooldown)

    return False


def main():
    log("=" * 50)
    log("overnight.py 시작")
    log("=" * 50)

    # ── Step 1: 놀이시설 수집 ────────────────
    ok = run_step(
        cmd=[sys.executable, "-u", str(SCRIPTS / "fetch_kids.py"), "--pg-only"],
        log_file=LOG_DIR / "fetch_log.txt",
        label="놀이시설 수집 (fetch_kids.py --pg-only)",
    )
    if not ok:
        log("🚫 수집 실패. 종료.")
        sys.exit(1)

    # 수집 결과 검증
    pg_file = ROOT / "_rawdata" / "playgrounds.json"
    if not pg_file.exists() or pg_file.stat().st_size < 1_000_000:
        log(f"🚫 playgrounds.json 이상 ({pg_file.stat().st_size if pg_file.exists() else '없음'} bytes). 종료.")
        sys.exit(1)
    log(f"   playgrounds.json: {pg_file.stat().st_size / 1024 / 1024:.1f} MB")

    # ── Step 2: SEO 설명문 생성 ──────────────
    ok = run_step(
        cmd=[sys.executable, "-u", str(SCRIPTS / "generate_seo.py")],
        log_file=LOG_DIR / "seo_log.txt",
        label="SEO 설명문 생성 (generate_seo.py)",
        max_retries=3,
    )
    if not ok:
        log("⚠️  SEO 생성 실패. 빌드는 계속 진행합니다.")

    # ── Step 3: Jekyll 빌드 ──────────────────
    ok = run_step(
        cmd=["bundle", "exec", "jekyll", "build"],
        log_file=LOG_DIR / "build_log.txt",
        label="Jekyll 빌드",
        max_retries=2,
    )
    if not ok:
        log("🚫 Jekyll 빌드 실패.")
        sys.exit(1)

    log("=" * 50)
    log("🎉 모든 작업 완료! 내일 아침에 확인하세요.")
    log("   다음 단계: git add . && git commit && git push")
    log("=" * 50)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\n⛔ 사용자 중단 (Ctrl+C)")
        sys.exit(0)
