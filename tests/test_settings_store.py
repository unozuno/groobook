import copy
import json

import pytest

from processors.order_form import settings_store
from processors.order_form.fields import FIELD_IDS
from processors.order_form.seed import build_seed_settings
from processors.order_form.settings_models import SettingsValidationError, validate_settings


def test_seed_is_valid_and_complete():
    s = validate_settings(build_seed_settings())
    names = [t["name"] for t in s["types"]]
    assert names == ["교재", "노트", "시험지", "명함", "브로셔", "안내문", "스탬프보드", "상품권",
                     "레터지", "빙고판", "포스터", "상장", "졸업장", "초대장", "엽서"]
    for t in s["types"]:
        assert set(t["fields"]) == set(FIELD_IDS)
    assert len(s["address_book"]) == 53
    assert s["address_book"][0]["name"] == "대치본원"
    assert s["address_book"][-1]["name"] == "최선 대구 수성시지"
    assert not any(a["address"].startswith("인수처 주소") for a in s["address_book"])
    assert not any(a["contact"].startswith("인수 담당자") for a in s["address_book"])
    assert not any(a["phone"] != a["phone"].strip() for a in s["address_book"])


def test_diploma_and_postcard_are_independent_copies():
    s = build_seed_settings()
    by_name = {t["name"]: t for t in s["types"]}
    assert by_name["졸업장"]["fields"] == by_name["상장"]["fields"]
    assert by_name["졸업장"]["id"] != by_name["상장"]["id"]
    by_name["졸업장"]["fields"]["cover_paper"]["options"].append("새 용지")
    assert "새 용지" not in by_name["상장"]["fields"]["cover_paper"]["options"]
    assert by_name["엽서"]["fields"] == by_name["초대장"]["fields"]


def test_first_load_writes_seed_file(isolated_data_dir):
    path = settings_store.settings_path()
    assert not path.exists()
    s = settings_store.load_settings()
    assert path.exists()
    assert s["updated_at"] is not None
    assert json.loads(path.read_text(encoding="utf-8"))["multi_label"] == "다중"


def test_save_is_atomic_and_roundtrips():
    s = settings_store.load_settings()
    s["multi_label"] = "여러 학원"
    s["messages"].append("새 문구")
    saved = settings_store.save_settings(s)
    assert saved["multi_label"] == "여러 학원"
    assert saved["updated_at"] != s["updated_at"]
    assert not settings_store.settings_path().with_suffix(".json.tmp").exists()
    again = settings_store.load_settings()
    assert again["messages"][-1] == "새 문구"


def test_save_detects_conflict():
    s = settings_store.load_settings()
    settings_store.save_settings(s)  # updated_at 변경
    with pytest.raises(settings_store.SettingsConflictError):
        settings_store.save_settings(s, expected_updated_at=s["updated_at"])


def test_reset_restores_seed():
    s = settings_store.load_settings()
    s["types"] = s["types"][:2]
    settings_store.save_settings(s)
    assert len(settings_store.load_settings()["types"]) == 2
    settings_store.reset_settings()
    assert len(settings_store.load_settings()["types"]) == 15


@pytest.mark.parametrize("mutate, fragment", [
    (lambda s: s["types"][0]["fields"]["binding_method"]["options"].append("무선제본"), "중복"),
    (lambda s: s["types"][0]["fields"]["binding_method"].__setitem__("default", "없는값"), "선택지에 없습니다"),
    (lambda s: s["types"].__setitem__(1, copy.deepcopy(s["types"][0])), "중복"),
    (lambda s: s["types"][1].__setitem__("name", "교재"), "이름이 중복"),
    (lambda s: s["address_book"][1].__setitem__("name", "대치본원"), "캠퍼스명이 중복"),
    (lambda s: s.__setitem__("unknown_key", 1), "unknown_key"),
    (lambda s: s["types"][0]["item_defaults"].__setitem__("qty", -1), "0 이상"),
    (lambda s: s.__setitem__("schema_version", 99), "버전"),
])
def test_invalid_settings_rejected(mutate, fragment):
    s = build_seed_settings()
    mutate(s)
    with pytest.raises(SettingsValidationError) as exc:
        settings_store.save_settings(s)
    assert fragment in str(exc.value)


def test_unknown_field_rejected():
    s = build_seed_settings()
    s["types"][0]["fields"]["weird"] = {"options": [], "default": None}
    with pytest.raises(SettingsValidationError):
        validate_settings(s)


def test_missing_fields_are_filled():
    s = build_seed_settings()
    del s["types"][0]["fields"]["cover_plate"]
    out = validate_settings(s)
    assert out["types"][0]["fields"]["cover_plate"] == {"options": [], "default": None}
