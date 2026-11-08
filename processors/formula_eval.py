"""간단한 Excel 수식 평가기.

openpyxl 은 수식을 계산하지 않으므로, 캐시값이 없는 수식 셀의 값을 Python 에서
직접 구할 때 사용한다. 지원 범위:
- 셀 참조 (A1, $A$1)
- SUM(범위) / ROUND(SUM(범위), n)
- 셀 참조끼리의 사칙연산 체인 (A1+B1, $E11*F11, A1+B1+C1 …)
"""
import re

from openpyxl.utils import column_index_from_string

_RE_CELL_REF = re.compile(r'^\$?([A-Za-z]+)\$?(\d+)$')
_CELL = r'\$?[A-Za-z]+\$?\d+'
_RE_ARITH_CHAIN = re.compile(rf'({_CELL})([+\-*/]({_CELL}))+')
_RE_SUM = re.compile(r'(?:ROUND\()?SUM\(([^)]+)\)(?:,\s*-?\d+\))?', re.IGNORECASE)

MAX_DEPTH = 4


def cell_ref_to_rc(ref: str):
    """'$A$1' / 'A1' → (row, col) 1-based. 실패 시 (None, None)."""
    m = _RE_CELL_REF.match(ref.strip())
    if not m:
        return None, None
    return int(m.group(2)), column_index_from_string(m.group(1).upper())


def get_val(ws, row, col, depth=0):
    """셀 값을 반환. 수식이면 재귀 평가(최대 MAX_DEPTH 단계). 계산 불가 시 None."""
    if depth > MAX_DEPTH:
        return None
    v = ws.cell(row=row, column=col).value
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str) or not v.startswith('='):
        return None
    return eval_expr(ws, v[1:].strip(), depth)


def eval_expr(ws, expr: str, depth: int):
    """수식 문자열(앞의 '=' 제외) 평가."""
    expr = expr.strip()

    m = _RE_SUM.fullmatch(expr)
    if m:
        return eval_sum(ws, m.group(1).strip(), depth)

    if _RE_ARITH_CHAIN.fullmatch(expr):
        parts = re.split(r'([+\-*/])', expr)
        r, c = cell_ref_to_rc(parts[0])
        if r is None:
            return None
        result = get_val(ws, r, c, depth + 1)
        if result is None:
            return None
        for i in range(1, len(parts) - 1, 2):
            op = parts[i]
            r, c = cell_ref_to_rc(parts[i + 1])
            if r is None:
                return None
            v = get_val(ws, r, c, depth + 1)
            if v is None:
                return None
            if op == '+':
                result += v
            elif op == '-':
                result -= v
            elif op == '*':
                result *= v
            elif op == '/' and v != 0:
                result /= v
            else:
                return None
        return result

    # 단일 셀 참조 (=A1)
    r, c = cell_ref_to_rc(expr)
    if r is not None:
        return get_val(ws, r, c, depth + 1)

    return None


def eval_sum(ws, range_str: str, depth: int):
    """SUM 인자 문자열(A1:B10 또는 A1) 평가. 빈 셀은 0 으로 취급."""
    if ':' in range_str:
        parts = range_str.split(':')
        r1, c1 = cell_ref_to_rc(parts[0])
        r2, c2 = cell_ref_to_rc(parts[1])
        if None in (r1, c1, r2, c2):
            return None
        total = 0.0
        for r in range(r1, r2 + 1):
            for c in range(c1, c2 + 1):
                v = get_val(ws, r, c, depth + 1)
                if v is not None:
                    total += v
        return total
    r, c = cell_ref_to_rc(range_str)
    return get_val(ws, r, c, depth + 1) if r else None
