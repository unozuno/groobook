from datetime import datetime

import pytest
from openpyxl import load_workbook

from processors.order_form import reflect as rf
from processors.order_form import workbook_io as wio
from xlsx_fixtures import DATA_FIRST, TOTAL_ROW, make_desktop, make_marketing

DUE = "2026-11-27"
ITEMS = [
    {"name": "교재 상품권 난수", "qty": "1000", "color": "2", "unit_price": "250"},
    {"name": "레벨테스트권 난수", "qty": "500", "color": "2", "unit_price": ""},
]


@pytest.fixture
def desk(tmp_path):
    return make_desktop(tmp_path / "desk", invoice_campuses=("분당캠퍼스", "평촌캠퍼스"))


def order_for(make_order, **kw):
    base = dict(campus="분당캠퍼스", due_date=DUE, items=ITEMS)
    base.update(kw)
    return make_order(**base)


def run(order, desk, targets=("invoice", "marketing"), dry_run=False):
    return rf.reflect(order, {t: True for t in targets}, str(desk), dry_run=dry_run).items


def invoice_path(desk, campus="분당캠퍼스"):
    return desk / "2026년 11월 매출청구서_소모품" / f"2026년 11월 {campus} 청구서_소모품.xlsx"


def marketing_path(desk):
    return desk / "2026년 11월 소모품 제작내역_Marketing팀.xlsx"


# ───────── 청구서 ─────────

def test_invoice_dry_run_changes_nothing(make_order, desk):
    before = {p: p.read_bytes() for p in (invoice_path(desk), marketing_path(desk))}
    items = run(order_for(make_order), desk, dry_run=True)
    assert [(i.target, i.status) for i in items] == [("invoice", "ok"), ("marketing", "ok")]
    assert items[0].detail == "1127교재상품권난수"
    assert {p: p.read_bytes() for p in before} == before
    assert not wio.backups_dir().exists()


def test_invoice_sheet_appended_at_end(make_order, desk):
    items = run(order_for(make_order), desk, targets=("invoice",))
    assert [(i.status, i.detail) for i in items] == [("done", "1127교재상품권난수")]
    assert items[0].backup and (wio.backups_dir() / items[0].backup.split("/")[-1]).exists()
    wb = load_workbook(invoice_path(desk))
    assert wb.sheetnames == ["견적서", "1008내신블랭크", "1127교재상품권난수"]
    ws = wb["1127교재상품권난수"]
    assert ws["A1"].value == "납   품   명   세   서"
    assert ws["C3"].value == datetime(2026, 11, 27)
    assert (ws["C5"].value, ws["B9"].value, ws["C9"].value, ws["E9"].value) == ("분당캠퍼스", "교재 상품권 난수", 1000, 250)
    assert ws["E10"].value == 660                          # 입력 없는 품목은 단가표 자동 단가
    assert "분당" in ws["A21"].value                      # 주소록 값이 들어감
    # 기존 시트·이미지 불변
    assert len(wb["견적서"]._images) == 1
    assert wb["견적서"]["G13"].value == "='1008내신블랭크'!C17"
    assert wb["1008내신블랭크"]["B9"].value == "기존 제품"
    assert wb.calculation.fullCalcOnLoad is True


def test_invoice_existing_sheet_is_skipped(make_order, desk):
    run(order_for(make_order), desk, targets=("invoice",))
    after_first = invoice_path(desk).read_bytes()
    items = run(order_for(make_order), desk, targets=("invoice",))
    assert [(i.status) for i in items] == ["skip"] and "이미" in items[0].message
    assert invoice_path(desk).read_bytes() == after_first


def test_invoice_business_card_sheet_name(make_order, desk):
    order = order_for(make_order, type_id="business_card", items=[{"name": "명함_이성희", "qty": "200", "color": "2"}])
    items = run(order, desk, targets=("invoice",), dry_run=True)
    assert items[0].detail == "1127명함"


def test_invoice_sheet_name_truncated_and_sanitized(make_order, desk):
    long_name = "아주 긴 제품 이름 " * 6 + "끝"
    order = order_for(make_order, items=[{"name": f"[{long_name}]", "qty": "1", "color": "1"}])
    name = run(order, desk, targets=("invoice",), dry_run=True)[0].detail
    assert len(name) <= 31 and name.startswith("1127") and " " not in name and "[" not in name


def test_invoice_file_missing_is_skipped(make_order, desk):
    order = order_for(make_order, campus="수원캠퍼스")
    items = run(order, desk, targets=("invoice",))
    assert items[0].status == "skip" and "찾지 못" in items[0].message
    assert items[0].file.endswith("2026년 11월 수원캠퍼스 청구서_소모품.xlsx")
    assert not invoice_path(desk, "수원캠퍼스").exists()          # 새로 만들지 않음


def test_invoice_locked_file_is_error(make_order, desk):
    (invoice_path(desk).parent / "~$2026년 11월 분당캠퍼스 청구서_소모품.xlsx").write_bytes(b"lock")
    items = run(order_for(make_order), desk, targets=("invoice",), dry_run=True)
    assert items[0].status == "error" and "열려" in items[0].message


def test_multi_order_each_campus_own_file(make_order, desk):
    order = make_order(order_type="multi", multi_name="분당평촌수원", due_date=DUE, items=[
        {"name": "교재 상품권 난수", "color": "2", "unit_price": "250"},
        {"name": "대봉투", "color": "1"},
    ], distribution=[
        {"campus": "분당캠퍼스", "qtys": ["300", "0"]},
        {"campus": "평촌캠퍼스", "qtys": ["100", "50"]},
        {"campus": "수원캠퍼스", "qtys": ["10", "10"]},
    ])
    items = run(order, desk, targets=("invoice",))
    assert [(i.campus, i.status) for i in items] == [("분당캠퍼스", "done"), ("평촌캠퍼스", "done"), ("수원캠퍼스", "skip")]
    b = load_workbook(invoice_path(desk, "분당캠퍼스"))["1127교재상품권난수"]
    p = load_workbook(invoice_path(desk, "평촌캠퍼스"))["1127교재상품권난수"]
    assert [(b["B9"].value, b["C9"].value), (b["B10"].value, b["C10"].value)] == [("교재 상품권 난수", 300), (None, None)]
    assert [(p["B9"].value, p["C9"].value), (p["B10"].value, p["C10"].value)] == [("교재 상품권 난수", 100), ("대봉투", 50)]


def test_blank_delivery_mode_reflects(make_order, desk):
    order = make_order(mode="blank_delivery", campus="분당캠퍼스", due_date=DUE,
                       items=[{"name": "대봉투", "qty": "100", "pages": "0", "unit_price": "200"}])
    items = run(order, desk)
    assert [i.status for i in items] == ["done", "done"]


# ───────── 청구서: 견적서 줄 ─────────

def est(desk, campus="분당캠퍼스"):
    return load_workbook(invoice_path(desk, campus))["견적서"]


def test_estimate_gets_one_line_for_new_sheet(make_order, desk):
    items = run(order_for(make_order), desk, targets=("invoice",))
    assert items[0].status == "done" and "견적서 14행에 한 줄을 추가" in items[0].message
    ws = est(desk)
    assert [ws[f"{c}14"].value for c in "BDFGIKN"] == [
        "소모품", "교재 상품권 난수", None, "='1127교재상품권난수'!C19", None, "='1127교재상품권난수'!F19", "11/27 납품"]
    assert ws["B13"].value == "소모품" and ws["D13"].value == "기존 제품 1"     # 기존 줄 그대로
    assert ws["I28"].value == "=SUM(K13:M22)" and ws["J10"].value == "=SUM(G13:H22)"   # 삽입 없음 → 수식 불변


def test_estimate_formula_targets_delivery_total_row(make_order, desk):
    run(order_for(make_order), desk, targets=("invoice",))
    wb = load_workbook(invoice_path(desk))
    assert wb["1127교재상품권난수"]["C19"].value == "=SUM(C9:C18)" and wb["1127교재상품권난수"]["F19"].value == "=SUM(F9:F18)"
    many = [{"name": f"제품{i}", "qty": "1", "unit_price": "1"} for i in range(12)]
    run(order_for(make_order, items=many, due_date="2026-11-28"), desk, targets=("invoice",))
    ws = est(desk)
    assert ws["G15"].value == "='1128제품0'!C21" and ws["K15"].value == "='1128제품0'!F21"     # 12줄이면 합계 행 21


def test_second_sheet_uses_next_free_line_and_date_note_has_no_zero_padding(make_order, desk):
    run(order_for(make_order), desk, targets=("invoice",))
    run(order_for(make_order, due_date="2026-12-03", items=[{"name": "다른 제품", "qty": "5", "unit_price": "10"}]),
        make_desktop(desk, month=12, invoice_campuses=("분당캠퍼스",), with_marketing=False), targets=("invoice",))
    ws = load_workbook(invoice_path(desk).parent.parent / "2026년 12월 매출청구서_소모품" / "2026년 12월 분당캠퍼스 청구서_소모품.xlsx")["견적서"]
    assert ws["N14"].value == "12/3 납품" and ws["D14"].value == "다른 제품"


def test_estimate_line_inserted_when_full(make_order, tmp_path):
    from xlsx_fixtures import build_estimate
    desk = make_desktop(tmp_path / "d")
    wb = load_workbook(invoice_path(desk))
    ws = wb["견적서"]
    for r in range(14, 23):
        ws[f"B{r}"], ws[f"D{r}"] = "소모품", f"채움{r}"
    wb.save(invoice_path(desk))

    items = run(order_for(make_order), desk, targets=("invoice",))
    assert items[0].status == "done" and "줄을 삽입해 한 줄을 추가" in items[0].message, items[0].message
    ws = est(desk)
    assert ws["D23"].value == "교재 상품권 난수" and ws["G23"].value == "='1127교재상품권난수'!C19"
    assert ws["D25"].value == "표  지" and ws["D29"].value == "공 급 가"                    # 아래가 한 줄씩 내려감
    assert ws["I29"].value == "=SUM(K13:M23)" and ws["J10"].value == "=SUM(G13:H23)"
    assert ws["K31"].value == "=SUM(K29:M30)" and ws["M10"].value == "=K31"
    merges = {str(r) for r in ws.merged_cells.ranges}
    assert {"B24:O24", "K23:M23", "B32:O36"} <= merges
    assert len(ws._images) == 1 and ws.print_area.endswith("$O$36")
    assert load_workbook(invoice_path(desk)).sheetnames[-1] == "1127교재상품권난수"


def test_estimate_dry_run_reports_free_or_insert(make_order, desk):
    items = run(order_for(make_order), desk, targets=("invoice",), dry_run=True)
    assert items[0].message == "맨 끝에 '1127교재상품권난수' 시트를 추가하고, 견적서 14행에 한 줄을 추가합니다."


def test_skipped_duplicate_sheet_leaves_estimate_untouched(make_order, desk):
    run(order_for(make_order), desk, targets=("invoice",))
    before = est(desk)["D15"].value
    assert run(order_for(make_order), desk, targets=("invoice",))[0].status == "skip"
    assert est(desk)["D15"].value == before is None


def test_missing_estimate_structure_is_error_and_file_untouched(make_order, desk):
    wb = load_workbook(invoice_path(desk))
    wb["견적서"]["B12"] = "다른 제목"
    wb.save(invoice_path(desk))
    raw = invoice_path(desk).read_bytes()
    items = run(order_for(make_order), desk, targets=("invoice",))
    assert items[0].status == "error" and "견적서 구조" in items[0].message
    assert invoice_path(desk).read_bytes() == raw


def test_estimate_shift_mismatch_is_rejected(make_order, desk, monkeypatch):
    """삽입 결과가 기대와 다르면(예: 수식 이동 버그) 저장하지 않고 원본을 그대로 둔다."""
    from processors.order_form import estimate_sheet as es
    wb = load_workbook(invoice_path(desk))
    for r in range(14, 23):
        wb["견적서"][f"B{r}"], wb["견적서"][f"D{r}"] = "소모품", f"x{r}"
    wb.save(invoice_path(desk))
    raw = invoice_path(desk).read_bytes()
    orig_insert = es.insert_item_row

    def broken(ws, layout):
        row = orig_insert(ws, layout)
        ws["K29"].value = "=I28"                      # 한 줄 어긋난 수식 (올바른 값은 =I29)
        return row
    monkeypatch.setattr(es, "insert_item_row", broken)
    items = run(order_for(make_order), desk, targets=("invoice",))
    assert items[0].status == "error" and "검증에 실패" in items[0].message
    assert invoice_path(desk).read_bytes() == raw


# ───────── 마케팅팀 ─────────

def test_marketing_rows_appended(make_order, desk):
    items = run(order_for(make_order), desk, targets=("marketing",))
    assert [(i.status, i.detail) for i in items] == [("done", "4~5행")]
    ws = load_workbook(marketing_path(desk))["소모품출고내역"]
    c0 = 1 + 2 * 6                                  # 분당캠퍼스 = 세 번째 구역
    row4 = [ws.cell(4, c0 + k).value for k in range(6)]
    assert row4[:5] == [datetime(2026, 11, 27), "교재 상품권 난수", 1000, 2, 250]
    assert row4[5] == "=O4*Q4"
    row5 = [ws.cell(5, c0 + k).value for k in range(6)]
    assert row5 == [datetime(2026, 11, 27), "레벨테스트권 난수", 500, 2, 660, "=O5*Q5"]   # 입력 없으면 자동 단가
    assert ws.cell(4, c0).number_format == 'mm"월"\\ dd"일"'
    assert ws.cell(TOTAL_ROW, c0 + 2).value == f"=SUM({'O'}{DATA_FIRST}:{'O'}47)"
    assert ws.cell(4, 1).value is None              # 다른 학원 구역은 그대로


def test_marketing_continues_after_existing_rows(make_order, tmp_path):
    existing = {"분당캠퍼스": [(datetime(2026, 11, 3), "예전 교재", 10, 20, 100, 1000),
                              (datetime(2026, 11, 4), "예전 교재2", 5, 20, 100, 500)]}
    desk = make_desktop(tmp_path / "d", marketing_rows=existing)
    items = run(order_for(make_order), desk, targets=("marketing",))
    assert items[0].detail == "6~7행"
    ws = load_workbook(marketing_path(desk))["소모품출고내역"]
    assert ws.cell(5, 14).value == "예전 교재2" and ws.cell(6, 14).value == "교재 상품권 난수"


def test_marketing_duplicate_is_skipped(make_order, desk):
    run(order_for(make_order), desk, targets=("marketing",))
    snapshot = marketing_path(desk).read_bytes()
    items = run(order_for(make_order), desk, targets=("marketing",))
    assert items[0].status == "skip" and "이미 입력" in items[0].message
    assert marketing_path(desk).read_bytes() == snapshot


def test_marketing_unknown_campus_skipped(make_order, desk):
    items = run(order_for(make_order, campus="최선 세종"), desk, targets=("marketing",))
    assert items[0].status == "skip" and "구역이 없어" in items[0].message


def test_marketing_not_enough_rows(make_order, tmp_path):
    full = {"분당캠퍼스": [(datetime(2026, 10, 1), f"p{i}", 1, 1, 1, 1) for i in range(44)]}
    desk = make_desktop(tmp_path / "d", marketing_rows=full)
    items = run(order_for(make_order), desk, targets=("marketing",))
    assert items[0].status == "error" and "빈 행이 부족" in items[0].message


def test_marketing_multi_campuses_single_save(make_order, desk):
    order = make_order(order_type="multi", multi_name="x", due_date=DUE, items=[
        {"name": "교재 상품권 난수", "color": "2", "unit_price": "250"},
    ], distribution=[
        {"campus": "분당캠퍼스", "qtys": ["300"]}, {"campus": "평촌캠퍼스", "qtys": ["100"]}])
    items = run(order, desk, targets=("marketing",))
    assert [(i.campus, i.status) for i in items] == [("분당캠퍼스", "done"), ("평촌캠퍼스", "done")]
    assert len(list(wio.backups_dir().iterdir())) == 1         # 파일 하나당 백업 한 번
    ws = load_workbook(marketing_path(desk))["소모품출고내역"]
    assert ws.cell(4, 15).value == 300 and ws.cell(4, 1 + 3 * 6 + 2).value == 100


def test_marketing_file_missing_and_wrong_sheet(make_order, tmp_path):
    desk = make_desktop(tmp_path / "d", with_marketing=False)
    items = run(order_for(make_order), desk, targets=("marketing",))
    assert items[0].status == "skip" and items[0].file.endswith("2026년 11월 소모품 제작내역_Marketing팀.xlsx")


# ───────── 공통 ─────────

def test_missing_due_date_and_desktop(make_order, desk, tmp_path):
    items = run(order_for(make_order, due_date=""), desk)
    assert [i.status for i in items] == ["error", "error"] and "납품일" in items[0].message
    items = run(order_for(make_order), tmp_path / "없는바탕화면")
    assert [i.status for i in items] == ["error", "error"] and "바탕화면" in items[0].message


def test_no_targets_does_nothing(make_order, desk):
    assert run(order_for(make_order), desk, targets=()) == []


# ───────── 실제 참조 파일 (sample/ 은 git 에 없으므로 있을 때만 실행) ─────────

SAMPLE_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "sample"
REAL_INVOICE = SAMPLE_DIR / "참조1번_2026년 10월 분당캠퍼스 청구서_소모품.xlsx"
REAL_MARKETING = SAMPLE_DIR / "참조2번_2026년 09월 소모품 제작내역_Marketing팀.xlsx"


@pytest.mark.skipif(not (REAL_INVOICE.exists() and REAL_MARKETING.exists()), reason="sample 참조 파일 없음")
def test_real_reference_files_roundtrip(make_order, tmp_path):
    import shutil
    desk = tmp_path / "desk"
    (desk / "2026년 11월 매출청구서_소모품").mkdir(parents=True)
    shutil.copy(REAL_INVOICE, invoice_path(desk))
    shutil.copy(REAL_MARKETING, marketing_path(desk))
    before_inv = load_workbook(invoice_path(desk))
    n_sheets, n_links = len(before_inv.sheetnames), len(before_inv._external_links)

    items = run(order_for(make_order), desk)
    assert [i.status for i in items] == ["done", "done"], [i.message for i in items]

    inv = load_workbook(invoice_path(desk))
    assert len(inv.sheetnames) == n_sheets + 1 and inv.sheetnames[-1] == "1127교재상품권난수"
    assert len(inv["견적서"]._images) == 1 and len(inv._external_links) == n_links
    assert inv["견적서"]["D21"].value == "교재 상품권 난수" and inv["견적서"]["N21"].value == "11/27 납품"   # 참조1 의 첫 빈 줄
    assert inv["견적서"]["G21"].value == "='1127교재상품권난수'!C19" and inv["견적서"]["I28"].value == "=SUM(K13:M22)"
    mk = load_workbook(marketing_path(desk))["소모품출고내역"]
    assert mk["AF7"].value == "교재 상품권 난수" and mk["AG7"].value == 1000       # 분당캠퍼스 구역(AE~AJ)
    assert mk["AG48"].value == "=SUM(AG4:AG47)"
    assert [i.status for i in run(order_for(make_order), desk)] == ["skip", "skip"]
