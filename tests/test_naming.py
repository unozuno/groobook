from datetime import date
from types import SimpleNamespace

import pytest

from processors.order_form import naming

D = date(2026, 11, 8)


def _order(**kw):
    base = dict(mode="order", order_type="single", type_name="교재", campus="평촌캠퍼스", multi_name="")
    base.update(kw)
    return SimpleNamespace(**base)


def test_single_filename():
    assert naming.build_filename(_order(), D) == "261108 그루북 평촌캠퍼스 교재발주.xlsx"


def test_multi_filename_uses_typed_name():
    o = _order(order_type="multi", campus="다중", multi_name="평촌분당")
    assert naming.build_filename(o, D) == "261108 그루북 평촌분당 교재발주.xlsx"


def test_blank_order_filename_without_type():
    assert naming.build_filename(_order(mode="blank_order", type_name=""), D) == "261108 그루북 평촌캠퍼스 발주.xlsx"
    assert naming.build_filename(_order(mode="blank_order", type_name="특수"), D) == "261108 그루북 평촌캠퍼스 특수발주.xlsx"


def test_blank_delivery_filename():
    o = _order(mode="blank_delivery", campus="분당캠퍼스")
    assert naming.build_filename(o, D) == "261108 그루북 분당캠퍼스 납품서.xlsx"


def test_filename_sanitizes_forbidden_chars():
    o = _order(campus='평촌/캠퍼스:*?"<>|\\')
    assert naming.build_filename(o, D) == "261108 그루북 평촌캠퍼스 교재발주.xlsx"


def test_yymmdd_uses_seoul_date(monkeypatch):
    monkeypatch.setattr(naming, "today_seoul", lambda: date(2027, 1, 2))
    assert naming.yymmdd() == "270102"


def test_sheet_name_sanitize_and_truncate():
    assert naming.sanitize_sheet_name("납품서_대치/본원:S관?") == "납품서_대치본원S관"
    long = "납품서_" + "가" * 40
    assert len(naming.sanitize_sheet_name(long)) == 31
    assert naming.sanitize_sheet_name("[]:*?/\\") == "납품서"


def test_unique_sheet_name_appends_counter_within_limit():
    taken = {"납품서_평촌캠퍼스"}
    assert naming.unique_sheet_name("납품서_평촌캠퍼스", taken) == "납품서_평촌캠퍼스 (2)"
    taken.add("납품서_평촌캠퍼스 (2)")
    assert naming.unique_sheet_name("납품서_평촌캠퍼스", taken) == "납품서_평촌캠퍼스 (3)"
    long = "가" * 31
    assert len(naming.unique_sheet_name(long, {long})) == 31


@pytest.mark.parametrize("campus, multi, expected, adjusted", [
    ("평촌캠퍼스", True, "납품서_평촌캠퍼스", False),
    ("평촌캠퍼스", False, "납품서", False),
    ("대치/본원", True, "납품서_대치본원", True),
])
def test_delivery_sheet_name(campus, multi, expected, adjusted):
    assert naming.delivery_sheet_name(campus, set(), multi) == (expected, adjusted)
