from datetime import datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook

from processors.order_form.verify import OrderVerifyError, verify_workbook
from processors.order_form.xlsx_builder import build_workbook


def _wb(order):
    data = build_workbook(order)
    return data, load_workbook(BytesIO(data))


def test_single_order_layout(sample_order):
    data, wb = _wb(sample_order)
    assert wb.sheetnames == ["발주서", "납품서"]
    ws = wb["발주서"]
    assert (ws["C1"].value, ws["D1"].value, ws["F1"].value) == ("그루북", "교재", "제작 요청서")
    # 입력칸 노란 배경은 쓰지 않는다 (머리글 연두색만 유지)
    assert all(c.fill.fill_type is None for row in ws.iter_rows(min_row=2, max_row=9) for c in row)
    assert all(c.fill.fill_type is None for c in ws[1] if c.column not in (4, 5))
    assert all(c.fill.fill_type is None for row in ws.iter_rows(min_row=11, max_row=21, min_col=1, max_col=14) for c in row)
    assert ws["C2"].value == datetime(2026, 11, 8) and ws["F2"].value == datetime(2026, 11, 10)
    assert ws["C3"].value == "평촌캠퍼스" and ws["I3"].value == 2105
    assert (ws["C4"].value, ws["D4"].value) == ("무선제본", "좌철")
    assert (ws["C5"].value, ws["D5"].value, ws["E5"].value) == ("80g 미색모조", "양면 2도", "210*297")
    assert ws["C6"].value == "90g 청간지"
    assert (ws["C7"].value, ws["D7"].value, ws["E7"].value, ws["F7"].value, ws["G7"].value) == \
        ("250g 아트지", "단면 4도", "210*297", "무광코팅", None)
    assert ws["C8"].value == "댐지포장"
    # 9행 전달사항: 빨간 큰 글씨, 병합
    assert ws["B9"].value == "첫, 마지막 페이지 표지입니다\n쪽번호 붙여 주세요"
    assert ws["B9"].font.color.rgb.endswith("FF0000") and ws["B9"].font.size == 14
    assert "B9:J9" in [str(r) for r in ws.merged_cells.ranges]
    # 머리글
    assert [ws.cell(10, c).value for c in range(1, 11)] == \
        ["표지no", "학교", "교재명", "본문no", "발주수량", "1도", "청간지", "4도", "페이지합계", "덩이수"]
    assert ws["A10"].fill.fgColor.rgb.endswith("92D050")
    # 품목
    assert ws["C11"].value == "중2 영어 내신" and ws["E11"].value == 700 and ws["H11"].value == 2
    assert ws["B11"].value is None and ws["J11"].value is None
    assert ws["D11"].value == "=A11" and ws["I11"].value == "=F11+G11+H11"
    assert ws["K11"].value == "=$E11*F11" and ws["N11"].value == "=SUM(K11:M11)"
    # 품목 수(3)만큼만 행을 만들고 바로 아래가 합계 행
    assert ws["A13"].value == 3 and ws["C13"].value == "교사용"
    assert ws["A14"].value == "합계" and ws["E14"].value == "=SUM(E11:E13)" and ws["N14"].value == "=SUM(K14:M14)"
    assert ws["A15"].value is None and ws["N15"].value is None
    assert wb.calculation.fullCalcOnLoad is True
    assert not wb._external_links
    verify_workbook(data, sample_order)


def test_order_item_name_centered(sample_order):
    _, wb = _wb(sample_order)
    ws = wb["발주서"]
    names = [ws[f"C{r}"] for r in range(11, 22) if ws[f"C{r}"].value]
    assert names and all(c.alignment.horizontal == "center" for c in names)


def test_delivery_sheet_layout(sample_order):
    data, wb = _wb(sample_order)
    ws = wb["납품서"]
    assert ws["A1"].value == "납   품   명   세   서"
    assert ws["C3"].value == datetime(2026, 11, 10) and ws["F3"].value is None   # 납품서에는 작업번호 없음
    assert ws["C5"].value == "평촌캠퍼스" and ws["F5"].value == "그루북"
    assert (ws["D8"].value, ws["E8"].value, ws["F8"].value) == ("페이지", "단가", "공급액")
    assert (ws["B9"].value, ws["C9"].value, ws["D9"].value, ws["E9"].value) == ("중2 영어 내신", 700, 2, 660)
    assert ws["E11"].value == 1200
    assert ws["F9"].value == '=IF(AND(C9>0,E9<>""),C9*E9,"")'
    # 3건 → 5행 (9~13), 합계 14행
    assert ws["A14"].value == "합계" and ws["C14"].value == "=SUM(C9:C13)" and ws["F14"].value == "=SUM(F9:F13)"
    assert ws["A16"].value.startswith("인수처 주소 : 경기도 안양시")
    assert ws["A17"].value == "인수 담당자 : 김경민 과장님 (010-5125-7196)"
    assert (ws["E17"].value, ws["F17"].value) == ("서명", "      (인)")


def test_many_items_grow_table(make_order):
    items = [{"name": f"품목{i}", "qty": str(10 * (i + 1)), "mono": "1", "color": "2"} for i in range(13)]
    order = make_order(items=items)
    data, wb = _wb(order)
    ws = wb["발주서"]
    assert ws["A23"].value == 13 and ws["C23"].value == "품목12"
    assert ws["A24"].value == "합계" and ws["E24"].value == "=SUM(E11:E23)" and ws["K24"].value == "=SUM(K11:K23)"
    assert ws["A25"].value is None
    d = wb["납품서"]
    assert d["A22"].value == "합계" and d["C22"].value == "=SUM(C9:C21)"
    assert d["A24"].value.startswith("인수처 주소")
    verify_workbook(data, order)


def test_multi_order_sheets(sample_multi_order):
    data, wb = _wb(sample_multi_order)
    assert wb.sheetnames == ["발주서", "납품서_평촌캠퍼스", "납품서_분당캠퍼스"]
    ws = wb["발주서"]
    assert ws["C3"].value == "다중"
    assert [ws.cell(r, 5).value for r in (11, 12, 13)] == [1000, 10, 5]
    p = wb["납품서_평촌캠퍼스"]
    assert [(p.cell(r, 2).value, p.cell(r, 3).value) for r in (9, 10, 11)] == \
        [("중2 영어 내신", 700), ("교사용", 5), (None, None)]
    b = wb["납품서_분당캠퍼스"]
    assert [(b.cell(r, 2).value, b.cell(r, 3).value) for r in (9, 10)] == [("중2 영어 내신", 300), ("중3 영어 내신", 10)]
    assert b["C3"].value == datetime(2026, 11, 10) and b["F3"].value is None
    assert b["A16"].value.startswith("인수처 주소 : 경기도 성남시")
    verify_workbook(data, sample_multi_order)


def test_address_missing_leaves_prefix_only(make_order):
    order = make_order(campus="새학원")
    _, wb = _wb(order)
    ws = wb["납품서"]
    assert ws["A16"].value == "인수처 주소 :" and ws["A17"].value == "인수 담당자 :"


def test_blank_delivery_only_sheet(make_order):
    order = make_order(mode="blank_delivery", campus="분당캠퍼스", items=[
        {"name": "노트", "qty": "50", "pages": "80", "unit_price": "1500"},
    ])
    data, wb = _wb(order)
    assert wb.sheetnames == ["납품서"]
    ws = wb["납품서"]
    assert (ws["B9"].value, ws["C9"].value, ws["D9"].value, ws["E9"].value) == ("노트", 50, 80, 1500)
    verify_workbook(data, order)


def test_blank_order_has_empty_type_and_spec(make_order):
    order = make_order(mode="blank_order", type_id=None, type_name="", spec={}, messages=[],
                       items=[{"name": "A", "qty": "10", "unit_price": "100"}])
    _, wb = _wb(order)
    ws = wb["발주서"]
    assert ws["D1"].value is None and ws["C4"].value is None and ws["B9"].value is None
    assert "B9:J9" not in [str(r) for r in ws.merged_cells.ranges]


def test_job_no_text_preserved(make_order):
    order = make_order(job_no="A-007")
    _, wb = _wb(order)
    assert wb["발주서"]["I3"].value == "A-007"


def test_verify_detects_tampered_formula(sample_order):
    data = build_workbook(sample_order)
    wb = load_workbook(BytesIO(data))
    wb["발주서"]["K11"].value = "=$E11*H11"
    buf = BytesIO()
    wb.save(buf)
    with pytest.raises(OrderVerifyError):
        verify_workbook(buf.getvalue(), sample_order)


def _sides(c):
    b = c.border
    return tuple(getattr(x, "style", None) for x in (b.left, b.right, b.top, b.bottom))


def test_order_sheet_format(sample_order):
    _, wb = _wb(sample_order)
    ws = wb["발주서"]
    # 날짜 중앙, 제작 종류 빨강, 납기일자 라벨은 E2 단일 셀
    assert ws["C2"].alignment.horizontal == "center" and ws["F2"].alignment.horizontal == "center"
    assert ws["D1"].font.color is None or ws["D1"].font.color.rgb in (None, "FF000000")   # 검정
    assert ws["D1"].fill.fgColor.rgb.endswith("FCD582")
    assert ws["E2"].value == "납기일자" and ws["H2"].value is None
    merged = [str(r) for r in ws.merged_cells.ranges]
    assert "F2:H2" in merged and "H2:J2" not in merged
    # 열 너비(엑셀 단위): C 33, A~J 나머지 11
    assert ws.column_dimensions["C"].width == 33
    for col in "ABDEFGHIJ":
        assert ws.column_dimensions[col].width == 11
    # 표 바깥(머리글 10행 ~ 합계 14행, A~J)은 medium, 안쪽은 thin
    assert _sides(ws["A10"]) == ("medium", "thin", "medium", "thin")
    assert _sides(ws["J10"]) == ("thin", "medium", "medium", "thin")
    assert _sides(ws["A14"])[0] == "medium" and _sides(ws["A14"])[3] == "medium"
    assert _sides(ws["J14"]) == ("thin", "medium", "thin", "medium")
    assert _sides(ws["E11"]) == ("thin", "thin", "thin", "thin")


@pytest.mark.parametrize("n,rows", [(1, 5), (5, 5), (6, 10), (10, 10), (11, 11), (13, 13)])
def test_delivery_row_count_steps(make_order, n, rows):
    items = [{"name": f"품목{i}", "qty": "10", "unit_price": "100"} for i in range(n)]
    order = make_order(items=items)
    data, wb = _wb(order)
    ws = wb["납품서"]
    total = 9 + rows
    assert ws.cell(total, 1).value == "합계" and ws.cell(total, 3).value == f"=SUM(C9:C{total - 1})"
    assert ws.cell(total - 1, 1).value == rows and ws.cell(total + 1, 1).value is None
    verify_workbook(data, order)


def test_delivery_sheet_format(sample_order):
    _, wb = _wb(sample_order)
    ws = wb["납품서"]
    # D5: 좌우 테두리만
    assert _sides(ws["D5"]) == ("thin", "thin", None, None)
    # 표 바깥(7행 ~ 합계 14행, A~F)은 medium
    assert _sides(ws["A7"])[0] == "medium" and _sides(ws["A7"])[2] == "medium"
    assert _sides(ws["F8"])[1] == "medium"
    assert _sides(ws["A14"])[0] == "medium" and _sides(ws["A14"])[3] == "medium"
    assert _sides(ws["F14"])[1] == "medium" and _sides(ws["F14"])[3] == "medium"
    assert _sides(ws["B10"]) == ("thin", "thin", "thin", "thin")
    # 서명 라벨 좌정렬
    assert ws["E17"].alignment.horizontal == "left"


def test_delivery_extras_follow_items_and_count_for_rows(make_order):
    items = [{"name": f"품목{i}", "qty": "10", "unit_price": "100"} for i in range(5)]
    order = make_order(items=items, extras=[{"name": "택배비", "qty": "1", "unit_price": "3000"}])
    data, wb = _wb(order)
    ws = wb["납품서"]
    # 품목 5 + 추가 1 = 6줄 → 10행 (9~18), 합계 19행
    assert (ws["A14"].value, ws["B14"].value, ws["C14"].value, ws["D14"].value, ws["E14"].value) == (6, "택배비", 1, None, 3000)
    assert ws["F14"].value == '=IF(AND(C14>0,E14<>""),C14*E14,"")'
    assert ws["A19"].value == "합계" and ws["C19"].value == "=SUM(C9:C18)"
    # 발주서 시트에는 추가 항목이 없다
    assert all(wb["발주서"].cell(r, 3).value != "택배비" for r in range(1, 30))
    verify_workbook(data, order)


def test_delivery_extras_only_in_their_campus_sheet(make_order):
    order = make_order(order_type="multi", multi_name="묶음", items=[{"name": "A", "color": "2", "unit_price": "100"}],
                       distribution=[{"campus": "평촌캠퍼스", "qtys": ["10"]}, {"campus": "분당캠퍼스", "qtys": ["5"]}],
                       extras_by_campus=[{"campus": "분당캠퍼스", "extras": [{"name": "디자인비", "qty": "1", "unit_price": "50000"}]}])
    data, wb = _wb(order)
    assert wb["납품서_평촌캠퍼스"]["B10"].value is None
    assert wb["납품서_분당캠퍼스"]["B10"].value == "디자인비"
    verify_workbook(data, order)


def test_delivery_numeric_columns_right_aligned(sample_order):
    _, wb = _wb(sample_order)
    ws = wb["납품서"]
    for r in range(9, 15):          # 품목 줄 ~ 합계 줄
        for col in "CDEF":
            assert ws[f"{col}{r}"].alignment.horizontal == "right", f"{col}{r}"
    assert ws["A14"].alignment.horizontal == "center"


def test_delivery_double_line_between_header_and_items(sample_order):
    _, wb = _wb(sample_order)
    ws = wb["납품서"]
    for c in range(1, 7):
        assert ws.cell(8, c).border.bottom.style == "double"
        assert ws.cell(9, c).border.top.style == "double"
    assert ws["A7"].border.top.style == "medium" and ws["A9"].border.left.style == "medium"


def test_zero_numbers_are_hidden_by_format(sample_order):
    _, wb = _wb(sample_order)
    fmt = wb["발주서"]["E11"].number_format
    assert fmt == "#,##0;-#,##0;;@"            # 0 은 빈 문자열 구간
    assert wb["납품서"]["F14"].number_format == fmt


def test_totals_have_cached_values_for_non_recalculating_viewers(sample_order):
    import io, zipfile
    data, _ = _wb(sample_order)
    xml = zipfile.ZipFile(io.BytesIO(data)).read("xl/worksheets/sheet2.xml").decode("utf-8")
    assert "<f>SUM(C9:C13)</f><v>1005</v>" in xml


def test_delivery_totals_and_column_widths(sample_order):
    _, wb = _wb(sample_order)
    ws = wb["납품서"]
    assert ws["D14"].value == "=SUM(D9:D13)" and ws["E14"].value == "=SUM(E9:E13)"
    assert [ws.column_dimensions[c].width for c in "ABCDEF"] == [5.8, 36, 17.1, 17.1, 17.1, 17.1]
