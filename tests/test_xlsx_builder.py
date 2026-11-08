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
    assert all(c.fill.fill_type is None for row in ws.iter_rows(min_row=1, max_row=9) for c in row)
    assert all(c.fill.fill_type is None for row in ws.iter_rows(min_row=11, max_row=21, min_col=1, max_col=14) for c in row)
    assert ws["C2"].value == datetime(2026, 11, 8) and ws["H2"].value == datetime(2026, 11, 10)
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
    # 10행 패딩 + 합계 21행
    assert ws["A20"].value == 10 and ws["E20"].value is None
    assert ws["A21"].value == "합계" and ws["E21"].value == "=SUM(E11:E20)" and ws["N21"].value == "=SUM(K21:M21)"
    assert ws["N22"].value is None
    assert wb.calculation.fullCalcOnLoad is True
    assert not wb._external_links
    verify_workbook(data, sample_order)


def test_delivery_sheet_layout(sample_order):
    data, wb = _wb(sample_order)
    ws = wb["납품서"]
    assert ws["A1"].value == "납   품   명   세   서"
    assert ws["C3"].value == datetime(2026, 11, 10) and ws["F3"].value == 2105
    assert ws["C5"].value == "평촌캠퍼스" and ws["F5"].value == "그루북"
    assert (ws["D8"].value, ws["E8"].value, ws["F8"].value) == ("페이지", "단가", "공급액")
    assert (ws["B9"].value, ws["C9"].value, ws["D9"].value, ws["E9"].value) == ("중2 영어 내신", 700, 2, 660)
    assert ws["E11"].value == 1200
    assert ws["F9"].value == '=IF(AND(C9>0,E9<>""),C9*E9,"")'
    assert ws["A19"].value == "합계" and ws["C19"].value == "=SUM(C9:C18)" and ws["F19"].value == "=SUM(F9:F18)"
    assert ws["A21"].value.startswith("인수처 주소 : 경기도 안양시")
    assert ws["A22"].value == "인수 담당자 : 김경민 과장님 (010-5125-7196)"
    assert (ws["E22"].value, ws["F22"].value) == ("서명", "      (인)")


def test_many_items_grow_table(make_order):
    items = [{"name": f"품목{i}", "qty": str(10 * (i + 1)), "mono": "1", "color": "2"} for i in range(13)]
    order = make_order(items=items)
    data, wb = _wb(order)
    ws = wb["발주서"]
    assert ws["A23"].value == 13 and ws["C23"].value == "품목12"
    assert ws["A24"].value == "합계" and ws["E24"].value == "=SUM(E11:E23)" and ws["K24"].value == "=SUM(K11:K23)"
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
    assert b["C3"].value == datetime(2026, 11, 10) and b["F3"].value == 2105
    assert b["A21"].value.startswith("인수처 주소 : 경기도 성남시")
    verify_workbook(data, sample_multi_order)


def test_address_missing_leaves_prefix_only(make_order):
    order = make_order(campus="새학원")
    _, wb = _wb(order)
    ws = wb["납품서"]
    assert ws["A21"].value == "인수처 주소 :" and ws["A22"].value == "인수 담당자 :"


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
