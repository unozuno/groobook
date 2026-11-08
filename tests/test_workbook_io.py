import os

import pytest
from openpyxl import load_workbook

from processors.order_form import workbook_io as wio
from xlsx_fixtures import make_invoice, make_marketing


def _open_and_snap(path):
    wb = wio.open_workbook(path)
    return wb, wio.snapshot(wb)


def test_backup_copies_and_prunes(tmp_path):
    f = tmp_path / "a.xlsx"
    f.write_bytes(b"orig")
    paths = [wio.backup_file(f, keep=3) for _ in range(5)]
    kept = sorted(p.name for p in wio.backups_dir().iterdir())
    assert len(kept) == 3
    assert paths[-1].read_bytes() == b"orig"
    assert paths[-1].name.endswith("_a.xlsx")


def test_check_writable_blocks_excel_lock_file(tmp_path):
    f = make_invoice(tmp_path / "청구서.xlsx")
    wio.check_writable(f)
    (tmp_path / "~$청구서.xlsx").write_bytes(b"lock")
    with pytest.raises(wio.WorkbookIOError, match="열려 있"):
        wio.check_writable(f)


def test_open_workbook_rejects_non_excel(tmp_path):
    f = tmp_path / "bad.xlsx"
    f.write_bytes(b"not a zip")
    with pytest.raises(wio.WorkbookIOError, match="읽을 수 없"):
        wio.open_workbook(f)


def test_safe_save_adds_sheet_and_keeps_everything_else(tmp_path):
    f = make_invoice(tmp_path / "청구서.xlsx")
    wb, snap = _open_and_snap(f)
    ws = wb.create_sheet("1127새시트")
    ws["A1"] = "hello"
    backup = wio.safe_save(wb, f, snap, new_sheets=["1127새시트"])
    assert backup.exists() and backup.read_bytes() != f.read_bytes()
    out = load_workbook(f)
    assert out.sheetnames == ["견적서", "1008내신블랭크", "1127새시트"]
    assert len(out["견적서"]._images) == 1
    assert out["견적서"]["G13"].value == "='1008내신블랭크'!C17"
    assert out.calculation.fullCalcOnLoad is True
    assert not list(tmp_path.glob(".groobook-*"))


def test_safe_save_allows_declared_cells_only(tmp_path):
    f = make_marketing(tmp_path / "m.xlsx")
    wb, snap = _open_and_snap(f)
    ws = wb["소모품출고내역"]
    ws["N4"] = "허용"
    wio.safe_save(wb, f, snap, allowed={"소모품출고내역": {"N4"}})
    assert load_workbook(f)["소모품출고내역"]["N4"].value == "허용"

    wb, snap = _open_and_snap(f)
    wb["소모품출고내역"]["N5"] = "허용 안 된 변경"
    before = f.read_bytes()
    with pytest.raises(wio.WorkbookIOError, match="검증에 실패"):
        wio.safe_save(wb, f, snap, allowed={"소모품출고내역": {"N4"}})
    assert f.read_bytes() == before                       # 원본 불변
    assert not list(tmp_path.glob(".groobook-*"))         # 임시 파일 정리


def test_safe_save_detects_removed_sheet_or_merge(tmp_path):
    f = make_invoice(tmp_path / "청구서.xlsx")
    wb, snap = _open_and_snap(f)
    del wb["1008내신블랭크"]
    with pytest.raises(wio.WorkbookIOError):
        wio.safe_save(wb, f, snap)
    wb, snap = _open_and_snap(f)
    wb["견적서"].unmerge_cells("B1:F1")
    with pytest.raises(wio.WorkbookIOError, match="병합"):
        wio.safe_save(wb, f, snap)


def test_safe_save_blocked_by_lock_and_replace_failure(tmp_path, monkeypatch):
    f = make_invoice(tmp_path / "청구서.xlsx")
    wb, snap = _open_and_snap(f)
    lock = tmp_path / "~$청구서.xlsx"
    lock.write_bytes(b"x")
    with pytest.raises(wio.WorkbookIOError, match="열려 있"):
        wio.safe_save(wb, f, snap)
    lock.unlink()

    before = f.read_bytes()
    def deny(src, dst):
        raise PermissionError("locked")
    monkeypatch.setattr(os, "replace", deny)
    with pytest.raises(wio.WorkbookIOError, match="저장할 수 없"):
        wio.safe_save(wb, f, snap)
    assert f.read_bytes() == before
    assert not list(tmp_path.glob(".groobook-*"))
