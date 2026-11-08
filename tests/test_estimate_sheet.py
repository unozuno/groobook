import pytest
from openpyxl import Workbook

from processors.order_form import estimate_sheet as es
from xlsx_fixtures import ESTIMATE_FIRST, ESTIMATE_LAST, build_estimate


def make_ws(filled=1):
    wb = Workbook()
    ws = wb.active
    ws.title = "견적서"
    build_estimate(ws, filled=filled, existing_sheets=[f"s{i}" for i in range(10)])
    return wb, ws


def fill(ws, layout, n):
    for i in range(n):
        row = es.find_free_row(ws, layout)
        if row is None:
            row = es.insert_item_row(ws, layout)
            layout = es.find_layout(ws)
        es.write_item_row(ws, layout, row, f"제품{i}", f"시트{i}", 19, 11, 27)
    return es.find_layout(ws)


def test_layout_found():
    _, ws = make_ws()
    lay = es.find_layout(ws)
    assert (lay.header_row, lay.first, lay.last, lay.separator) == (12, ESTIMATE_FIRST, ESTIMATE_LAST, 23)
    assert lay.cols["품목"] == 2 and lay.cols["적요"] == 4 and lay.cols["수량"] == 7 and lay.cols["금액"] == 11 and lay.cols["비고"] == 14


def test_layout_missing_raises():
    ws = Workbook().active
    ws["A1"] = "무관한 시트"
    with pytest.raises(es.EstimateError):
        es.find_layout(ws)


def test_free_row_is_first_empty_line():
    _, ws = make_ws(filled=3)
    lay = es.find_layout(ws)
    assert es.find_free_row(ws, lay) == 16


def test_write_item_row_values_and_formulas():
    _, ws = make_ws(filled=0)
    lay = es.find_layout(ws)
    es.write_item_row(ws, lay, 13, "엘자화일 외", "1030엘자화일외(재)", 19, 10, 8)
    assert ws["B13"].value == "소모품" and ws["D13"].value == "엘자화일 외"
    assert ws["G13"].value == "='1030엘자화일외(재)'!C19" and ws["K13"].value == "='1030엘자화일외(재)'!F19"
    assert ws["N13"].value == "10/8 납품"                       # 0 을 채우지 않음
    assert ws["F13"].value is None and ws["I13"].value is None


def test_sheet_name_with_apostrophe_is_escaped():
    assert es.quote_sheet("1127O'Neil") == "'1127O''Neil'"


@pytest.mark.parametrize("src, expected", [
    ("=SUM(K13:M22)", "=SUM(K13:M23)"),                      # 구분줄 바로 위에서 끝나는 범위는 끝 행도 늘어남
    ("=SUM(G13:H22)", "=SUM(G13:H23)"),
    ("=I28", "=I29"), ("=K28*0.1", "=K29*0.1"), ("=SUM(K28:M29)", "=SUM(K29:M30)"),
    ("=K30", "=K31"), ("=C5+C6", "=C5+C6"), ("=$A$30+B$1", "=$A$31+B$1"),
    ("='1030상품권'!C14", "='1030상품권'!C14"),                # 다른 시트 참조는 그대로
    ("=VLOOKUP(D4,[1]팀장!$A$2:$D$30,2,0)", "=VLOOKUP(D4,[1]팀장!$A$2:$D$30,2,0)"),
    ("=SUM(A1:A5)", "=SUM(A1:A5)"), ("텍스트", "텍스트"),
])
def test_shift_formula(src, expected):
    assert es.shift_formula(src, 23) == expected


def test_insert_moves_everything_below_by_one():
    _, ws = make_ws(filled=10)
    lay = es.find_layout(ws)
    assert es.find_free_row(ws, lay) is None
    heights_before = {r: ws.row_dimensions[r].height for r in range(1, 37)}
    merges_before = {str(r) for r in ws.merged_cells.ranges}
    row = es.insert_item_row(ws, lay)
    assert row == 23
    # 값
    assert ws["B24"].value is None and ws["D25"].value == "표  지" and ws["D29"].value == "공 급 가"
    # 수식
    assert ws["J10"].value == "=SUM(G13:H23)" and ws["I29"].value == "=SUM(K13:M23)"
    assert ws["K29"].value == "=I29" and ws["K30"].value == "=K29*0.1" and ws["K31"].value == "=SUM(K29:M30)"
    assert ws["M10"].value == "=K31" and ws["D5"].value == "=VLOOKUP(D4,[1]팀장!$A$2:$D$30,2,0)"
    # 병합: 아래는 한 줄씩, 새 줄은 품목 줄 패턴, 위는 그대로
    merges = {str(r) for r in ws.merged_cells.ranges}
    assert {"B24:O24", "K29:M29", "K31:M31", "B32:O36", "D25:E25", "F25:O25", "B25:C27"} <= merges
    assert {"B23:C23", "D23:E23", "G23:H23", "I23:J23", "K23:M23", "N23:O23"} <= merges
    assert {"B1:F1", "B13:C13", "N22:O22"} <= merges
    assert len(merges) == len(merges_before) + 6
    # 행 높이·인쇄영역
    for r in range(24, 37):
        assert ws.row_dimensions[r].height == heights_before[r - 1]
    assert ws.row_dimensions[23].height == heights_before[22]
    assert ws.print_area.endswith("$O$36")


def test_repeated_inserts_stay_consistent():
    _, ws = make_ws(filled=10)
    lay = fill(ws, es.find_layout(ws), 13)               # 빈 줄 0 + 새 줄 13개 → 삽입 13번
    assert lay.last == ESTIMATE_LAST + 13
    assert ws[f"I{28 + 13}"].value == f"=SUM(K13:M{ESTIMATE_LAST + 13})"
    assert ws["J10"].value == f"=SUM(G13:H{ESTIMATE_LAST + 13})"
    assert ws[f"K{30 + 13}"].value == f"=SUM(K{28 + 13}:M{29 + 13})"
    assert ws["M10"].value == f"=K{30 + 13}"
    assert ws[f"D{24 + 13}"].value == "표  지"
    assert ws.print_area.endswith(f"$O${35 + 13}")


def test_insert_refuses_merge_spanning_insertion_point():
    _, ws = make_ws()
    ws.merge_cells("P20:P24")
    lay = es.find_layout(ws)
    with pytest.raises(es.EstimateError):
        es.insert_item_row(ws, lay)
