"""사용자의 기존 엑셀 파일을 안전하게 수정·저장하기 위한 도구.

흐름: 열기 → 수정 전 스냅샷 → (호출자가 시트 추가·셀 입력) → safe_save
  1. 잠금 확인  : 엑셀이 열어 둔 파일(~$ 잠금 파일, 쓰기 불가)이면 저장하지 않고 안내
  2. 백업       : data/backups/ 에 원본 복사 (최근 N개 유지)
  3. 임시 저장  : 같은 폴더의 임시 파일에 저장
  4. 검증       : 임시 파일을 다시 열어 기존 시트가 그대로인지 확인 (호출자가 허용한 셀만 변경 가능)
  5. 교체       : 검증을 통과했을 때만 os.replace 로 원본을 교체 (실패하면 원본은 건드리지 않음)
"""
import os
import re
import shutil
import uuid
import zipfile
from xml.etree import ElementTree as ET
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

_NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def load_cached_numbers(path: Path) -> dict:
    """원본 파일에 저장돼 있는 계산값 중 숫자만 {시트명: {좌표: 숫자}} 로 읽는다 (읽을 수 없으면 빈 값)."""
    try:
        wb = load_workbook(path, data_only=True)
    except Exception:
        return {}
    try:
        out = {}
        for ws in wb.worksheets:
            out[ws.title] = {c.coordinate: c.value for row in ws.iter_rows() for c in row
                             if isinstance(c.value, (int, float)) and not isinstance(c.value, bool)}
        return out
    finally:
        wb.close()


def inject_cached_values(path: Path, values: dict) -> int:
    """openpyxl 은 수식 셀의 계산값(캐시)을 비워 저장한다. 엑셀은 열 때 다시 계산하지만, 다시 계산하지 않는
    프로그램(미리보기·Numbers·보호된 보기)에서는 0 이나 '-' 로 보인다. 우리가 값을 아는 수식 셀에 한해
    계산값을 직접 채워 넣는다.  values: {시트명: {셀 좌표: 숫자}}  →  채운 셀 개수."""
    if not values:
        return 0
    with zipfile.ZipFile(path) as zin:
        files = {name: zin.read(name) for name in zin.namelist()}
        infos = {i.filename: i for i in zin.infolist()}
    wb_xml = ET.fromstring(files["xl/workbook.xml"])
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(files["xl/_rels/workbook.xml.rels"])}
    sheet_files = {}
    for sh in wb_xml.iter(f"{_NS_MAIN}sheet"):
        target = rels.get(sh.get(f"{_NS_REL}id"), "")
        sheet_files[sh.get("name")] = "xl/" + target.lstrip("/").removeprefix("xl/")
    pattern = re.compile(r'(<c r="([A-Z]+[0-9]+)"(?: [^>]*)?>\s*<f(?: [^>]*)?>[^<]*</f>)\s*(?:<v\s*/>|<v></v>)?(\s*</c>)')
    done = 0
    for title, cells in values.items():
        name = sheet_files.get(title)
        if name not in files:
            continue
        count = 0

        def fill(m):
            nonlocal count
            number = cells.get(m.group(2))
            if isinstance(number, bool) or not isinstance(number, (int, float)):
                return m.group(0)
            count += 1
            return f"{m.group(1)}<v>{number!r}</v>{m.group(3)}"
        files[name] = pattern.sub(fill, files[name].decode("utf-8")).encode("utf-8")
        done += count
    tmp = path.with_name(path.name + ".cache")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for fname, data in files.items():
            zout.writestr(infos[fname], data, compress_type=zipfile.ZIP_DEFLATED)
    os.replace(tmp, path)
    return done


def safe_save(wb, path: Path, before: dict, allowed: Optional[dict] = None,
              new_sheets: Optional[list] = None, expected: Optional[dict] = None,
              cached: Optional[dict] = None) -> Path:
    """검증을 통과했을 때만 원본을 교체한다. 백업 파일 경로를 돌려준다.
    cached: {시트명: {셀: 숫자}} — 새로 쓴 수식 셀의 계산값 (inject_cached_values 참고)."""
    check_writable(path)
    backup = backup_file(path)
    wb.calculation.fullCalcOnLoad = True
    tmp = path.with_name(f".groobook-{uuid.uuid4().hex[:8]}.tmp.xlsx")
    try:
        wb.save(tmp)
        if cached:
            inject_cached_values(tmp, cached)
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
