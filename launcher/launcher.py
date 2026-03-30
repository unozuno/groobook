import os
import sys
import socket
import subprocess
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import scrolledtext, messagebox


# ── PROJECT_ROOT 감지 ──────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # PyInstaller 번들 실행 중
    if sys.platform == "darwin":
        # .app/Contents/MacOS/그루북 → 3단계 위 = 프로젝트 루트
        _exe_dir = os.path.dirname(sys.executable)           # .../MacOS/
        PROJECT_ROOT = os.path.normpath(os.path.join(_exe_dir, "..", "..", ".."))
    else:
        # Windows: .exe 파일이 프로젝트 루트에 위치
        PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    # 개발 모드: launcher/launcher.py → 1단계 위 = 프로젝트 루트
    PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))

# ── venv Python 경로 ───────────────────────────────────────────────────────────
if sys.platform == "win32":
    VENV_PYTHON = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
else:
    VENV_PYTHON = os.path.join(PROJECT_ROOT, "venv", "bin", "python")

SERVER_URL = "http://127.0.0.1:8000"
PORT = 8000


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def build_env() -> dict:
    """uvicorn 프로세스에 전달할 환경 변수 구성."""
    env = os.environ.copy()
    if sys.platform == "darwin":
        # WeasyPrint가 pango/glib 라이브러리를 찾을 수 있도록 Homebrew 경로 주입
        homebrew_lib = "/opt/homebrew/lib"       # Apple Silicon
        if not os.path.isdir(homebrew_lib):
            homebrew_lib = "/usr/local/lib"      # Intel Mac
        existing = env.get("DYLD_LIBRARY_PATH", "")
        env["DYLD_LIBRARY_PATH"] = f"{homebrew_lib}:{existing}" if existing else homebrew_lib
    return env


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("그루북 서버")
        self.resizable(False, False)
        self._proc: subprocess.Popen | None = None
        self._log_thread: threading.Thread | None = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 구성 ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        pad = {"padx": 16, "pady": 8}

        # 상태 레이블
        self._status_var = tk.StringVar(value="⚪  준비됨")
        tk.Label(self, textvariable=self._status_var, font=("", 13, "bold"),
                 anchor="w", width=28).pack(fill="x", **pad)

        # 시작/중지 버튼
        self._btn = tk.Button(self, text="서버 시작", width=22, height=2,
                              bg="#4CAF50", fg="white", font=("", 12, "bold"),
                              relief="flat", cursor="hand2",
                              command=self._toggle)
        self._btn.pack(padx=16, pady=(0, 8))

        # 로그 영역
        tk.Label(self, text="로그", anchor="w").pack(fill="x", padx=16)
        self._log = scrolledtext.ScrolledText(self, width=52, height=12,
                                              state="disabled", font=("Courier", 10))
        self._log.pack(padx=16, pady=(0, 12))

    # ── 버튼 토글 ──────────────────────────────────────────────────────────────
    def _toggle(self):
        if self._proc is None:
            self._start_server()
        else:
            self._stop_server()

    # ── 서버 시작 ──────────────────────────────────────────────────────────────
    def _start_server(self):
        # 사전 검증
        if not os.path.isfile(VENV_PYTHON):
            messagebox.showerror(
                "오류",
                f"가상 환경을 찾을 수 없습니다.\n\n"
                f"경로: {VENV_PYTHON}\n\n"
                "프로젝트 폴더에 venv가 올바르게 설치되어 있는지 확인하세요."
            )
            return

        if is_port_in_use(PORT):
            answer = messagebox.askyesno(
                "포트 사용 중",
                f"포트 {PORT}이 이미 사용 중입니다.\n\n"
                "브라우저에서 바로 접속하시겠습니까?"
            )
            if answer:
                webbrowser.open(SERVER_URL)
            return

        self._append_log(f"프로젝트 경로: {PROJECT_ROOT}\n")
        self._append_log("서버를 시작하는 중...\n")

        try:
            self._proc = subprocess.Popen(
                [VENV_PYTHON, "-m", "uvicorn", "main:app",
                 "--host", "127.0.0.1", "--port", str(PORT)],
                cwd=PROJECT_ROOT,
                env=build_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            messagebox.showerror("실행 오류", str(e))
            self._proc = None
            return

        self._btn.config(text="서버 중지", bg="#f44336")
        self._status_var.set("🟢  실행 중")

        # 로그 스트리밍 스레드
        self._log_thread = threading.Thread(target=self._stream_logs, daemon=True)
        self._log_thread.start()

        # 브라우저 자동 오픈 (2.5초 지연)
        threading.Thread(target=self._open_browser_delayed, daemon=True).start()

    def _open_browser_delayed(self):
        time.sleep(2.5)
        if self._proc is not None:
            webbrowser.open(SERVER_URL)

    # ── 서버 중지 ──────────────────────────────────────────────────────────────
    def _stop_server(self):
        if self._proc is None:
            return
        self._append_log("\n서버를 종료하는 중...\n")
        self._proc.terminate()
        try:
            self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None
        self._btn.config(text="서버 시작", bg="#4CAF50")
        self._status_var.set("⚪  준비됨")
        self._append_log("서버가 종료되었습니다.\n")

    # ── 로그 스트리밍 ──────────────────────────────────────────────────────────
    def _stream_logs(self):
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            self._append_log(line)
        # 프로세스가 예기치 않게 종료된 경우
        if self._proc is not None:
            self.after(0, self._handle_unexpected_exit)

    def _handle_unexpected_exit(self):
        if self._proc is None:
            return
        ret = self._proc.poll()
        if ret is not None and ret != 0:
            self._proc = None
            self._btn.config(text="서버 시작", bg="#4CAF50")
            self._status_var.set("🔴  오류 발생")
            self._append_log(f"\n[서버가 종료되었습니다. 종료 코드: {ret}]\n")

    def _append_log(self, text: str):
        self._log.config(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.config(state="disabled")

    # ── 창 닫기 ────────────────────────────────────────────────────────────────
    def _on_close(self):
        self._stop_server()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
