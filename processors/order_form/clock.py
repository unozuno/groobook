"""서울 시간 기준 날짜·시각 (서버가 UTC 여도 업무일 기준을 유지)."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")


def now_seoul() -> datetime:
    return datetime.now(SEOUL)


def today_seoul() -> date:
    return now_seoul().date()


def now_iso() -> str:
    """설정 파일 변경 감지(낙관적 잠금)에도 쓰이므로 마이크로초까지 기록한다."""
    return now_seoul().isoformat(timespec="microseconds")
