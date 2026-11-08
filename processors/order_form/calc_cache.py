"""수식 셀의 계산값(캐시) 구하기.

openpyxl 로 저장하면 모든 수식의 계산값이 사라진다. 엑셀은 열 때 다시 계산하지만 미리보기·Numbers·보호된 보기는
다시 계산하지 않거나 일부만 계산해서, 견적서 수량·금액처럼 다른 시트를 가리키는 칸이 0 / '-' 로 보인다.
저장 직전에 값을 구해 workbook_io.inject_cached_values 로 채워 넣는다.

값은 두 가지로 구한다.
1. 직접 계산: 숫자·셀 참조(다른 시트 포함)·SUM·사칙연산·괄호, 그리고 납품서의 공급액 수식
   `=IF(AND(C9>0,E9<>""),C9*E9,"")`.
2. 계산할 수 없는 수식(외부 파일 링크 등)은 원본 파일에 저장돼 있던 값을 그대로 쓴다 — 수식이 그대로이고
   견적서처럼 값이 바뀌는 시트가 아닐 때만.
"""
import re
from typing import Optional

from openpyxl.formula import Tokenizer
from openpyxl.formula.tokenizer import Token
from openpyxl.utils import range_boundaries
from openpyxl.utils.cell import get_column_letter

MAX_DEPTH = 40
_REF = r"\$?[A-Z]+\$?\d+"
_IF_AND = re.compile(rf'=IF\(AND\(({_REF})>0,({_REF})<>""\),({_REF})\*({_REF}),""\)')


class Unsupported(Exception):
    pass


def _to_python(formula: str) -> str:
    parts = []
    for t in Tokenizer(formula).items:
        if t.type == Token.WSPACE:
            continue
        if t.type == Token.OPERAND and t.subtype == Token.NUMBER:
            parts.append(t.value)
        elif t.type == Token.OPERAND and t.subtype == Token.RANGE:
            if "[" in t.value:
                raise Unsupported("외부 통합문서 참조")
            parts.append(f"_r({t.value!r})")
        elif t.type == Token.FUNC and t.subtype == Token.OPEN and t.value.upper() == "SUM(":
            parts.append("_sum(")
        elif t.type == Token.FUNC and t.subtype == Token.CLOSE:
            parts.append(")")
        elif t.type == Token.SEP and t.subtype == Token.ARG:
            parts.append(",")
        elif t.type in (Token.OP_IN, Token.OP_PRE) and t.value in ("+", "-", "*", "/"):
            parts.append(t.value)
        elif t.type == Token.PAREN:
            parts.append(t.value)
        else:
            raise Unsupported(t.value)
    return "".join(parts)


def _split_ref(ref: str, here: str) -> tuple[str, str]:
    """'시트'!A1:B2 → (시트명, 'A1:B2'). 시트 표기가 없으면 here."""
    if "!" not in ref:
        return here, ref.replace("$", "")
    sheet, _, cells = ref.rpartition("!")
    if sheet.startswith("'") and sheet.endswith("'"):
        sheet = sheet[1:-1].replace("''", "'")
    return sheet, cells.replace("$", "")


def _clean(v):
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


class _Engine:
    def __init__(self, wb, original_cache: dict, original_formulas: dict, volatile: set):
        self.wb = wb
        self.orig_cache = original_cache
        self.orig_formulas = original_formulas
        self.volatile = volatile        # 값이 바뀔 수 있어 원본 캐시를 믿으면 안 되는 시트
        self.memo: dict[tuple, Optional[float]] = {}
        self.busy: set = set()

    def value(self, sheet: str, coord: str, depth: int = 0):
        """셀 값: 숫자 또는 None(텍스트·계산 불가). 빈 셀은 0."""
        key = (sheet, coord)
        if key in self.memo:
            return self.memo[key]
        if depth > MAX_DEPTH or key in self.busy or sheet not in self.wb.sheetnames:
            return None
        v = self.wb[sheet][coord].value
        if v is None:
            return 0
        if isinstance(v, bool):
            return None
        if isinstance(v, (int, float)):
            return v
        if not isinstance(v, str) or not v.startswith("="):
            return None
        self.busy.add(key)
        try:
            result = self._formula(sheet, coord, v, depth)
        finally:
            self.busy.discard(key)
        self.memo[key] = result
        return result

    def _formula(self, sheet: str, coord: str, formula: str, depth: int):
        m = _IF_AND.fullmatch(formula)
        if m and m.group(1) == m.group(3) and m.group(2) == m.group(4):
            qty_ref, price_ref = m.group(1).replace("$", ""), m.group(2).replace("$", "")
            qty = self.value(sheet, qty_ref, depth + 1)
            if qty is not None:
                if qty > 0 and self.wb[sheet][price_ref].value not in (None, ""):
                    price = self.value(sheet, price_ref, depth + 1)
                    return _clean(qty * price) if price is not None else None
                return None                                   # 수식이 "" 를 돌려주는 경우
            return self._fallback(sheet, coord, formula)
        try:
            env = {"_r": self._reference(sheet, depth), "_sum": self._sum, "__builtins__": {}}
            out = eval(_to_python(formula), env)           # noqa: S307 — 숫자·참조·SUM·사칙연산·괄호 토큰만 허용한 식
            if isinstance(out, (int, float)) and not isinstance(out, bool):
                return _clean(out)
        except Exception:
            pass
        return self._fallback(sheet, coord, formula)

    def _fallback(self, sheet: str, coord: str, formula: str):
        if sheet in self.volatile or self.orig_formulas.get(sheet, {}).get(coord) != formula:
            return None
        v = self.orig_cache.get(sheet, {}).get(coord)
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

    def _reference(self, sheet: str, depth: int):
        def ref(text: str):
            target, cells = _split_ref(text, sheet)
            if ":" in cells:
                c1, r1, c2, r2 = range_boundaries(cells)
                return [self.value(target, f"{get_column_letter(c)}{r}", depth + 1)
                        for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
            v = self.value(target, cells, depth + 1)
            if v is None:
                raise Unsupported("텍스트·계산 불가 셀")
            return v
        return ref

    @staticmethod
    def _sum(*args):
        total = 0
        for a in args:
            if isinstance(a, list):
                total += sum(x for x in a if isinstance(x, (int, float)) and not isinstance(x, bool))
            elif isinstance(a, (int, float)):
                total += a
        return total


def compute_cached(wb, original_cache: dict, original_snapshot: dict, volatile: tuple = ()) -> dict:
    """저장할 워크북(수식 상태)의 모든 수식 셀 계산값 → {시트명: {좌표: 숫자}}.
    original_cache: workbook_io.load_cached_numbers(원본 경로), original_snapshot: 수정 전 snapshot,
    volatile: 값이 바뀌는 시트(원본 캐시 대체 금지)."""
    orig_formulas = {title: {c: sig[0] for c, sig in s["cells"].items() if isinstance(sig[0], str) and sig[0].startswith("=")}
                     for title, s in original_snapshot["sheets"].items()}
    engine = _Engine(wb, original_cache, orig_formulas, set(volatile))
    out: dict[str, dict] = {}
    for ws in wb.worksheets:
        values = {}
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if isinstance(v, str) and v.startswith("="):
                    result = engine.value(ws.title, cell.coordinate)
                    if isinstance(result, (int, float)) and not isinstance(result, bool):
                        values[cell.coordinate] = result
        if values:
            out[ws.title] = values
    return out
