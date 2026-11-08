"""생성된 엑셀의 수식 결과가 화면(서버) 계산값과 같은지 확인한다.

openpyxl 은 수식을 계산하지 않으므로 processors/formula_eval 로 직접 평가한다.
납품서 공급액(IF/AND)은 평가기가 지원하지 않아 수식 문자열과 참조 행을 검사한다.
"""
from io import BytesIO

from openpyxl import load_workbook

from processors.formula_eval import get_val
from processors.order_form import xlsx_builder as xb
from processors.order_form.compute import item_totals, print_volumes
from processors.order_form.models import Order


class OrderVerifyError(Exception):
    pass


def _expect(ws, row, col, expected, label, problems):
    actual = get_val(ws, row, col)
    if expected == 0 and actual in (None, 0, 0.0):
        return
    if actual is None or abs(actual - expected) > 1e-9:
        problems.append(f"{ws.title}!{ws.cell(row=row, column=col).coordinate} {label}: 기대 {expected}, 실제 {actual}")


def verify_workbook(xlsx_bytes: bytes, order: Order) -> None:
    wb = load_workbook(BytesIO(xlsx_bytes))
    problems: list[str] = []

    if order.mode != "blank_delivery":
        ws = wb["발주서"]
        n = xb.item_row_count(len(order.items))
        first = xb.ORDER_FIRST_ITEM_ROW
        for idx, it in enumerate(order.items):
            r = first + idx
            _expect(ws, r, xb.COL_BODY_NO, idx + 1, "본문no", problems)
            _expect(ws, r, xb.COL_PAGES, it.pages, "페이지합계", problems)
            k, l, m, total = print_volumes(it.qty, it.mono, it.insert, it.color)
            _expect(ws, r, xb.COL_K, k, "1도 인쇄량", problems)
            _expect(ws, r, xb.COL_L, l, "2도 인쇄량", problems)
            _expect(ws, r, xb.COL_M, m, "4도 인쇄량", problems)
            _expect(ws, r, xb.COL_N, total, "인쇄량 합계", problems)
        t = first + n
        totals = item_totals(order.items)
        for col, key in ((xb.COL_QTY, "qty"), (xb.COL_MONO, "mono"), (xb.COL_INSERT, "insert"),
                         (xb.COL_COLOR, "color"), (xb.COL_PAGES, "pages"),
                         (xb.COL_K, "k"), (xb.COL_L, "l"), (xb.COL_M, "m"), (xb.COL_N, "n")):
            _expect(ws, t, col, totals[key], f"합계 {key}", problems)

    for note in order.deliveries:
        ws = wb[note.sheet_name]
        n = xb.item_row_count(len(note.lines))
        first = xb.DELIV_FIRST_ITEM_ROW
        last = first + n - 1
        for idx, line in enumerate(note.lines):
            r = first + idx
            qty = ws.cell(row=r, column=xb.DCOL_QTY).value
            if (qty or 0) != (line.qty or 0):
                problems.append(f"{ws.title}!C{r} 수량: 기대 {line.qty}, 실제 {qty}")
            pages = ws.cell(row=r, column=xb.DCOL_PAGES).value
            if (pages or 0) != line.item.pages:
                problems.append(f"{ws.title}!D{r} 페이지: 기대 {line.item.pages}, 실제 {pages}")
            amount = ws.cell(row=r, column=xb.DCOL_AMOUNT).value
            expected = f'=IF(AND(C{r}>0,E{r}<>""),C{r}*E{r},"")'
            if amount != expected:
                problems.append(f"{ws.title}!F{r} 공급액 수식: 기대 {expected}, 실제 {amount}")
        t = last + 1
        _expect(ws, t, xb.DCOL_QTY, sum((l.qty or 0) for l in note.lines), "수량 합계", problems)
        f_total = ws.cell(row=t, column=xb.DCOL_AMOUNT).value
        if f_total != f"=SUM(F{first}:F{last})":
            problems.append(f"{ws.title}!F{t} 공급액 합계 수식 불일치: {f_total}")

    if problems:
        raise OrderVerifyError("생성된 엑셀 수식 검증 실패: " + " / ".join(problems))
