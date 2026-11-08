from openpyxl import Workbook, load_workbook

from processors.order_form import calc_cache as cc
from processors.order_form import reflect as rf
from processors.order_form import workbook_io as wio
from xlsx_fixtures import make_desktop

DUE = "2026-11-27"


def compute(wb, orig_cache=None, volatile=()):
    return cc.compute_cached(wb, orig_cache or {}, wio.snapshot(wb), volatile)


def make_wb():
    wb = Workbook()
    ws = wb.active
    ws.title = "견적서"
    d = wb.create_sheet("1117l자 화일")
    d["C9"], d["E9"] = 10, 250
    d["C10"], d["E10"] = 5, None                    # 단가 없는 줄은 공급액 수식이 "" 를 돌려줌
    for r in (9, 10):
        d[f"F{r}"] = f'=IF(AND(C{r}>0,E{r}<>""),C{r}*E{r},"")'
    d["C19"], d["F19"] = "=SUM(C9:C18)", "=SUM(F9:F18)"
    return wb, ws, d


def test_sum_arithmetic_and_cross_sheet_refs():
    wb, ws, d = make_wb()
    ws["G13"], ws["K13"] = "='1117l자 화일'!C19", "='1117l자 화일'!F19"
    ws["J10"], ws["K28"], ws["K29"], ws["K30"] = "=SUM(G13:H22)", "=SUM(K13:M22)", "=K28*0.1", "=SUM(K28:M29)"
    ws["A1"] = "=(1+2)*3-1"
    got = compute(wb)
    assert got["1117l자 화일"] == {"F9": 2500, "C19": 15, "F19": 2500}          # F10 은 "" 라 값 없음
    assert got["견적서"] == {"G13": 15, "K13": 2500, "J10": 15, "K28": 2500, "K29": 250, "K30": 2750, "A1": 8}


def test_unsupported_formula_is_skipped():
    wb, ws, _ = make_wb()
    ws["D5"] = "=VLOOKUP(D4,[1]팀장!$A$2:$D$30,2,0)"
    ws["D6"] = "=ROUND(A1*1.5,0)"
    ws["D7"] = "=A1/0"
    assert "견적서" not in compute(wb)


def test_original_cache_used_only_for_unchanged_formula_on_stable_sheet():
    wb, ws, d = make_wb()
    d["H9"] = "=ROUND(C9*1.5,0)"                  # 직접 계산하지 않는 수식 → 원본 캐시
    ws["H9"] = "=ROUND(C9*1.5,0)"
    cache = {"1117l자 화일": {"H9": 15}, "견적서": {"H9": 15}}
    got = compute(wb, cache, volatile=("견적서",))
    assert got["1117l자 화일"]["H9"] == 15
    assert "H9" not in got.get("견적서", {})        # 값이 바뀌는 시트는 원본 캐시를 믿지 않음

    snap = wio.snapshot(wb)
    d["H9"] = "=ROUND(C9*2,0)"                       # 수식이 바뀌었으면 원본 값은 무효
    assert "H9" not in cc.compute_cached(wb, cache, snap)["1117l자 화일"]


def test_formula_depending_on_cached_external_value_uses_cache_inside_sum():
    wb, ws, d = make_wb()
    d["C10"] = "=ROUND(2*3.3,0)"                   # 계산 불가 → 원본 캐시 7 (수량 합계에 반영)
    d["C9"] = 10
    got = compute(wb, {"1117l자 화일": {"C10": 7}})
    assert got["1117l자 화일"]["C19"] == 17


def test_old_rows_are_healed_when_new_row_is_reflected(make_order, tmp_path):
    """캐시가 비어 있는 예전 시트·견적서 줄도 반영할 때 값이 채워진다."""
    desk = make_desktop(tmp_path / "d")
    inv = next((tmp_path / "d").glob("*매출청구서_소모품/*분당*.xlsx"))
    assert load_workbook(inv, data_only=True)["견적서"]["G13"].value is None
    order = make_order(campus="분당캠퍼스", due_date=DUE, items=[{"name": "신규", "qty": "10", "unit_price": "100"}])
    assert [i.status for i in rf.reflect(order, {"invoice": True}, str(desk), dry_run=False).items] == ["done"]
    est = load_workbook(inv, data_only=True)["견적서"]
    assert est["G13"].value == 54                      # 예전 줄: 1008내신블랭크 시트의 C17
    assert (est["G14"].value, est["K14"].value) == (10, 1000)
    assert est["J10"].value == 64 and est["K28"].value == 1000
