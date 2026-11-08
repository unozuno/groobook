from processors.email_sender import scan_files
from processors.order_form import settings_store


def _set_email(name, email):
    s = settings_store.load_settings()
    for a in s["address_book"]:
        if a["name"] == name:
            a["email"] = email
    settings_store.save_settings(s)


def _file(name):
    return {"filename": name, "bytes": b"x"}


def test_scan_uses_address_book_email():
    _set_email("분당캠퍼스", "bundang@test.kr")
    res = scan_files([_file("2026년 11월 분당캠퍼스 청구서_내신교재.xlsx")])
    assert [(p["campus"], p["email"]) for p in res["preview"]] == [("분당캠퍼스", "bundang@test.kr")]


def test_scan_matches_names_ignoring_spaces():
    _set_email("대치본원 S관", "s@test.kr")             # 주소록은 공백 있음, 파일명은 없음
    res = scan_files([_file("2026년 11월 대치본원S관 청구서_내신교재.xlsx")])
    assert res["preview"][0]["email"] == "s@test.kr"


def test_unregistered_or_blank_email_is_missing():
    res = scan_files([_file("2026년 11월 분당캠퍼스 청구서_내신교재.xlsx"),
                      _file("2026년 11월 없는학원 청구서_소모품.xlsx")])
    assert [p["email"] for p in res["preview"]] == ["이메일 없음", "이메일 없음"]


def test_edit_in_settings_applies_immediately():
    _set_email("분당캠퍼스", "old@test.kr")
    _set_email("분당캠퍼스", "new@test.kr")
    res = scan_files([_file("2026년 11월 분당캠퍼스 청구서_내신교재.xlsx")])
    assert res["preview"][0]["email"] == "new@test.kr"
    assert next(iter(res["groups"].values()))[0]["email"] == "new@test.kr"
