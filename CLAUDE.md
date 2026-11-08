# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

그루북 업무 자동화 웹앱 — an internal tool for Groobook (Korean educational publisher) that automates these workflows:
1. **포장전표 생성**: Parses Excel files, generates print-ready A4 PDF packaging slips
2. **청구서 메일 발송**: Parses billing Excel filenames, looks up campus emails, sends via Gmail SMTP
3. **공통발주서**: Form-driven generation of a 발주서 (purchase order) sheet plus 납품서 (delivery note) sheets in one xlsx, with an admin settings page for option lists, defaults and the campus address book

## Running the App

```bash
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload
```

Server runs at `http://127.0.0.1:8000`. There are no build or lint commands.

**Tests** (공통발주서 only):
```bash
pip install -r requirements-dev.txt
python -m pytest -q
```
Tests set `GROOBOOK_DATA_DIR` to a temp dir (see `tests/conftest.py`) so they never touch the real `data/` folder.

## Required Configuration

**`.env` file** (git-ignored, required for email feature only):
```env
GMAIL_ADDRESS=your-gmail@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

**`campus_emails.json`** (project root): Maps Korean campus names → email addresses. Must be updated manually when adding new campuses.

**`data/` directory** (git-ignored, auto-created on first use; override location with env `GROOBOOK_DATA_DIR`):
- `data/order_settings.json` — 공통발주서 admin settings (제작 종류, 선택지/기본값, 전달사항 문구, 주소록, 조건부 규칙). Seeded from `processors/order_form/seed.py` when missing; edited via `/order-settings`. Never hand-edit while the server runs.
- `data/orders/*.json` — archived source data of every generated 발주서 (for future 단가 자동 계산 / 청구서 연동).
- Back up by copying the folder; `git pull` never touches it.

**WeasyPrint system libraries** (required for PDF generation):
- Windows: GTK3 runtime (tschoonj installer)
- macOS: `brew install pango glib`
- Linux: `libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0`

## Architecture

### Request Flow — Packaging Slips

```
Browser upload → POST /api/process/{proc_type}
  → background threading.Thread
  → processors/{naeshin,quarterly,midterm}.py → slip_list[]
  → renderer/pdf_renderer.py (Jinja2 template → WeasyPrint → PDF bytes)
  → stored in tasks[task_id]
Browser polls GET /api/progress/{task_id} → GET /api/download/{task_id}
```

### Request Flow — Email Dispatch (two-step)

```
Browser upload → POST /api/email/scan
  → filename regex parse + campus_emails.json lookup
  → preview table returned (stored in email_scans[scan_id])
User confirms → POST /api/email/send
  → background thread → email_sender.py → Gmail SMTP (port 587, STARTTLS)
```

### Request Flow — 공통발주서 (synchronous, no polling)

```
Browser loads /order-form → GET /api/order-settings (settings + field meta + today)
User fills form (vanilla JS in static/js/order_form.js mirrors server validation live)
  → POST /api/order-form/generate {order, force}
  → processors/order_form/service.generate()
      validation.validate()  → errors: 422 {errors}, warnings & !force: 409 {warnings}
      xlsx_builder.build_workbook() → verify.verify_workbook() (re-evaluates formulas vs compute.py)
      archive.archive_order() → data/orders/*.json
  → 200 xlsx bytes (Content-Disposition filename*=UTF-8''…) → browser downloads via blob
Admin: /order-settings ↔ GET/PUT /api/order-settings (+ /export, /reset); PUT checks expected_updated_at (409 on conflict)
```

Modes: `order` (registered type), `blank_order` (빈 발주서, free-text spec), `blank_delivery` (빈 납품서, delivery sheet only). `order_type: multi` adds a per-campus distribution matrix → one 납품서 sheet per campus (`납품서_{캠퍼스}`), 발주수량 = column sums.

### State Management

All task state lives in two in-memory dicts in `main.py` (`tasks`, `email_scans`). State is lost on server restart. Do **not** run with `--workers > 1` (multi-process would break shared state). 공통발주서 settings are file-backed (`data/order_settings.json`) behind a module lock with atomic replace.

## Key Files

| File | Role |
|---|---|
| `main.py` | All FastAPI routes + in-memory task store |
| `processors/naeshin.py` | "비법전수 내신노트" Excel parser — fixed banding of 30 |
| `processors/quarterly.py` | Quarterly textbook parser — reads banding from Excel |
| `processors/midterm.py` | Midterm/finals parser — 3 sub-types (본책/미니북/교사용) |
| `processors/email_sender.py` | Filename regex, campus email lookup, SMTP sender |
| `renderer/pdf_renderer.py` | Selects Jinja2 template by `proc_type`, renders PDF bytes |
| `renderer/templates/slip_naeshin.html` | A4 landscape, 2×2 slip grid |
| `renderer/templates/slip_midterm.html` | A4 landscape, 2×3 slip grid (also used for quarterly) |
| `templates/work.html` | Reusable upload page — `{{ show_banding }}` flag controls midterm banding inputs |
| `campus_emails.json` | Campus name → email mapping |
| `processors/formula_eval.py` | Minimal Excel formula evaluator (cell refs, SUM, arithmetic chains); shared by 중등 청구서 and 공통발주서 verification |
| `processors/order_form/fields.py` | The 14 spec field ids/labels/groups — single source of truth for settings JSON, request JSON and the JS |
| `processors/order_form/seed.py` | Initial settings: 15 제작 종류 (지시서 4-1/4-2), rules, 53-campus address book |
| `processors/order_form/settings_models.py` / `settings_store.py` | Pydantic schema + validation; load/save/reset of `data/order_settings.json` |
| `processors/order_form/models.py` | `OrderRequest` (raw strings from the browser) and normalized `Order`/`Item`/`DeliveryNote` dataclasses |
| `processors/order_form/validation.py` | Error/warning codes with Korean messages and `path`s; builds `Order` incl. per-campus deliveries |
| `processors/order_form/compute.py` / `naming.py` / `pricing.py` / `rules.py` | Pure calculations; filename & sheet-name rules; unit-price hook (단가표 goes here later); JS-rule reference impl |
| `processors/order_form/xlsx_builder.py` / `verify.py` | openpyxl sheet writers (cell map documented inline) and post-build formula verification |
| `processors/order_form/service.py` / `archive.py` | Generate pipeline; JSON archive of each order |
| `templates/order_form.html` + `static/js/order_form.js` | 발주서 작성 UI (state → render; combobox = `<input list>` + `<datalist>`) |
| `templates/order_settings.html` + `static/js/order_settings.js` | Admin settings UI (types, options/defaults, messages, address book, export/import/reset) |
| `static/js/order_common.js` | Shared helpers: combobox, confirm modal, toast, blob download |
| `tests/` | pytest suite for 공통발주서 (compute, validation, naming, builder, settings store, API) |

## Excel Parsing Conventions

- **naeshin**: Row 3 = campus names, Row 4 = quantities
- **quarterly**: "밴딩" column in sheet contains banding value; rows = books, cols = campuses
- **midterm**: Books are columns, campuses are rows; even/odd rows alternate teacher vs. total quantities
- **email filenames**: Must match pattern `YYYY년 MM월 캠퍼스명 청구서_내신교재.xlsx`

## 공통발주서 Conventions

- Reference workbook: `sample/발주서 단일화.xlsx` (git-ignored). Sheet `발주서(sample)` / `납품서((sample)` define the output layout; `발주서단일화` holds the option matrix; `인수처주소및담당자` the address book.
- Output deviations from the sample (intentional): no yellow input-cell fills (white; only the green header row keeps a fill); 표지 row has 사이즈/코팅/동판 in E7/F7/G7; row 9 = 생산처 전달사항 (red, bold 14, merged B9:J9); 페이지합계 I column is a formula; the `/8000` cell is omitted; 공급액 = `=IF(AND(C>0,E<>""),C*E,"")`; no external links.
- Item rows: minimum 10, grows with items; totals row formulas follow. Numeric blanks are written as `None`, never 0.
- 간지/표지 사이즈 follow 내지 사이즈 **only when that type's default is `null`** (the sample's `=I2` exists for 교재 only).
- Filenames: `{YYMMDD 오늘, Asia/Seoul} 그루북 {학원|다중이름} {종류}발주.xlsx`; 빈 납품서: `… {수령자} 납품서.xlsx`. Sheet names sanitized to Excel rules (31 chars, no `\ / ? * [ ] :`) and de-duplicated with ` (2)`.
- Validation codes (`validation.py`) are mirrored in `order_form.js` — change both together.
- 빈 발주서 / 빈 납품서 are fixed **modes**, not editable types; 졸업장/엽서 are independent copies of 상장/초대장 in the seed.

## Git & Commit Guidelines

- **Atomic Commits:** Follow `.claude/rules/commit-convention.md` strictly.
- **State Management:** Keep track of unpushed local commits.
- **Push Strategy:** Do not push automatically. After completing a logical set of tasks, ask the user if they want to:
  1. **Squash & Push:** Combine multiple local commits into one clean commit and push.
  2. **Straight Push:** Push all local commits as they are.
  3. **Wait:** Keep working without pushing.
