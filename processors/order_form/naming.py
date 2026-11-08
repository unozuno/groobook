"""파일명·시트명 생성과 정리."""
import re
from datetime import date

from processors.order_form.clock import today_seoul

_INVALID_FILENAME = re.compile(r'[\\/:*?"<>|]')
_INVALID_SHEET = re.compile(r'[\\/?*\[\]:]')
SHEET_NAME_MAX = 31
DELIVERY_SHEET_BASE = "납품서"


def yymmdd(d: date | None = None) -> str:
    d = d or today_seoul()
    return d.strftime("%y%m%d")


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def sanitize_filename(name: str) -> str:
    return _collapse(_INVALID_FILENAME.sub("", name))


def build_filename(order, today: date | None = None) -> str:
    """지시서 8장 파일명 규칙. 날짜는 실제 작업일(오늘) 기준."""
    d = yymmdd(today)
    if order.mode == "blank_delivery":
        name = f"{d} 그루북 {order.campus} 납품서"
    else:
        kind = f"{order.type_name}발주" if order.type_name else "발주"
        who = order.multi_name if order.order_type == "multi" else order.campus
        name = f"{d} 그루북 {who} {kind}"
    return sanitize_filename(name) + ".xlsx"


def sanitize_sheet_name(name: str) -> str:
    cleaned = _collapse(_INVALID_SHEET.sub("", name))
    cleaned = cleaned.strip("'")
    if not cleaned:
        cleaned = DELIVERY_SHEET_BASE
    return cleaned[:SHEET_NAME_MAX]


def unique_sheet_name(name: str, taken: set[str]) -> str:
    """이미 쓰인 이름이면 ' (2)', ' (3)' 을 붙이되 31자를 넘지 않도록 앞부분을 줄인다."""
    if name not in taken:
        return name
    n = 2
    while True:
        suffix = f" ({n})"
        candidate = name[: SHEET_NAME_MAX - len(suffix)].rstrip() + suffix
        if candidate not in taken:
            return candidate
        n += 1


def delivery_sheet_name(campus: str, taken: set[str], multi: bool) -> tuple[str, bool]:
    """(시트명, 원래 의도와 달라졌는지)."""
    intended = f"{DELIVERY_SHEET_BASE}_{campus}" if multi else DELIVERY_SHEET_BASE
    name = unique_sheet_name(sanitize_sheet_name(intended), taken)
    return name, name != intended
