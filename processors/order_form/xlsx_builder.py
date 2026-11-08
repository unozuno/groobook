"""발주서·납품서 엑셀 생성 (openpyxl).

레이아웃은 기준 파일 `발주서(sample)` / `납품서((sample)` 시트를 따르되,
- 표지 행에 사이즈·코팅·동판 칸을 추가하고
- 포장 아래(9행)에 생산처 전달사항을 붉은 글씨로 넣으며
- 품목 행 수는 10행 이상 가변, 합계 수식 범위도 함께 늘어난다.
외부 파일 참조는 전혀 쓰지 않는다.
"""
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

from processors.order_form.models import DeliveryNote, Order

# ───────── 스타일 상수 ─────────
GREEN = PatternFill("solid", fgColor="92D050")
_THIN = Side(style="thin")
BOX = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
BOTTOM = Border(bottom=_THIN)
NUM_FMT = '_-* #,##0_-;\\-* #,##0_-;_-* "-"_-;_-@_-'
DATE_FMT = '[$-F800]dddd\\,\\ mmmm\\ dd\\,\\ yyyy'
CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")
MEMO_ALIGN = Alignment(horizontal="left", vertical="center", wrap_text=True)

F12 = Font(size=12, bold=True)
F14_RED = Font(size=14, bold=True, color="FF0000")
F20 = Font(size=20, bold=True)
F24 = Font(size=24, bold=True)
F8 = Font(size=8, bold=True)

ROW_H = 30
MIN_ITEM_ROWS = 10

# 발주서 품목 표 열 (1-based)
ORDER_FIRST_ITEM_ROW = 11
COL_NO, COL_SCHOOL, COL_NAME, COL_BODY_NO, COL_QTY, COL_MONO, COL_INSERT, COL_COLOR, \
    COL_PAGES, COL_BUNDLE, COL_K, COL_L, COL_M, COL_N = range(1, 15)

# 납품서 품목 표 열
DELIV_FIRST_ITEM_ROW = 9
DCOL_NO, DCOL_NAME, DCOL_QTY, DCOL_PAGES, DCOL_PRICE, DCOL_AMOUNT = range(1, 7)


def _set(ws, row, col, value=None, font=F12, align=CENTER, fill=None, border=None, fmt=None):
    c = ws.cell(row=row, column=col)
    if value is not None:
        c.value = value
    c.font = font
    c.alignment = align
    if fill is not None:
        c.fill = fill
    if border is not None:
        c.border = border
    if fmt is not None:
        c.number_format = fmt
    return c


def _page_setup(ws):
    ws.page_setup.orientation = "portrait"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)


def _job_no_value(job_no: str):
    return int(job_no) if job_no.isdigit() else (job_no or None)


def item_row_count(n_items: int) -> int:
    return max(MIN_ITEM_ROWS, n_items)


# ───────── 발주서 ─────────

def write_order_sheet(ws, order: Order) -> None:
    widths = {"A": 10.8, "B": 15, "C": 37, "D": 12, "E": 12, "F": 12, "G": 12,
              "K": 9, "L": 9, "M": 9, "N": 9}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    # 1행 제목
    _set(ws, 1, 3, "그루북", font=F20, align=RIGHT)
    ws.merge_cells("D1:E1")
    _set(ws, 1, 4, order.type_name or None, font=F20)
    _set(ws, 1, 6, "제작 요청서", font=F20, align=LEFT)

    # 2~8행 기본 정보 + 사양
    for i, r in enumerate(range(2, 9), start=1):
        _set(ws, r, 1, i)
    _set(ws, 2, 2, "접수일자")
    _set(ws, 2, 3, order.received_date, align=LEFT, fmt=DATE_FMT)
    ws.merge_cells("F2:G2")
    _set(ws, 2, 6, "납기일자")
    ws.merge_cells("H2:J2")
    _set(ws, 2, 8, order.due_date, fmt=DATE_FMT)

    _set(ws, 3, 2, "납품학원")
    _set(ws, 3, 3, order.campus or None)
    ws.merge_cells("I3:J3")
    _set(ws, 3, 9, _job_no_value(order.job_no), font=F20)

    s = order.spec
    _set(ws, 4, 2, "제본")
    _set(ws, 4, 3, s["binding_method"] or None)
    _set(ws, 4, 4, s["binding_staple"] or None)

    _set(ws, 5, 2, "내지")
    _set(ws, 5, 3, s["inner_paper"] or None)
    _set(ws, 5, 4, s["inner_print"] or None)
    _set(ws, 5, 5, s["inner_size"] or None)

    _set(ws, 6, 2, "간지")
    _set(ws, 6, 3, s["insert_paper"] or None)
    _set(ws, 6, 4, s["insert_print"] or None)
    _set(ws, 6, 5, s["insert_size"] or None)

    _set(ws, 7, 2, "표지")
    _set(ws, 7, 3, s["cover_paper"] or None)
    _set(ws, 7, 4, s["cover_print"] or None)
    _set(ws, 7, 5, s["cover_size"] or None)
    _set(ws, 7, 6, s["cover_coating"] or None)
    _set(ws, 7, 7, s["cover_plate"] or None)

    _set(ws, 8, 2, "포장")
    _set(ws, 8, 3, s["packaging"] or None)

    # 9행 생산처 전달사항
    memo_lines = len(order.messages)
    if memo_lines:
        ws.merge_cells("B9:J9")
        _set(ws, 9, 2, "\n".join(order.messages), font=F14_RED, align=MEMO_ALIGN)

    # 10행 머리글
    headers = ["표지no", "학교", "교재명", "본문no", "발주수량", "1도", "청간지", "4도", "페이지합계", "덩이수"]
    for col, h in enumerate(headers, start=1):
        _set(ws, 10, col, h, fill=GREEN, border=BOX)
    for col, h in zip((COL_K, COL_L, COL_M, COL_N), ("1도", "2도", "4도", "합계")):
        _set(ws, 10, col, h, font=F8, fmt=NUM_FMT)

    # 품목 행
    n = item_row_count(len(order.items))
    first = ORDER_FIRST_ITEM_ROW
    last = first + n - 1
    for idx in range(n):
        r = first + idx
        it = order.items[idx] if idx < len(order.items) else None
        _set(ws, r, COL_NO, idx + 1, border=BOX)
        _set(ws, r, COL_SCHOOL, None, border=BOX)
        _set(ws, r, COL_NAME, it.name if it and it.name else None, align=LEFT, border=BOX)
        _set(ws, r, COL_BODY_NO, f"=A{r}", border=BOX)
        _set(ws, r, COL_QTY, it.qty if it else None, border=BOX, fmt=NUM_FMT)
        _set(ws, r, COL_MONO, it.mono if it else None, border=BOX, fmt=NUM_FMT)
        _set(ws, r, COL_INSERT, it.insert if it else None, border=BOX, fmt=NUM_FMT)
        _set(ws, r, COL_COLOR, it.color if it else None, border=BOX, fmt=NUM_FMT)
        _set(ws, r, COL_PAGES, f"=F{r}+G{r}+H{r}", border=BOX, fmt=NUM_FMT)
        _set(ws, r, COL_BUNDLE, None, border=BOX)
        _set(ws, r, COL_K, f"=$E{r}*F{r}", font=F8, fmt=NUM_FMT)
        _set(ws, r, COL_L, f"=$E{r}*G{r}", font=F8, fmt=NUM_FMT)
        _set(ws, r, COL_M, f"=$E{r}*H{r}", font=F8, fmt=NUM_FMT)
        _set(ws, r, COL_N, f"=SUM(K{r}:M{r})", font=F8, fmt=NUM_FMT)

    # 합계 행
    t = last + 1
    ws.merge_cells(start_row=t, start_column=1, end_row=t, end_column=2)
    _set(ws, t, 1, "합계", border=BOX)
    _set(ws, t, 2, None, border=BOX)
    _set(ws, t, COL_NAME, None, border=BOX)
    _set(ws, t, COL_BODY_NO, None, border=BOX)
    for col in range(COL_QTY, COL_BUNDLE + 1):
        letter = get_column_letter(col)
        _set(ws, t, col, f"=SUM({letter}{first}:{letter}{last})", border=BOX, fmt=NUM_FMT)
    for col in (COL_K, COL_L, COL_M):
        letter = get_column_letter(col)
        _set(ws, t, col, f"=SUM({letter}{first}:{letter}{last})", font=F8, fmt=NUM_FMT)
    _set(ws, t, COL_N, f"=SUM(K{t}:M{t})", font=F8, fmt=NUM_FMT)

    for r in range(1, t + 1):
        ws.row_dimensions[r].height = ROW_H
    if memo_lines > 1:
        ws.row_dimensions[9].height = max(ROW_H, 22 * memo_lines)
    _page_setup(ws)


# ───────── 납품서 ─────────

def write_delivery_sheet(ws, order: Order, note: DeliveryNote) -> None:
    for col, w in {"A": 6.2, "B": 32, "C": 18.7, "D": 11, "E": 11, "F": 13, "G": 9}.items():
        ws.column_dimensions[col].width = w

    ws.merge_cells("A1:F1")
    _set(ws, 1, 1, "납   품   명   세   서", font=F24)

    ws.merge_cells("A3:B3")
    _set(ws, 3, 1, "납품일", border=BOTTOM)
    _set(ws, 3, 2, None, border=BOTTOM)
    ws.merge_cells("C3:D3")
    _set(ws, 3, 3, order.due_date, border=BOTTOM, fmt=DATE_FMT)
    _set(ws, 3, 4, None, border=BOTTOM)
    _set(ws, 3, 6, _job_no_value(order.job_no), font=F20)

    ws.merge_cells("A5:B5")
    _set(ws, 5, 1, "수령자", border=BOX)
    _set(ws, 5, 2, None, border=BOX)
    _set(ws, 5, 3, note.campus, border=BOX)
    _set(ws, 5, 4, None, border=BOX)
    _set(ws, 5, 5, "공급자", border=BOX)
    _set(ws, 5, 6, "그루북", border=BOX)

    _set(ws, 6, 1, "아래와 같이 납품합니다.", align=LEFT)

    for rng, text in (("A7:A8", "no"), ("B7:B8", "제품명"), ("C7:C8", "수량"), ("D7:F7", "인쇄단가   (Vat 별도)")):
        ws.merge_cells(rng)
    for r in (7, 8):
        for c in range(1, 7):
            _set(ws, r, c, None, border=BOX)
    ws["A7"].value = "no"
    ws["B7"].value = "제품명"
    ws["C7"].value = "수량"
    ws["D7"].value = "인쇄단가   (Vat 별도)"
    ws["D8"].value = "페이지"
    ws["E8"].value = "단가"
    ws["F8"].value = "공급액"

    n = item_row_count(len(note.lines))
    first = DELIV_FIRST_ITEM_ROW
    last = first + n - 1
    for idx in range(n):
        r = first + idx
        line = note.lines[idx] if idx < len(note.lines) else None
        price = note.unit_prices[idx] if line and idx < len(note.unit_prices) else None
        _set(ws, r, DCOL_NO, idx + 1, border=BOX)
        _set(ws, r, DCOL_NAME, line.item.name if line and line.item.name else None, border=BOX)
        _set(ws, r, DCOL_QTY, line.qty if line else None, border=BOX, fmt=NUM_FMT)
        _set(ws, r, DCOL_PAGES, line.item.pages if line else None, border=BOX, fmt=NUM_FMT)
        _set(ws, r, DCOL_PRICE, price, border=BOX, fmt=NUM_FMT)
        _set(ws, r, DCOL_AMOUNT, f'=IF(AND(C{r}>0,E{r}<>""),C{r}*E{r},"")', border=BOX, fmt=NUM_FMT)

    t = last + 1
    _set(ws, t, DCOL_NO, "합계", border=BOX)
    _set(ws, t, DCOL_NAME, None, border=BOX)
    _set(ws, t, DCOL_QTY, f"=SUM(C{first}:C{last})", border=BOX, fmt=NUM_FMT)
    _set(ws, t, DCOL_PAGES, None, border=BOX)
    _set(ws, t, DCOL_PRICE, None, border=BOX)
    _set(ws, t, DCOL_AMOUNT, f"=SUM(F{first}:F{last})", border=BOX, fmt=NUM_FMT)

    addr_row = t + 2
    _set(ws, addr_row, 1, f"인수처 주소 : {note.address or ''}".rstrip(), align=LEFT)
    _set(ws, addr_row + 1, 1, f"인수 담당자 : {note.contact or ''}".rstrip(), align=LEFT)
    _set(ws, addr_row + 1, 5, "서명", border=BOTTOM)
    _set(ws, addr_row + 1, 6, "      (인)", align=RIGHT, border=BOTTOM)

    for r in range(1, addr_row + 2):
        ws.row_dimensions[r].height = ROW_H
    ws.row_dimensions[2].height = 33
    _page_setup(ws)


# ───────── 워크북 ─────────

def build_workbook(order: Order) -> bytes:
    wb = Workbook()
    ws = wb.active
    if order.mode == "blank_delivery":
        note = order.deliveries[0]
        ws.title = note.sheet_name
        write_delivery_sheet(ws, order, note)
    else:
        ws.title = "발주서"
        write_order_sheet(ws, order)
        for note in order.deliveries:
            write_delivery_sheet(wb.create_sheet(note.sheet_name), order, note)
    wb.calculation.fullCalcOnLoad = True
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
