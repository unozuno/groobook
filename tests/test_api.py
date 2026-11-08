import json
from io import BytesIO
from urllib.parse import unquote

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from conftest import make_request
from main import app
from processors.order_form.archive import orders_dir


@pytest.fixture
def client():
    return TestClient(app)


def _filename(res) -> str:
    cd = res.headers["content-disposition"]
    assert cd.startswith("attachment; filename*=UTF-8''")
    return unquote(cd.split("''", 1)[1])


@pytest.mark.parametrize("path, active", [("/order-form", "공통발주서"), ("/order-settings", "공통설정")])
def test_pages_render(client, path, active):
    res = client.get(path)
    assert res.status_code == 200
    assert active in res.text
    assert "/static/js/order_common.js" in res.text
    if path == "/order-form":
        assert 'class="nav-item active"' in res.text
    else:
        assert 'class="sidebar-brand active"' in res.text


def test_home_has_cards(client):
    html = client.get("/").text
    assert 'href="/order-form"' in html
    # 설정은 메뉴·카드가 아니라 로고 링크로 이동한다
    assert 'class="sidebar-brand" title="공통설정"' in html and 'href="/order-settings" class="nav-item' not in html
    assert 'href="/order-settings" class="card"' not in html


def test_get_settings_with_meta(client):
    res = client.get("/api/order-settings")
    assert res.status_code == 200
    body = res.json()
    assert len(body["meta"]["fields"]) == 14
    assert body["meta"]["groups"][0]["name"] == "제본"
    assert len(body["settings"]["types"]) == 15
    assert len(body["meta"]["today"]) == 10


def test_put_settings_roundtrip_and_conflict(client):
    s = client.get("/api/order-settings").json()["settings"]
    s["multi_label"] = "여러곳"
    res = client.put("/api/order-settings", json={"settings": s, "expected_updated_at": s["updated_at"]})
    assert res.status_code == 200
    assert res.json()["settings"]["multi_label"] == "여러곳"
    # 오래된 updated_at 으로 다시 저장 → 409
    res = client.put("/api/order-settings", json={"settings": s, "expected_updated_at": s["updated_at"]})
    assert res.status_code == 409


def test_put_settings_rejects_duplicates(client):
    s = client.get("/api/order-settings").json()["settings"]
    s["types"][0]["fields"]["binding_method"]["options"].append("무선제본")
    res = client.put("/api/order-settings", json={"settings": s})
    assert res.status_code == 422
    assert any("중복" in e for e in res.json()["errors"])


def test_export_and_reset(client):
    res = client.get("/api/order-settings/export")
    assert res.status_code == 200
    assert _filename(res).startswith("order_settings_")
    assert json.loads(res.content)["multi_label"] == "다중"

    s = client.get("/api/order-settings").json()["settings"]
    s["types"] = s["types"][:1]
    client.put("/api/order-settings", json={"settings": s})
    assert len(client.get("/api/order-settings").json()["settings"]["types"]) == 1
    res = client.post("/api/order-settings/reset")
    assert res.status_code == 200 and len(res.json()["settings"]["types"]) == 15


def test_generate_single_returns_xlsx_and_archives(client):
    req = make_request().model_dump()
    res = client.post("/api/order-form/generate", json={"order": req})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("application/vnd.openxmlformats")
    name = _filename(res)
    assert name.endswith(" 그루북 평촌캠퍼스 교재발주.xlsx")
    wb = load_workbook(BytesIO(res.content))
    assert wb.sheetnames == ["발주서", "납품서"]
    archived = list(orders_dir().glob("*.json"))
    assert len(archived) == 1
    saved = json.loads(archived[0].read_text(encoding="utf-8"))
    assert saved["filename"] == name and saved["order"]["campus"] == "평촌캠퍼스"


def test_generate_warning_requires_force(client):
    req = make_request(campus="새학원").model_dump()
    res = client.post("/api/order-form/generate", json={"order": req})
    assert res.status_code == 409
    assert res.json()["warnings"][0]["code"] == "ADDRESS_NOT_FOUND"
    assert not list(orders_dir().glob("*.json")) if orders_dir().exists() else True

    res = client.post("/api/order-form/generate", json={"order": req, "force": True})
    assert res.status_code == 200
    assert len(list(orders_dir().glob("*.json"))) == 1


def test_generate_errors_422(client):
    req = make_request(items=[{"name": "x", "qty": "abc"}], campus="").model_dump()
    res = client.post("/api/order-form/generate", json={"order": req, "force": True})
    assert res.status_code == 422
    codes = {e["code"] for e in res.json()["errors"]}
    assert {"ITEM_NUM_INVALID", "CAMPUS_REQUIRED"} <= codes


def test_generate_multi(client):
    req = make_request(order_type="multi", multi_name="평촌분당", distribution=[
        {"campus": "평촌캠퍼스", "qtys": ["700", "0", "5"]},
        {"campus": "분당캠퍼스", "qtys": ["300", "10", ""]},
    ]).model_dump()
    res = client.post("/api/order-form/generate", json={"order": req})
    assert res.status_code == 200, res.text
    assert _filename(res).endswith(" 그루북 평촌분당 교재발주.xlsx")
    wb = load_workbook(BytesIO(res.content))
    assert wb.sheetnames == ["발주서", "납품서_평촌캠퍼스", "납품서_분당캠퍼스"]
