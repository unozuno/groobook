import re
from pathlib import Path

import pytest

from processors.order_form.models import Item
from processors.order_form.pricing import quote
from processors.order_form.seed_prices import SEED_PRICE_RULES

RULES = SEED_PRICE_RULES
SAMPLE = Path(__file__).resolve().parents[1] / "sample" / "발주서 단일화.xlsx"

TEXTBOOK = {"binding_method": "무선제본", "inner_paper": "80g 미색모조", "inner_print": "양면 2도",
            "inner_size": "210*297"}


def item(qty=100, pages=100):
    return Item(name="x", qty=qty, mono=pages, insert=None, color=None, pages=pages)


def q(type_id, spec, it=None, mode="order", name="교재"):
    return quote(mode, type_id, name, spec, it or item(), RULES)


def test_textbook_per_page_formula():
    r = q("textbook", TEXTBOOK)
    assert (r.status, r.price) == ("auto", 100 * 30 + 600)


@pytest.mark.parametrize("override, expected", [
    ({"binding_method": "스프링제본"}, 100 * 30 + 2500),
    ({"binding_method": "중철제본"}, 100 * 30 + 600),
    ({"inner_paper": "100g 백색모조"}, 100 * 33 + 600),     # 쉼표 목록의 두 번째 값
    ({"inner_print": "양면 8도"}, 100 * 50 + 600),
    ({"inner_size": "148*210"}, 100 * 20 + 600),
    ({"inner_size": "148*210", "inner_print": "양면 8도", "inner_paper": "120g 미색모조"}, 100 * 38 + 600),
])
def test_textbook_combinations(override, expected):
    assert q("textbook", {**TEXTBOOK, **override}).price == expected


def test_textbook_combination_not_in_table_is_manual():
    r = q("textbook", {**TEXTBOOK, "inner_print": "양면 4도"})
    assert r.status == "manual" and "단가표에 없는 조합" in r.reason


def test_spec_values_compare_without_spaces():
    r = q("poster", {"cover_size": "420*594", "cover_paper": "200스노우"}, item(qty=5, pages=1), name="포스터")
    assert (r.status, r.price) == ("auto", 6000)


@pytest.mark.parametrize("qty, expected", [(1, 10000), (9, 10000), (10, 9000), (29, 9000), (30, 7000),
                                           (49, 7000), (50, 5000), (999, 5000)])
def test_quantity_tier_boundaries(qty, expected):
    spec = {"cover_size": "594*420", "cover_paper": "스티커형 인쇄"}
    assert q("poster", spec, item(qty=qty, pages=1), name="포스터").price == expected


def test_quantity_outside_all_tiers_is_manual():
    spec = {"cover_size": "594*420", "cover_paper": "스티커형 인쇄"}
    assert q("poster", spec, item(qty=1000, pages=1), name="포스터").status == "manual"


@pytest.mark.parametrize("qty, expected", [(299, 600), (300, 550), (499, 550), (500, 400), (1000, 300)])
def test_leaflet_tiers_by_total_quantity(qty, expected):
    spec = {"cover_size": "210*297"}
    assert q("leaflet", spec, item(qty=qty, pages=1), name="안내문").price == expected


def test_leaflet_pages_must_match_exactly():
    spec = {"cover_size": "210*297"}
    assert q("leaflet", spec, item(qty=100, pages=2), name="안내문").price == 1000
    assert q("leaflet", spec, item(qty=100, pages=4), name="안내문").price == 1500
    assert q("leaflet", spec, item(qty=100, pages=3), name="안내문").status == "manual"


def test_brochure_per_page_with_tier():
    spec = {"inner_print": "단면 4도"}
    assert q("brochure", spec, item(qty=499, pages=4), name="브로셔").price == 4 * 70 + 1000
    assert q("brochure", spec, item(qty=500, pages=4), name="브로셔").price == 4 * 70 + 800


@pytest.mark.parametrize("type_id, spec, expected", [
    ("business_card", {}, 25000),
    ("stamp_board", {}, 300),
    ("exam_paper", {}, 100 * 30 + 600),
    ("letter_paper", {"inner_paper": "120g 미색모조"}, 60),
])
def test_flat_and_unconditional_rules(type_id, spec, expected):
    assert q(type_id, spec, name=type_id).price == expected


@pytest.mark.parametrize("type_id", ["certificate", "diploma", "invitation", "postcard"])
def test_manual_types(type_id):
    r = q(type_id, {}, name="상장")
    assert r.status == "manual" and "직접 입력" in r.reason


def test_blank_order_is_always_manual():
    r = q("textbook", TEXTBOOK, mode="blank_order")
    assert r.status == "manual" and "직접 입력" in r.reason


# ───── 빈 납품서(납품명세서) ─────

def dq(name, campus="분당캠퍼스"):
    return quote("blank_delivery", None, "", {}, Item(name=name, qty=10, mono=None, insert=None, color=None, pages=0),
                 RULES, campus)


@pytest.mark.parametrize("name, price", [
    ("대봉투", 200), ("모의고사 대봉투", 200), ("소봉투", 100), ("적박소봉투", 150),
    ("쇼핑백", 1400), ("브랜드 브로셔", 3720), ("비닐봉투", 200), ("엘자화일", 250),
])
def test_delivery_default_prices(name, price):
    r = dq(name)
    assert (r.status, r.price) == ("auto", price)


def test_delivery_campus_specific_prices_override_default():
    for campus in ("대치크레오", "하남크레오", "송파크레오"):
        assert dq("비닐봉투", campus).price == 300
        assert dq("엘자화일", campus).price == 500
    assert dq("엘자화일", "키비즈").price == 500
    assert dq("비닐봉투", "키비즈").price == 200            # 키비즈는 엘자화일만 특가
    assert dq("엘자화일", "분당캠퍼스").price == 250


def test_delivery_campus_and_name_compare_ignore_spaces():
    assert dq("엘자 화일", "키 비즈").price == 500
    assert dq("모의고사대봉투").price == 200


@pytest.mark.parametrize("name", ["고3 모의고사 대봉투", "고2 봉투모의고사 대봉투"])
def test_delivery_blue_cells_are_manual(name):
    r = dq(name)
    assert r.status == "manual" and "직접 입력" in r.reason


def test_delivery_unknown_product_is_manual():
    r = dq("처음 보는 제품")
    assert r.status == "manual" and "납품명세서 단가표에 없는 제품" in r.reason


def test_type_without_any_rule_is_manual():
    r = quote("order", "custom", "신규", {}, item(), RULES)
    assert r.status == "manual" and "단가표가 없어" in r.reason


# ───── 엑셀 원본(sample)과의 일치 — 파일이 있을 때만 ─────

def _sheet_rows():
    from openpyxl import load_workbook
    ws = load_workbook(SAMPLE, data_only=False)["단가표"]
    return [ws[f"K{r}"].value for r in range(3, 99) if ws[f"K{r}"].value is not None]


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample/발주서 단일화.xlsx 없음")
def test_every_sheet_row_matches_its_rule_and_is_not_shadowed():
    prices = _sheet_rows()
    priced = [r for r in RULES if r["price"] is not None and r["type_id"] != "delivery"]
    assert len(prices) == len(priced)
    for raw, rule in zip(prices, priced):
        spec = {f: vals[0] for f, vals in rule["when"].items()}
        it = item(qty=rule["qty_min"] or 100, pages=rule["pages"] if rule["pages"] is not None else 100)
        r = quote("order", rule["type_id"], rule["type_id"], spec, it, RULES)
        if isinstance(raw, (int, float)):
            expected = int(raw)
        else:
            a, b = map(int, re.fullmatch(r"페이지\*(\d+)\+(\d+)", raw).groups())
            expected = it.pages * a + b
        assert (r.status, r.price) == ("auto", expected), (rule["id"], raw)
