"""바탕화면 위치와 청구서·마케팅팀 엑셀 파일 경로 탐색.

서버가 사용자 PC 에서 돌 때만 의미가 있다 (EC2 배포본에서는 바탕화면이 없어 exists=False).

바탕화면 결정 순서: 공통설정의 desktop_dir > 환경변수 GROOBOOK_DESKTOP_DIR > OS 자동 탐색.
폴더·파일 이름 비교는 공백을 무시하고 유니코드를 NFC 로 정규화해서 한다
(macOS 는 한글 이름을 분해형 NFD 로 저장하기 때문).
"""
import os
import re
import sys
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

ENV_DESKTOP = "GROOBOOK_DESKTOP_DIR"
_FOLDERID_DESKTOP = "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}"


@dataclass
class DesktopInfo:
    path: Path
    exists: bool
    source: str   # "설정" | "환경변수" | "자동"

    def as_dict(self) -> dict:
        return {"desktop_dir": str(self.path), "exists": self.exists,
                "source": self.source, "os": sys.platform}


def norm_name(name: str) -> str:
    """이름 비교용: NFC 정규화 + 모든 공백 제거."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", name))


def _windows_known_desktop() -> Optional[Path]:
    """윈도우 셸이 알려주는 실제 바탕화면 (OneDrive 로 옮겨진 경우 포함)."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

        guid = GUID.from_buffer_copy(uuid.UUID(_FOLDERID_DESKTOP).bytes_le)
        fn = ctypes.windll.shell32.SHGetKnownFolderPath
        fn.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
                       ctypes.POINTER(ctypes.c_wchar_p)]
        out = ctypes.c_wchar_p()
        if fn(ctypes.byref(guid), 0, None, ctypes.byref(out)) != 0:
            return None
        path = out.value
        ctypes.windll.ole32.CoTaskMemFree(out)
        return Path(path) if path else None
    except Exception:
        return None


def candidate_desktops() -> list[Path]:
    home = Path.home()
    cands = [_windows_known_desktop(), home / "Desktop", home / "OneDrive" / "Desktop",
             home / "OneDrive" / "바탕 화면", home / "바탕 화면"]
    seen, out = set(), []
    for c in cands:
        if c is not None and str(c) not in seen:
            seen.add(str(c))
            out.append(c)
    return out


def resolve_desktop(configured: str = "") -> DesktopInfo:
    configured = (configured or "").strip()
    if configured:
        p = Path(configured).expanduser()
        return DesktopInfo(p, p.is_dir(), "설정")
    env = os.environ.get(ENV_DESKTOP, "").strip()
    if env:
        p = Path(env).expanduser()
        return DesktopInfo(p, p.is_dir(), "환경변수")
    cands = candidate_desktops()
    for c in cands:
        if c.is_dir():
            return DesktopInfo(c, True, "자동")
    fallback = cands[0] if cands else Path.home() / "Desktop"
    return DesktopInfo(fallback, False, "자동")


def find_child(parent: Path, wanted: str, *, want_dir: bool) -> Optional[Path]:
    """parent 바로 아래에서 이름이 wanted 와 (공백·NFC 무시하고) 같은 폴더/파일을 찾는다."""
    target = norm_name(wanted)
    try:
        entries = list(parent.iterdir())
    except OSError:
        return None
    for e in sorted(entries, key=lambda x: x.name):
        if e.name.startswith("~$") or e.name.startswith("."):
            continue
        if norm_name(e.name) != target:
            continue
        if (e.is_dir() if want_dir else e.is_file()):
            return e
    return None


# ───────── 이름 규칙 ─────────

def invoice_folder_name(d: date) -> str:
    return f"{d.year}년 {d.month:02d}월 매출청구서_소모품"


def invoice_file_name(d: date, campus: str) -> str:
    return f"{d.year}년 {d.month:02d}월 {campus} 청구서_소모품.xlsx"


def marketing_file_name(d: date) -> str:
    return f"{d.year}년 {d.month:02d}월 소모품 제작내역_Marketing팀.xlsx"


@dataclass
class FoundFile:
    path: Optional[Path]      # 실제로 찾은 경로 (없으면 None)
    expected: Path            # 못 찾았을 때 안내할 예상 경로


def find_invoice_file(desktop: Path, d: date, campus: str) -> FoundFile:
    folder_name = invoice_folder_name(d)
    file_name = invoice_file_name(d, campus)
    expected = desktop / folder_name / file_name
    folder = find_child(desktop, folder_name, want_dir=True)
    if folder is None:
        return FoundFile(None, expected)
    found = find_child(folder, file_name, want_dir=False)
    return FoundFile(found, folder / file_name if found is None else found)


def find_marketing_file(desktop: Path, d: date) -> FoundFile:
    file_name = marketing_file_name(d)
    found = find_child(desktop, file_name, want_dir=False)
    return FoundFile(found, desktop / file_name if found is None else found)
