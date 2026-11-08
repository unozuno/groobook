import unicodedata
from datetime import date

import pytest

from processors.order_form import desktop_paths as dp
from processors.order_form.settings_models import SettingsValidationError, validate_settings
from processors.order_form.seed import build_seed_settings

D = date(2026, 11, 27)


def test_name_rules():
    assert dp.invoice_folder_name(D) == "2026년 11월 매출청구서_소모품"
    assert dp.invoice_folder_name(date(2026, 9, 3)) == "2026년 09월 매출청구서_소모품"
    assert dp.invoice_file_name(D, "분당캠퍼스") == "2026년 11월 분당캠퍼스 청구서_소모품.xlsx"
    assert dp.marketing_file_name(D) == "2026년 11월 소모품 제작내역_Marketing팀.xlsx"


def test_resolve_priority(tmp_path, monkeypatch):
    cfg, env = tmp_path / "cfg", tmp_path / "env"
    cfg.mkdir()
    env.mkdir()
    monkeypatch.setenv(dp.ENV_DESKTOP, str(env))
    info = dp.resolve_desktop(str(cfg))
    assert (info.path, info.exists, info.source) == (cfg, True, "설정")
    info = dp.resolve_desktop("")
    assert (info.path, info.exists, info.source) == (env, True, "환경변수")
    monkeypatch.delenv(dp.ENV_DESKTOP)
    info = dp.resolve_desktop(str(tmp_path / "없는폴더"))
    assert info.exists is False and info.source == "설정"


def test_resolve_auto_uses_home_desktop(tmp_path, monkeypatch):
    monkeypatch.delenv(dp.ENV_DESKTOP, raising=False)
    monkeypatch.setattr(dp.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(dp, "_windows_known_desktop", lambda: None)
    assert dp.resolve_desktop("").exists is False
    (tmp_path / "Desktop").mkdir()
    info = dp.resolve_desktop("")
    assert info.path == tmp_path / "Desktop" and info.exists and info.source == "자동"


def test_find_invoice_file(tmp_path):
    folder = tmp_path / "2026년 11월 매출청구서_소모품"
    folder.mkdir()
    f = folder / "2026년 11월 분당캠퍼스 청구서_소모품.xlsx"
    f.write_bytes(b"x")
    (folder / "~$2026년 11월 분당캠퍼스 청구서_소모품.xlsx").write_bytes(b"lock")
    got = dp.find_invoice_file(tmp_path, D, "분당캠퍼스")
    assert got.path == f
    missing = dp.find_invoice_file(tmp_path, D, "평촌캠퍼스")
    assert missing.path is None
    assert missing.expected == folder / "2026년 11월 평촌캠퍼스 청구서_소모품.xlsx"
    no_folder = dp.find_invoice_file(tmp_path, date(2026, 12, 1), "분당캠퍼스")
    assert no_folder.path is None
    assert no_folder.expected == tmp_path / "2026년 12월 매출청구서_소모품" / "2026년 12월 분당캠퍼스 청구서_소모품.xlsx"


def test_find_ignores_spaces_and_unicode_form(tmp_path):
    """맥은 NFD 로 저장하고 폴더명 공백이 달라도 찾아야 한다."""
    folder = tmp_path / unicodedata.normalize("NFD", "2026년 11월  매출청구서_소모품")
    folder.mkdir()
    f = folder / unicodedata.normalize("NFD", "2026년 11월 대치본원S관 청구서_소모품.xlsx")
    f.write_bytes(b"x")
    got = dp.find_invoice_file(tmp_path, D, "대치본원 S관")
    assert got.path is not None and got.path.name == f.name


def test_find_marketing_file(tmp_path):
    f = tmp_path / unicodedata.normalize("NFD", "2026년 11월 소모품 제작내역_Marketing팀.xlsx")
    f.write_bytes(b"x")
    assert dp.find_marketing_file(tmp_path, D).path.name == f.name
    assert dp.find_marketing_file(tmp_path, date(2026, 10, 1)).path is None


def test_desktop_dir_setting_default_and_validation():
    s = build_seed_settings()
    assert s["desktop_dir"] == ""
    s["desktop_dir"] = "  C:\\Users\\a\\Desktop  "
    assert validate_settings(s)["desktop_dir"] == "C:\\Users\\a\\Desktop"
    old = build_seed_settings()
    del old["desktop_dir"]            # 이전 버전 설정 파일
    assert validate_settings(old)["desktop_dir"] == ""
    bad = build_seed_settings()
    bad["desktop_dir"] = "a\x00b"
    with pytest.raises(SettingsValidationError):
        validate_settings(bad)
