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


# ───────────────────────── 단가표 규칙 ─────────────────────────

def test_seed_has_price_rules_for_every_priced_type():
    s = validate_settings(build_seed_settings())
    by_type = {}
    for r in s["price_rules"]:
        by_type.setdefault(r["type_id"], []).append(r)
    ids = {t["id"] for t in s["types"]} | {"delivery"}   # delivery = 납품서 모드 단가
    assert set(by_type) == ids                       # 상장·초대장 등은 price=None 규칙으로 존재
    assert all(r["price"] is None for r in by_type["certificate"] + by_type["invitation"])
    assert len(by_type["textbook"]) == 28


def test_old_settings_file_without_price_rules_gets_seed(tmp_path):
    old = build_seed_settings()
    del old["price_rules"]
    settings_store.settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_store.settings_path().write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    assert len(settings_store.load_settings()["price_rules"]) > 50


def test_emptied_price_rules_are_respected():
    s = settings_store.load_settings()
    s["price_rules"] = []
    settings_store.save_settings(s)
    assert settings_store.load_settings()["price_rules"] == []


def test_price_rules_of_deleted_type_are_pruned():
    s = settings_store.load_settings()
    s["types"] = [t for t in s["types"] if t["id"] != "textbook"]
    settings_store.save_settings(s)
    assert not any(r["type_id"] == "textbook" for r in settings_store.load_settings()["price_rules"])


@pytest.mark.parametrize("mutate, fragment", [
    (lambda r: r.update(qty_min=500, qty_max=100), "수량 하한"),
    (lambda r: r["when"].update(nope=["x"]), "알 수 없는 필드"),
    (lambda r: r.update(price={"kind": "fixed"}), "금액이 필요"),
    (lambda r: r.update(price={"kind": "per_page"}), "페이지당 금액"),
    (lambda r: r.update(price={"kind": "fixed", "amount": -1}), "amount"),
])
def test_invalid_price_rule_rejected(mutate, fragment):
    s = build_seed_settings()
    mutate(s["price_rules"][0])
    with pytest.raises(SettingsValidationError) as exc:
        validate_settings(s)
    assert fragment in str(exc.value)


def test_duplicate_price_rule_id_rejected():
    s = build_seed_settings()
    s["price_rules"][1]["id"] = s["price_rules"][0]["id"]
    with pytest.raises(SettingsValidationError, match="단가 규칙 id"):
        validate_settings(s)


# ───────────────────────── 주소록 이메일 / campus_emails.json 가져오기 ─────────────────────────

def _v1_settings():
    s = build_seed_settings()
    s["schema_version"] = 1
    for a in s["address_book"]:
        a.pop("email", None)
    return s


@pytest.fixture
def legacy_json(tmp_path, monkeypatch):
    def _make(content):
        path = tmp_path / "campus_emails.json"
        path.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(settings_store, "LEGACY_EMAILS_PATH", path)
        return path
    return _make


def _write_v1(s):
    settings_store.settings_path().parent.mkdir(parents=True, exist_ok=True)
    settings_store.settings_path().write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def test_new_seed_has_empty_emails():
    s = validate_settings(build_seed_settings())
    assert s["schema_version"] == 3 and all(a["email"] == "" for a in s["address_book"])


def test_legacy_emails_fill_empty_entries_ignoring_spaces(legacy_json):
    legacy_json({"대치본원": "a@test.kr", "대치본원S관": "s@test.kr"})   # 주소록 이름은 '대치본원 S관'
    _write_v1(_v1_settings())
    book = {a["name"]: a for a in settings_store.load_settings()["address_book"]}
    assert book["대치본원"]["email"] == "a@test.kr"
    assert book["대치본원 S관"]["email"] == "s@test.kr"
    assert len(book) == 53                                   # 새 항목이 생기지 않음


def test_address_book_wins_on_conflict(legacy_json):
    legacy_json({"대치본원": "legacy@test.kr"})
    s = _v1_settings()
    s["address_book"][0]["email"] = "book@test.kr"
    _write_v1(s)
    assert settings_store.load_settings()["address_book"][0]["email"] == "book@test.kr"


def test_legacy_campus_missing_from_book_is_added(legacy_json):
    legacy_json({"신규학원": "new@test.kr", "": "x@test.kr", "빈메일": ""})
    _write_v1(_v1_settings())
    book = settings_store.load_settings()["address_book"]
    assert len(book) == 54
    assert book[-1] == {"id": "a054", "name": "신규학원", "address": "", "contact": "", "phone": "", "email": "new@test.kr"}


@pytest.mark.parametrize("content", ["{깨진 json", "[1, 2]"])
def test_legacy_file_broken_is_ignored(legacy_json, content):
    legacy_json(content)
    _write_v1(_v1_settings())
    s = settings_store.load_settings()
    assert len(s["address_book"]) == 53 and all(a["email"] == "" for a in s["address_book"])


def test_missing_legacy_file_is_ignored(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_store, "LEGACY_EMAILS_PATH", tmp_path / "없음.json")
    _write_v1(_v1_settings())
    assert settings_store.load_settings()["schema_version"] == 3


def test_migration_is_persisted_and_not_repeated(legacy_json):
    path = legacy_json({"대치본원": "a@test.kr"})
    _write_v1(_v1_settings())
    settings_store.load_settings()
    assert json.loads(settings_store.settings_path().read_text(encoding="utf-8"))["schema_version"] == 3
    s = settings_store.load_settings()
    s["address_book"][0]["email"] = ""                       # 사용자가 지운 값은 json 이 다시 채우지 않는다
    settings_store.save_settings(s)
    assert settings_store.load_settings()["address_book"][0]["email"] == ""
    assert path.exists()                                     # json 파일 자체는 건드리지 않는다


@pytest.mark.parametrize("bad", ["a@test.kr, b@test.kr", "a@test.kr;b@test.kr", "a b@test.kr", "abc", "a@b"])
def test_invalid_email_rejected(bad):
    s = build_seed_settings()
    s["address_book"][0]["email"] = bad
    with pytest.raises(SettingsValidationError, match="이메일 형식"):
        validate_settings(s)


def test_email_is_trimmed_and_blank_allowed():
    s = build_seed_settings()
    s["address_book"][0]["email"] = "  a@test.kr "
    s["address_book"][1]["email"] = "   "
    out = validate_settings(s)["address_book"]
    assert out[0]["email"] == "a@test.kr" and out[1]["email"] == ""


# ───────────────────────── 납품서 모드 단가 규칙 ─────────────────────────

def test_seed_delivery_rules():
    rules = [r for r in validate_settings(build_seed_settings())["price_rules"] if r["type_id"] == "delivery"]
    assert [r["product"] for r in rules][:2] == ["대봉투", "모의고사 대봉투"]
    elja = [r for r in rules if r["product"] == "엘자화일"]
    assert elja[0]["campuses"] == ["대치크레오", "하남크레오", "송파크레오", "키비즈"] and elja[0]["price"]["amount"] == 500
    assert elja[1]["campuses"] == [] and elja[1]["price"]["amount"] == 250     # 학원 한정 줄이 먼저
    assert [r["price"] for r in rules if r["product"].startswith("고")] == [None, None]


def test_v2_settings_get_delivery_rules_added(legacy_json):
    legacy_json("{}")
    s = _v1_settings()
    s["schema_version"] = 2
    s["price_rules"] = [r for r in build_seed_settings()["price_rules"] if r["type_id"] != "delivery"]
    _write_v1(s)
    rules = settings_store.load_settings()["price_rules"]
    assert any(r["type_id"] == "delivery" for r in rules)
    assert len([r for r in rules if r["type_id"] == "textbook"]) == 28


def test_delivery_rules_survive_type_pruning_and_validate():
    s = settings_store.load_settings()
    s["types"] = [t for t in s["types"] if t["id"] != "textbook"]
    settings_store.save_settings(s)
    assert any(r["type_id"] == "delivery" for r in settings_store.load_settings()["price_rules"])


@pytest.mark.parametrize("mutate, fragment", [
    (lambda r: r.update(product="  "), "제품명이 비어"),
    (lambda r: r.update(price={"kind": "per_page", "rate": 1}), "고정 금액"),
])
def test_invalid_delivery_rule_rejected(mutate, fragment):
    s = build_seed_settings()
    rule = next(r for r in s["price_rules"] if r["type_id"] == "delivery")
    mutate(rule)
    with pytest.raises(SettingsValidationError, match=fragment):
        validate_settings(s)


def test_product_not_allowed_on_normal_rule():
    s = build_seed_settings()
    s["price_rules"][0]["product"] = "대봉투"
    with pytest.raises(SettingsValidationError, match="납품서 단가에만"):
        validate_settings(s)
