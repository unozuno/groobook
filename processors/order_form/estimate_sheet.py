"""청구서 엑셀의 1번 시트 `견적서` 에 납품서 한 줄을 추가한다.

견적서 틀(참조1):  12행 머리글(품목·적요·페이지·수량·단가·금액·비고) → 품목 줄들 → `B:O` 전체 병합 구분줄 → 제작사양·합계…
- 빈 품목 줄(품목·적요·수량·금액이 모두 빈 줄)이 있으면 그 줄을 쓰고, 없으면 구분줄 자리에 줄을 하나 삽입한다.
- openpyxl 의 insert_rows 는 병합·수식 참조·행 높이·인쇄영역을 옮기지 않으므로 이 시트 구조에 맞춰 직접 옮긴다.
- 시트 안 수식만 다룬다(다른 시트·외부 통합문서 참조는 그대로). 이 시트를 가리키는 다른 시트의 수식은 다루지 않는다.
"""
import re
from copy import copy
from dataclasses import dataclass
from typing import Callable, Optional

from openpyxl.formula import Tokenizer
from openpyxl.formula.tokenizer import Token
from openpyxl.utils import get_column_letter as L
from openpyxl.utils.cell import coordinate_from_string

ESTIMATE_SHEET = "견적서"
ITEM_LABEL = "소모품"
HEADER_SCAN_ROWS = 60
REQUIRED_HEADERS = ("품목", "적요", "수량", "금액", "비고")


class EstimateError(Exception):
    """견적서 틀을 인식하지 못했거나 안전하게 수정할 수 없을 때."""


@dataclass
class EstimateLayout:
    header_row: int
    first: int                  # 첫 품목 줄
    last: int                   # 마지막 품목 줄 (구분줄 바로 위)
    cols: dict[str, int]        # 머리글 이름 → 열 번호 (병합이면 왼쪽 위 칸)
    max_col: int

    @property
    def separator(self) -> int:
        return self.last + 1


def _text(v) -> str:
    return re.sub(r"\s+", "", str(v)) if v is not None else ""


def find_layout(ws) -> EstimateLayout:
    header_row, cols = None, {}
    for r in range(1, min(ws.max_row, HEADER_SCAN_ROWS) + 1):
        found = {_text(c.value): c.column for c in ws[r] if c.value is not None and _text(c.value)}
        if all(h in found for h in REQUIRED_HEADERS):
            header_row, cols = r, found
            break
    if header_row is None:
        raise EstimateError("견적서에서 품목·적요·수량·금액·비고 머리글을 찾지 못했습니다.")

    separator = None
    for rng in sorted(ws.merged_cells.ranges, key=lambda x: x.min_row):
        if rng.min_row > header_row and rng.min_row == rng.max_row and rng.min_col == 2 \
                and rng.max_col - rng.min_col >= 5:
            separator = rng.min_row
            break
    if separator is None or separator - 1 <= header_row:
        raise EstimateError("견적서의 품목 줄 영역(머리글 아래 ~ 전체 병합 구분줄)을 찾지 못했습니다.")
    return EstimateLayout(header_row, header_row + 1, separator - 1, cols, ws.max_column)


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def find_free_row(ws, layout: EstimateLayout) -> Optional[int]:
    """품목·적요·수량·금액이 모두 빈 첫 품목 줄. 없으면 None."""
    keys = [layout.cols[k] for k in ("품목", "적요", "수량", "금액")]
    for r in range(layout.first, layout.last + 1):
        if all(_blank(ws.cell(r, c).value) for c in keys):
            return r
    return None


# ───────── 수식 참조 이동 ─────────

_REF = re.compile(r"^(\$?)([A-Za-z]{1,3})(\$?)(\d+)$")


def _shift_part(part: str, at_row: int, count: int, is_end: bool, expand_end: bool) -> str:
    m = _REF.match(part)
    if not m:
        return part
    row = int(m.group(4))
    if row >= at_row or (is_end and expand_end and row == at_row - 1):
        row += count
    return f"{m.group(1)}{m.group(2)}{m.group(3)}{row}"


def shift_formula(formula: str, at_row: int, count: int = 1) -> str:
    """같은 시트 참조에서 at_row 이상의 행을 count 만큼 밀고, 끝이 at_row-1 인 범위는 끝 행도 늘린다
    (영역 안에 줄을 끼운 것과 같은 결과). 다른 시트·외부 통합문서 참조는 건드리지 않는다."""
    if not isinstance(formula, str) or not formula.startswith("="):
        return formula
    tok = Tokenizer(formula)
    out = []
    for t in tok.items:
        v = t.value
        if t.type == Token.OPERAND and t.subtype == Token.RANGE and "!" not in v and "[" not in v:
            parts = v.split(":")
            if len(parts) == 1:
                v = _shift_part(parts[0], at_row, count, False, False)
            elif len(parts) == 2:
                start_row = _REF.match(parts[0])
                expand = bool(start_row) and int(start_row.group(4)) < at_row
                v = _shift_part(parts[0], at_row, count, False, False) + ":" + \
                    _shift_part(parts[1], at_row, count, True, expand)
        out.append(v)
    return "=" + "".join(out)


# ───────── 줄 삽입 ─────────

def _set_print_area_end(ws, at_row: int, count: int) -> None:
    area = ws.print_area
    if not area:
        return
    first = str(area).split(",")[0].split("!")[-1].replace("$", "")
    m = re.fullmatch(r"([A-Z]+)(\d+):([A-Z]+)(\d+)", first)
    if m and int(m.group(4)) >= at_row:
        ws.print_area = f"{m.group(1)}{m.group(2)}:{m.group(3)}{int(m.group(4)) + count}"


def insert_item_row(ws, layout: EstimateLayout) -> int:
    """구분줄 자리(layout.separator)에 품목 줄 1개를 삽입하고 그 행 번호를 돌려준다.
    아래쪽 셀·병합·행 높이·인쇄영역·시트 안 수식이 한 줄씩 밀린다."""
    at = layout.separator
    merges = [(r.min_row, r.min_col, r.max_row, r.max_col) for r in ws.merged_cells.ranges]
    if any(r0 < at <= r1 for r0, _, r1, _ in merges):
        raise EstimateError("품목 영역을 가로지르는 병합 셀이 있어 줄을 삽입할 수 없습니다.")

    max_row, max_col = ws.max_row, ws.max_column
    heights = {r: ws.row_dimensions[r].height for r in range(at - 1, max_row + 1) if r in ws.row_dimensions}

    for r0, c0, r1, c1 in merges:
        if r0 >= at:
            ws.unmerge_cells(start_row=r0, start_column=c0, end_row=r1, end_column=c1)
    ws.move_range(f"A{at}:{L(max_col)}{max_row}", rows=1, cols=0, translate=False)
    for r0, c0, r1, c1 in merges:
        if r0 >= at:
            ws.merge_cells(start_row=r0 + 1, start_column=c0, end_row=r1 + 1, end_column=c1)

    for r in range(max_row + 1, at, -1):
        ws.row_dimensions[r].height = heights.get(r - 1)
    ws.row_dimensions[at].height = heights.get(at - 1)

    # 새 줄 = 바로 위 품목 줄의 서식·병합 복사
    src = at - 1
    for c in range(1, max_col + 1):
        ws.cell(at, c)._style = copy(ws.cell(src, c)._style)
    for r0, c0, r1, c1 in merges:
        if r0 == r1 == src:
            ws.merge_cells(start_row=at, start_column=c0, end_row=at, end_column=c1)

    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                cell.value = shift_formula(cell.value, at, 1)
    _set_print_area_end(ws, at, 1)
    return at


# ───────── 한 줄 쓰기 ─────────

def quote_sheet(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


def write_item_row(ws, layout: EstimateLayout, row: int, summary: str, sheet: str,
                   total_row: int, month: int, day: int) -> None:
    c = layout.cols
    ws.cell(row, c["품목"]).value = ITEM_LABEL
    ws.cell(row, c["적요"]).value = summary
    ws.cell(row, c["수량"]).value = f"={quote_sheet(sheet)}!C{total_row}"
    ws.cell(row, c["금액"]).value = f"={quote_sheet(sheet)}!F{total_row}"
    # 견적서 틀의 비고 칸은 표시 서식이 `@ "납품"` 이라 값에는 '월/일'만 넣는다 (서식이 없는 틀이면 문구까지 넣는다)
    note = ws.cell(row, c["비고"])
    note.value = f"{month}/{day}" if "납품" in re.sub(r'["\\ ]', "", note.number_format or "") else f"{month}/{day} 납품"


# ───────── 저장 검증용: 줄 삽입 후 기대 스냅샷 ─────────

def expected_after_insert(at_row: int, new_row_merges: list[str]) -> Callable[[dict], dict]:
    """workbook_io.snapshot 의 시트 항목을 '구분줄 위치에 줄을 삽입한 뒤의 모습'으로 바꾸는 함수."""
    def _shift(snap: dict) -> dict:
        cells = {}
        for coord, sig in snap["cells"].items():
            col, row = coordinate_from_string(coord)
            new_row = row + 1 if row >= at_row else row
            if isinstance(sig[0], str) and sig[0].startswith("="):
                sig = (shift_formula(sig[0], at_row, 1),) + tuple(sig[1:])
            cells[f"{col}{new_row}"] = sig
        merged = []
        for rng in snap["merged"]:
            a, _, b = rng.partition(":")
            ca, ra = coordinate_from_string(a)
            cb, rb = coordinate_from_string(b or a)
            ra2, rb2 = (ra + 1 if ra >= at_row else ra), (rb + 1 if rb >= at_row else rb)
            merged.append(f"{ca}{ra2}:{cb}{rb2}" if b else f"{ca}{ra2}")
        merged = sorted(set(merged) | set(new_row_merges))
        return {**snap, "cells": cells, "merged": merged}
    return _shift


def row_merges(ws, row: int) -> list[str]:
    return [str(r) for r in ws.merged_cells.ranges if r.min_row == r.max_row == row]


def row_coords(layout: EstimateLayout, row: int) -> set[str]:
    return {f"{L(c)}{row}" for c in range(1, layout.max_col + 1)}

