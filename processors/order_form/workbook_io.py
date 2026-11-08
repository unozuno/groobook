"""사용자의 기존 엑셀 파일을 안전하게 수정·저장하기 위한 도구.

흐름: 열기 → 수정 전 스냅샷 → (호출자가 시트 추가·셀 입력) → safe_save
  1. 잠금 확인  : 엑셀이 열어 둔 파일(~$ 잠금 파일, 쓰기 불가)이면 저장하지 않고 안내
  2. 백업       : data/backups/ 에 원본 복사 (최근 N개 유지)
  3. 임시 저장  : 같은 폴더의 임시 파일에 저장
  4. 검증       : 임시 파일을 다시 열어 기존 시트가 그대로인지 확인 (호출자가 허용한 셀만 변경 가능)
  5. 교체       : 검증을 통과했을 때만 os.replace 로 원본을 교체 (실패하면 원본은 건드리지 않음)
"""
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Optional

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from processors.order_form.clock import now_seoul
from processors.order_form.settings_store import data_dir

BACKUP_KEEP = 30


class WorkbookIOError(Exception):
    """사용자에게 그대로 보여줄 수 있는 한국어 메시지를 가진 오류."""


# ───────── 백업 · 잠금 ─────────

def backups_dir() -> Path:
    return data_dir() / "backups"


def backup_file(path: Path, keep: int = BACKUP_KEEP) -> Path:
    folder = backups_dir()
    folder.mkdir(parents=True, exist_ok=True)
    # 마이크로초까지 넣어 이름순 = 시간순이 되게 한다 (정리할 때 오래된 것부터 지우기 위함)
    stamp = now_seoul().strftime("%y%m%d_%H%M%S_%f")
    dest = folder / f"{stamp}_{path.name}"
    n = 2
    while dest.exists():
        dest = folder / f"{stamp}_{n}_{path.name}"
        n += 1
    shutil.copy2(path, dest)
    olds = sorted(p for p in folder.iterdir() if p.is_file())
    for p in olds[:-keep] if keep > 0 else olds:
        try:
            p.unlink()
        except OSError:
            pass
    return dest


def check_writable(path: Path) -> None:
    lock = path.parent / f"~${path.name}"
    if lock.exists():
        raise WorkbookIOError(
            f"'{path.name}' 이(가) 엑셀에서 열려 있는 것 같습니다. 파일을 닫은 뒤 다시 시도해 주세요.")
    try:
        with open(path, "r+b"):
            pass
    except PermissionError:
        raise WorkbookIOError(
            f"'{path.name}' 을(를) 쓸 수 없습니다. 엑셀에서 열려 있거나 읽기 전용입니다. 닫은 뒤 다시 시도해 주세요.")
    except OSError as e:
        raise WorkbookIOError(f"'{path.name}' 을(를) 열 수 없습니다: {e}")


def open_workbook(path: Path):
    try:
        return load_workbook(path)          # keep_links=True (외부 링크 유지)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, ValueError) as e:
        raise WorkbookIOError(f"'{path.name}' 을(를) 엑셀 파일로 읽을 수 없습니다: {e}")
    except OSError as e:
        raise WorkbookIOError(f"'{path.name}' 을(를) 열 수 없습니다: {e}")


# ───────── 스냅샷 · 검증 ─────────

def _color(c) -> Optional[str]:
    if c is None:
        return None
    if getattr(c, "type", None) == "rgb":
        return c.rgb
    if getattr(c, "type", None) == "theme":
        # tint 는 저장 시 부동소수점 표기 끝자리가 달라질 수 있어 반올림해서 비교한다
        return f"theme{c.theme}/{round(c.tint or 0, 6)}"
    return str(getattr(c, "indexed", None))


def _cell_sig(cell) -> tuple:
    f, fl, b, a = cell.font, cell.fill, cell.border, cell.alignment
    return (
        cell.value,
        cell.number_format,
        (f.name, f.sz, f.b, f.i, _color(f.color)),
        (fl.fill_type, _color(fl.fgColor) if fl.fill_type else None),
        tuple(getattr(side, "style", None) for side in (b.left, b.right, b.top, b.bottom)),
        (a.horizontal, a.vertical, a.wrap_text),
    )


def _images(ws) -> list:
    out = []
    for img in getattr(ws, "_images", []):
        anchor = getattr(img, "anchor", None)
        frm = getattr(anchor, "_from", None)
        out.append((getattr(frm, "col", None), getattr(frm, "row", None)))
    return sorted(out, key=lambda x: (str(x[0]), str(x[1])))


def snapshot(wb) -> dict:
    sheets = {}
    for ws in wb.worksheets:
        cells = {}
        for row in ws.iter_rows():
            for c in row:
                sig = _cell_sig(c)
                if sig[0] is not None or c.has_style:
                    cells[c.coordinate] = sig
        sheets[ws.title] = {
            "cells": cells,
            "merged": sorted(str(r) for r in ws.merged_cells.ranges),
            "widths": {k: round(v.width or 0, 2) for k, v in ws.column_dimensions.items() if v.width},
            "images": _images(ws),
        }
    return {
        "order": [ws.title for ws in wb.worksheets],
        "sheets": sheets,
        "external_links": len(getattr(wb, "_external_links", [])),
    }


def compare_snapshots(before: dict, after: dict, allowed: Optional[dict] = None,
                      new_sheets: Optional[list] = None, expected: Optional[dict] = None) -> list[str]:
    """수정 전·후 스냅샷 차이를 문제 목록으로 돌려준다.
    allowed: {시트명: {셀 좌표}} — 이 셀들의 변경(값·서식)은 허용.
    new_sheets: 끝에 새로 생겨야 하는 시트 이름 목록.
    expected: {시트명: 함수} — 수정 전 시트 스냅샷을 '의도한 변경(예: 줄 삽입)이 적용된 모습'으로 바꾸는 함수.
              이 시트는 바뀐 모습과 비교한다 (allowed 의 셀은 여전히 비교에서 제외)."""
    allowed = allowed or {}
    new_sheets = new_sheets or []
    problems: list[str] = []

    expected_order = before["order"] + new_sheets
    if after["order"] != expected_order:
        problems.append(f"시트 구성이 예상과 다릅니다: 예상 {expected_order}, 실제 {after['order']}")
    if after["external_links"] != before["external_links"]:
        problems.append(f"외부 링크 개수가 달라졌습니다 ({before['external_links']} → {after['external_links']})")

    for title, b in before["sheets"].items():
        if title in (expected or {}):
            b = expected[title](b)
        a = after["sheets"].get(title)
        if a is None:
            problems.append(f"시트 '{title}' 이(가) 사라졌습니다")
            continue
        ok_cells = allowed.get(title, set())
        for coord in set(b["cells"]) | set(a["cells"]):
            if coord in ok_cells:
                continue
            if b["cells"].get(coord) != a["cells"].get(coord):
                problems.append(f"'{title}'!{coord} 내용이 달라졌습니다")
                if len(problems) > 20:
                    return problems
        if b["merged"] != a["merged"]:
            problems.append(f"'{title}' 병합 셀이 달라졌습니다")
        if b["widths"] != a["widths"]:
            problems.append(f"'{title}' 열 너비가 달라졌습니다")
        if b["images"] != a["images"]:
            problems.append(f"'{title}' 이미지가 달라졌습니다")
    return problems


# ───────── 안전 저장 ─────────

def safe_save(wb, path: Path, before: dict, allowed: Optional[dict] = None,
              new_sheets: Optional[list] = None, expected: Optional[dict] = None) -> Path:
    """검증을 통과했을 때만 원본을 교체한다. 백업 파일 경로를 돌려준다."""
    check_writable(path)
    backup = backup_file(path)
    wb.calculation.fullCalcOnLoad = True
    tmp = path.with_name(f".groobook-{uuid.uuid4().hex[:8]}.tmp.xlsx")
    try:
        wb.save(tmp)
        reloaded = open_workbook(tmp)
        try:
            problems = compare_snapshots(before, snapshot(reloaded), allowed, new_sheets, expected)
        finally:
            reloaded.close()
        if problems:
            raise WorkbookIOError("저장 결과 검증에 실패해 원본을 그대로 두었습니다: " + " / ".join(problems[:5]))
        try:
            os.replace(tmp, path)
        except PermissionError:
            raise WorkbookIOError(
                f"'{path.name}' 을(를) 저장할 수 없습니다. 엑셀에서 열려 있다면 닫은 뒤 다시 시도해 주세요.")
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return backup
