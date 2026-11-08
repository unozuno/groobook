"""생성한 발주서의 원본 요청을 data/orders/ 에 JSON 으로 보관한다.

2단계(단가 자동 계산, 청구서·마케팅 집계 연동, 불러와서 수정)의 기반 데이터다.
"""
import json
from pathlib import Path

from processors.order_form.clock import now_iso, now_seoul
from processors.order_form.models import OrderRequest
from processors.order_form.settings_store import data_dir


def orders_dir() -> Path:
    return data_dir() / "orders"


def archive_order(req: OrderRequest, filename: str, warnings: list) -> Path:
    folder = orders_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stem = Path(filename).stem
    ts = now_seoul().strftime("%y%m%d_%H%M%S")
    path = folder / f"{ts}_{stem}.json"
    n = 2
    while path.exists():
        path = folder / f"{ts}_{stem} ({n}).json"
        n += 1
    payload = {
        "saved_at": now_iso(),
        "filename": filename,
        "warnings": [w.as_dict() for w in warnings],
        "order": req.model_dump(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path
