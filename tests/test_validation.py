import pytest

from processors.order_form.models import OrderRequest
from processors.order_form.rules import apply_rules, follow_fields, type_defaults
from processors.order_form.seed import build_seed_settings
from processors.order_form.validation import parse_int, validate


@pytest.fixture
def settings():
    return build_seed_settings()


def base_request(**kw) -> OrderRequest:
    data = {
        "mode": "order", "order_type": "single", "type_id": "textbook",
        "received_date": "2026-11-08", "due_date": "2026-11-10",
        "campus": "평촌캠퍼스", "job_no": "2105",
        "spec": {"binding_method": "무선제본", "inner_size": "210*297"},
        "messages": ["사이즈 조정해 주세요"], "message_extra": "",
        "items": [
            {"name": "중2 영어", "qty": "700", "mono": "", "insert": "", "color": "2"},
            {"name": "중3 영어", "qty": 300, "mono": "10", "insert": "2", "color": ""},
        ],
    }
    data.update(kw)
    return OrderRequest.model_validate(data)


def codes(res, level):
    return [i.code for i in getattr(res, level)]


def test_parse_int():
    assert parse_int("") == (True, None)
    assert parse_int(None) == (True, None)
    assert parse_int(" 1,200 ") == (True, 1200)
    assert parse_int(5.0) == (True, 5)
    assert parse_int("3.0") == (True, 3)
    assert parse_int("-1") == (False, None)
    assert parse_int("abc") == (False, None)
    assert parse_int("1.5") == (False, None)


def test_valid_single_order(settings):
    res, order = validate(base_request(), settings)
    assert res.ok and not res.warnings
    assert order.type_name == "교재"
    assert [it.pages for it in order.items] == [2, 12]
    assert order.spec["binding_method"] == "무선제본"
    assert order.spec["cover_plate"] == ""
    assert order.messages == ["사이즈 조정해 주세요"]
    assert len(order.deliveries) == 1
    note = order.deliveries[0]
    assert note.sheet_name == "납품서"
    assert note.address.startswith("경기도 안양시")
    assert [l.qty for l in note.lines] == [700, 300]


def test_empty_item_rows_are_dropped_but_paths_keep_original_index(settings):
    req = base_request(items=[
        {"name": "", "qty": ""},
        {"name": "A", "qty": "10", "color": "x"},
    ])
    res, _ = validate(req, settings)
    assert [(i.code, i.path) for i in res.errors] == [("ITEM_NUM_INVALID", "items[1].color")]


def test_item_name_required(settings):
    req = base_request(items=[
        {"name": "A", "qty": "10"},
        {"name": " ", "qty": "5", "color": "1"},   # 이름 없이 값만 있음
        {"name": "", "qty": ""},                     # 완전히 빈 행은 무시
    ])
    res, order = validate(req, settings)
    assert order is None
    assert [(i.code, i.path) for i in res.errors] == [("ITEM_NAME_REQUIRED", "items[1].name")]
    assert "교재명" in res.errors[0].message
    req.items[1].name = "B"
    res, order = validate(req, settings)
    assert res.ok and [it.name for it in order.items] == ["A", "B"]


def test_item_name_required_in_blank_delivery(settings):
    req = base_request(mode="blank_delivery", campus="분당캠퍼스", items=[{"name": "", "qty": "5"}])
    res, _ = validate(req, settings)
    assert [(i.code, i.path) for i in res.errors] == [("ITEM_NAME_REQUIRED", "items[0].name")]
    assert "제품명" in res.errors[0].message


def test_type_required(settings):
    res, _ = validate(base_request(type_id="nope"), settings)
    assert "TYPE_REQUIRED" in codes(res, "errors")


def test_campus_required_and_receiver_required(settings):
    res, _ = validate(base_request(campus=" "), settings)
    assert "CAMPUS_REQUIRED" in codes(res, "errors")
    res, _ = validate(base_request(mode="blank_delivery", campus=""), settings)
    assert "RECEIVER_REQUIRED" in codes(res, "errors")


def test_dates(settings):
    res, _ = validate(base_request(due_date="2026/11/10"), settings)
    assert "DATE_INVALID" in codes(res, "errors")
    res, order = validate(base_request(due_date=""), settings)
    assert "DUE_DATE_MISSING" in codes(res, "warnings") and order.due_date is None


def test_no_items(settings):
    res, _ = validate(base_request(items=[{"name": "", "qty": ""}]), settings)
    assert "NO_ITEMS" in codes(res, "errors")


def test_item_warnings(settings):
    req = base_request(items=[
        {"name": "표지만", "qty": "100"},              # pages 0
        {"name": "수량없음", "qty": "", "color": "2"},  # qty empty
    ])
    res, _ = validate(req, settings)
    w = [(i.code, i.path) for i in res.warnings]
    assert ("ITEM_PAGES_ZERO", "items[0].pages") in w
    assert ("ITEM_PAGES_ZERO", "items[1].pages") not in w
    assert ("ITEM_QTY_EMPTY", "items[1].qty") in w


def test_blank_delivery_uses_pages_and_price(settings):
    req = base_request(mode="blank_delivery", order_type="single", campus="분당캠퍼스", items=[
        {"name": "노트", "qty": "50", "pages": "80", "unit_price": "1,500"},
        {"name": "뱃지", "qty": "10", "pages": "", "unit_price": "x"},
    ])
    res, _ = validate(req, settings)
    assert "ITEM_PAGES_ZERO" not in codes(res, "warnings")
    assert [(i.code, i.path) for i in res.errors] == [("PRICE_INVALID", "items[1].unit_price")]
    req.items[1].unit_price = ""
    res, order = validate(req, settings)
    assert res.ok
    assert order.items[0].pages == 80 and order.items[0].unit_price == 1500
    assert order.deliveries[0].unit_prices == [1500, None]


def test_blank_order_uses_typed_name_and_blank_spec(settings):
    req = base_request(mode="blank_order", type_id=None, type_name=" 특수 ", spec={})
    res, order = validate(req, settings)
    assert res.ok and order.type_name == "특수" and all(v == "" for v in order.spec.values())


def test_multi_recomputes_quantities_and_builds_notes(settings):
    req = base_request(order_type="multi", multi_name="평촌분당", campus="무시됨", distribution=[
        {"campus": "평촌캠퍼스", "qtys": ["700", "0"]},
        {"campus": "분당캠퍼스", "qtys": ["300", "10"]},
    ])
    req.items[0].qty = "999"  # 클라이언트 값은 무시
    res, order = validate(req, settings)
    assert res.ok and not res.warnings
    assert order.campus == "다중"
    assert [it.qty for it in order.items] == [1000, 10]
    assert [n.sheet_name for n in order.deliveries] == ["납품서_평촌캠퍼스", "납품서_분당캠퍼스"]
    assert [l.qty for l in order.deliveries[0].lines] == [700]       # 0 수량 품목 생략
    assert [l.qty for l in order.deliveries[1].lines] == [300, 10]
    assert order.deliveries[1].address.startswith("경기도 성남시")


def test_multi_errors_and_warnings(settings):
    req = base_request(order_type="multi", multi_name="", distribution=[
        {"campus": "평촌캠퍼스", "qtys": ["700", "-1"]},
        {"campus": "평촌캠퍼스", "qtys": ["1", ""]},
        {"campus": "", "qtys": ["5", ""]},
        {"campus": "", "qtys": ["", ""]},  # 완전 빈 행은 무시
    ])
    res, _ = validate(req, settings)
    e = codes(res, "errors")
    assert "MULTI_NAME_REQUIRED" in e
    assert "DIST_NUM_INVALID" in e
    assert "DIST_DUP_CAMPUS" in e
    assert "DIST_CAMPUS_EMPTY" in e
    assert e.count("DIST_CAMPUS_EMPTY") == 1


def test_multi_zero_campus_and_too_few(settings):
    req = base_request(order_type="multi", multi_name="x", distribution=[
        {"campus": "평촌캠퍼스", "qtys": ["700", "1"]},
        {"campus": "없는학원", "qtys": ["0", ""]},
    ])
    res, order = validate(req, settings)
    assert res.ok
    w = codes(res, "warnings")
    assert "DIST_CAMPUS_ZERO" in w
    assert "DIST_TOO_FEW" not in w
    assert len(order.deliveries) == 1

    req = base_request(order_type="multi", multi_name="x", distribution=[
        {"campus": "없는학원", "qtys": ["700", "1"]},
    ])
    res, order = validate(req, settings)
    w = codes(res, "warnings")
    assert "DIST_TOO_FEW" in w and "ADDRESS_NOT_FOUND" in w
    assert order.deliveries[0].address is None


def test_address_not_found_single(settings):
    res, order = validate(base_request(campus="새학원"), settings)
    assert "ADDRESS_NOT_FOUND" in codes(res, "warnings")
    assert order.deliveries[0].address is None


def test_sheet_name_adjusted_warning(settings):
    req = base_request(order_type="multi", multi_name="x", distribution=[
        {"campus": "대치/본원", "qtys": ["1", ""]},
        {"campus": "대치본원", "qtys": ["1", ""]},
    ])
    res, order = validate(req, settings)
    assert "SHEET_NAME_ADJUSTED" in codes(res, "warnings")
    assert [n.sheet_name for n in order.deliveries] == ["납품서_대치본원", "납품서_대치본원 (2)"]


# ───────── rules.py (JS 참조 구현) ─────────

def _type(settings, type_id):
    return next(t for t in settings["types"] if t["id"] == type_id)


def test_type_defaults_follow_inner_size(settings):
    tb = _type(settings, "textbook")
    spec = type_defaults(tb)
    assert spec["inner_size"] == "210*297"
    assert spec["insert_size"] == "210*297" and spec["cover_size"] == "210*297"
    assert follow_fields(tb) == {"insert_size", "cover_size"}

    note = _type(settings, "note")
    assert type_defaults(note)["cover_size"] == "210*297"
    assert follow_fields(note) == {"insert_size"}


def test_spring_binding_rule(settings):
    tb = _type(settings, "textbook")
    spec = type_defaults(tb)
    spec["binding_method"] = "스프링제본"
    out = apply_rules(spec, tb, settings["rules"])
    assert out["binding_staple"] == "양면 PVC"
    assert out["cover_coating"] == ""
    assert out["packaging"] == "박스포장"
    # 조건 해제 시 기본값 복원
    out["binding_method"] = "무선제본"
    back = apply_rules(out, tb, settings["rules"])
    assert back["binding_staple"] == "좌철" and back["cover_coating"] == "무광코팅" and back["packaging"] == "댐지포장"
    # 사용자가 직접 고친 칸은 유지
    spec["packaging"] = "댐지포장"
    kept = apply_rules(spec, tb, settings["rules"], touched={"packaging"})
    assert kept["packaging"] == "댐지포장" and kept["binding_staple"] == "양면 PVC"


def test_saddle_binding_rule(settings):
    tb = _type(settings, "textbook")
    spec = type_defaults(tb)
    spec["binding_method"] = "중철제본"
    assert apply_rules(spec, tb, settings["rules"])["binding_staple"] == ""
