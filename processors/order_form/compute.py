"""발주서 숫자 계산 (순수 함수). 화면 JS 와 엑셀 수식이 같은 결과를 내는지 검증하는 기준."""
from typing import Optional

Num = Optional[int]


def _z(v: Num) -> int:
    return 0 if v is None else int(v)


def page_total(mono: Num, insert: Num, color: Num) -> int:
    """페이지합계 = 1도 + 청간지 + 4도 (빈칸은 0)."""
    return _z(mono) + _z(insert) + _z(color)


def print_volumes(qty: Num, mono: Num, insert: Num, color: Num) -> tuple[int, int, int, int]:
    """(1도 인쇄량, 2도 인쇄량, 4도 인쇄량, 합계) = 발주수량 × 각 페이지 수."""
    q = _z(qty)
    k = q * _z(mono)
    l = q * _z(insert)
    m = q * _z(color)
    return k, l, m, k + l + m


def distribution_totals(matrix: list[list[Num]], n_items: int) -> list[int]:
    """학원별 분배표(행=학원, 열=품목) → 품목별 발주수량 합계."""
    totals = [0] * n_items
    for row in matrix:
        for i in range(n_items):
            if i < len(row):
                totals[i] += _z(row[i])
    return totals


def campus_totals(matrix: list[list[Num]]) -> list[int]:
    """학원별 소계."""
    return [sum(_z(v) for v in row) for row in matrix]


def item_totals(items) -> dict[str, int]:
    """품목 리스트(.qty/.mono/.insert/.color/.pages) → 합계 행 값."""
    out = {"qty": 0, "mono": 0, "insert": 0, "color": 0, "pages": 0, "k": 0, "l": 0, "m": 0, "n": 0}
    for it in items:
        out["qty"] += _z(it.qty)
        out["mono"] += _z(it.mono)
        out["insert"] += _z(it.insert)
        out["color"] += _z(it.color)
        out["pages"] += _z(it.pages)
        k, l, m, n = print_volumes(it.qty, it.mono, it.insert, it.color)
        out["k"] += k
        out["l"] += l
        out["m"] += m
        out["n"] += n
    return out
