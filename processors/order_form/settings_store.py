"""관리자 설정 파일(data/order_settings.json) 읽기·쓰기.

- 파일이 없으면 시드로 생성한다.
- 쓰기는 임시 파일 → os.replace 로 원자적으로 수행하고, 모듈 락으로 동시 쓰기를 직렬화한다.
- 저장 위치는 환경변수 GROOBOOK_DATA_DIR 로 바꿀 수 있다 (기본: 프로젝트 루트 data/).
"""
import json
import os
import threading
from pathlib import Path

from processors.order_form.clock import now_iso
from processors.order_form.seed import SCHEMA_VERSION, build_seed_settings
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


def migrate(data: dict) -> dict:
    """스키마 버전 업그레이드 지점. 현재는 v1 뿐이라 상위 버전만 거부한다."""
    version = data.get("schema_version", 1)
    if version > SCHEMA_VERSION:
        raise SettingsValidationError(
            [f"설정 파일 버전({version})이 프로그램이 지원하는 버전({SCHEMA_VERSION})보다 높습니다."]
        )
    data["schema_version"] = SCHEMA_VERSION
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
    return validate_settings(migrate(data))


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
