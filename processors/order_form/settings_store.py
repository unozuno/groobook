"""관리자 설정 파일(data/order_settings.json) 읽기·쓰기.

- 파일이 없으면 시드로 생성한다.
- 쓰기는 임시 파일 → os.replace 로 원자적으로 수행하고, 모듈 락으로 동시 쓰기를 직렬화한다.
- 저장 위치는 환경변수 GROOBOOK_DATA_DIR 로 바꿀 수 있다 (기본: 프로젝트 루트 data/).
"""
import copy
import json
import os
import threading
from pathlib import Path

from processors.order_form.clock import now_iso
from processors.order_form.desktop_paths import norm_name
from processors.order_form.seed import SCHEMA_VERSION, build_seed_settings
from processors.order_form.seed_prices import SEED_PRICE_RULES
from processors.order_form.settings_models import SettingsValidationError, validate_settings

SETTINGS_FILENAME = "order_settings.json"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_lock = threading.Lock()


class SettingsConflictError(Exception):
    """클라이언트가 읽은 이후 다른 곳에서 설정이 수정됨."""


def data_dir() -> Path:
    override = os.environ.get("GROOBOOK_DATA_DIR")
    return Path(override) if override else _PROJECT_ROOT / "data"


def settings_path() -> Path:
    return data_dir() / SETTINGS_FILENAME


def _write_atomic(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


LEGACY_EMAILS_PATH = _PROJECT_ROOT / "campus_emails.json"


def _merge_campus_emails(data: dict, path: Path | None = None) -> None:
    """v1→v2: 주소록에 email 칸을 만들고, 예전 campus_emails.json(학원명→메일)을 한 번 가져온다.
    주소록에 이미 메일이 있으면 그 값을 유지하고(주소록 우선), 주소록에 없는 학원은 새 항목으로 추가한다."""
    book = data.setdefault("address_book", [])
    for entry in book:
        entry.setdefault("email", "")
    path = path or LEGACY_EMAILS_PATH
    try:
        with open(path, encoding="utf-8") as f:
            legacy = json.load(f)
    except (OSError, ValueError):
        return
    if not isinstance(legacy, dict):
        return
    by_name = {norm_name(e.get("name", "")): e for e in book}
    next_no = len(book) + 1
    for name, email in legacy.items():
        if not isinstance(name, str) or not isinstance(email, str) or not name.strip() or not email.strip():
            continue
        entry = by_name.get(norm_name(name))
        if entry is not None:
            if not entry.get("email"):
                entry["email"] = email.strip()
            continue
        existing_ids = {e.get("id") for e in book}
        while f"a{next_no:03d}" in existing_ids:
            next_no += 1
        new = {"id": f"a{next_no:03d}", "name": name.strip(), "address": "", "contact": "", "phone": "",
               "email": email.strip()}
        book.append(new)
        by_name[norm_name(new["name"])] = new


def migrate(data: dict) -> dict:
    """스키마 버전 업그레이드 지점. 상위 버전은 거부하고, 단가표가 없던 옛 파일에는 초기 단가표를 채운다."""
    version = data.get("schema_version", 1)
    if version > SCHEMA_VERSION:
        raise SettingsValidationError(
            [f"설정 파일 버전({version})이 프로그램이 지원하는 버전({SCHEMA_VERSION})보다 높습니다."]
        )
    if version < 2:
        _merge_campus_emails(data)
    data["schema_version"] = SCHEMA_VERSION
    if "price_rules" not in data:   # 키 자체가 없을 때만 (관리자가 비운 [] 는 존중)
        data["price_rules"] = copy.deepcopy(SEED_PRICE_RULES)
    return data


def _load_unlocked() -> dict:
    path = settings_path()
    if not path.exists():
        seed = validate_settings(build_seed_settings())
        seed["updated_at"] = now_iso()
        _write_atomic(path, seed)
        return seed
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    old_version = data.get("schema_version", 1)
    result = validate_settings(migrate(data))
    if old_version < SCHEMA_VERSION:      # 업그레이드 결과를 저장해 두어 다음부터는 다시 병합하지 않는다
        _write_atomic(path, result)
    return result


def load_settings() -> dict:
    with _lock:
        return _load_unlocked()


def save_settings(data: dict, expected_updated_at: str | None = None) -> dict:
    """검증 후 저장. expected_updated_at 이 주어지면 현재 파일의 updated_at 과 비교한다."""
    with _lock:
        if expected_updated_at is not None and settings_path().exists():
            current = _load_unlocked()
            if current.get("updated_at") != expected_updated_at:
                raise SettingsConflictError("다른 곳에서 설정이 수정되었습니다. 새로고침 후 다시 저장해 주세요.")
        normalized = validate_settings(migrate(dict(data)))
        normalized["updated_at"] = now_iso()
        _write_atomic(settings_path(), normalized)
        return normalized


def reset_settings() -> dict:
    with _lock:
        seed = validate_settings(build_seed_settings())
        seed["updated_at"] = now_iso()
        _write_atomic(settings_path(), seed)
        return seed
