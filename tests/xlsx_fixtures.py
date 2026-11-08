"""반영 기능 테스트용 가짜 청구서·마케팅팀 엑셀을 코드로 만든다 (실제 파일은 저장소에 없음)."""
import io
from datetime import datetime
from pathlib import Path

from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L

MARKETING_CAMPUSES = ["대치본원", "대치본원 S관", "분당캠퍼스", "평촌캠퍼스", "수원캠퍼스"]
BLOCK_HEADERS = ["일자", "제품명", "부수", "페이지", "단가", "금액"]
DATA_FIRST, DATA_LAST, TOTAL_ROW = 4, 47, 48


def _png_bytes() -> bytes:
    from PIL import Image as PILImage
    buf = io.BytesIO()
    PILImage.new("RGB", (12, 8), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


def make_invoice(path: Path, existing_sheets=("1008내신블랭크",)) -> Path:
    """견적서(이미지·병합·수식) + 기존 납품서 시트들."""
    wb = Workbook()
    ws = wb.active
    ws.title = "견적서"
    ws["B1"] = "견  적  서"
    ws["B1"].font = Font(size=20, bold=True)
    ws.merge_cells("B1:F1")
    ws["D4"] = "최선어학원 분당캠퍼스"
    ws["G13"] = f"='{existing_sheets[0]}'!C17" if existing_sheets else None
    ws["I28"] = "=SUM(K13:M22)"
    ws.column_dimensions["B"].width = 18
    ws.add_image(Image(io.BytesIO(_png_bytes())), "N6")
    for name in existing_sheets:
        s = wb.create_sheet(name)
        s["A1"] = "납   품   명   세   서"
        s["B9"] = "기존 제품"
        s["C9"] = 54
        s["E9"] = 1980
        s["F9"] = '=IF(C9>0,C9*E9,"")'
        s["C17"] = "=SUM(C9:C16)"
        s.merge_cells("A1:F1")
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def make_marketing(path: Path, rows: dict | None = None, campuses=None) -> Path:
    """소모품출고내역(학원별 6열 구역, 2행 병합 머리글, 3행 머리글, 48행 합계) + 재고 LIST.
    rows: {학원명: [(date, 제품명, 부수, 페이지, 단가, 금액), ...]}"""
    campuses = campuses or MARKETING_CAMPUSES
    rows = rows or {}
    wb = Workbook()
    ws = wb.active
    ws.title = "소모품출고내역"
    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    for i, name in enumerate(campuses):
        c0 = 1 + i * 6
        ws.merge_cells(start_row=2, start_column=c0, end_row=2, end_column=c0 + 5)
        ws.cell(2, c0, name).alignment = Alignment(horizontal="center")
        for k, h in enumerate(BLOCK_HEADERS):
            ws.cell(3, c0 + k, h)
        for r in range(DATA_FIRST, DATA_LAST + 1):
            ws.cell(r, c0).number_format = 'mm"월"\\ dd"일"'
            for k in range(6):
                ws.cell(r, c0 + k).border = box
            for k in (2, 3, 4, 5):
                ws.cell(r, c0 + k).number_format = '_-* #,##0_-;\\-* #,##0_-;_-* "-"_-;_-@_-'
        ws.cell(TOTAL_ROW, c0, "합계")
        for k in (2, 5):
            col = L(c0 + k)
            ws.cell(TOTAL_ROW, c0 + k, f"=SUM({col}{DATA_FIRST}:{col}{DATA_LAST})")
        for r, line in enumerate(rows.get(name, []), start=DATA_FIRST):
            for k, v in enumerate(line):
                ws.cell(r, c0 + k, v)
    ws.freeze_panes = "G4"
    ws2 = wb.create_sheet("재고 LIST")
    ws2["A1"] = "재고"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path


def make_desktop(root: Path, year=2026, month=11, invoice_campuses=("분당캠퍼스",),
                 marketing_rows=None, with_marketing=True) -> Path:
    """root 를 바탕화면으로 가정하고 청구서 폴더·파일과 마케팅팀 파일을 만든다."""
    folder = root / f"{year}년 {month:02d}월 매출청구서_소모품"
    for c in invoice_campuses:
        make_invoice(folder / f"{year}년 {month:02d}월 {c} 청구서_소모품.xlsx")
    if with_marketing:
        make_marketing(root / f"{year}년 {month:02d}월 소모품 제작내역_Marketing팀.xlsx", marketing_rows)
    return root


D = datetime(2026, 11, 27)
