"""Pydantic 模型字段验证"""
import pytest
from pydantic import ValidationError

from aog_web.models.city import City, FleetItem, PartItem, ContactItem, Warehouse, Logistics
from aog_web.models.experience import Experience
from aog_web.models.core_plan import CorePlan
from aog_web.models.chat import ChatRequest, ChatResponse, Reference, SyncStatus


def test_fleet_item():
    f = FleetItem(model="B787", short_stay=True, after=False)
    assert f.model == "B787"
    assert f.short_stay is True
    assert f.after is False


def test_part_item():
    p = PartItem(pn="C20649000", name="B787 主轮", stock=1, unit="个")
    assert p.pn == "C20649000"
    assert p.stock == 1


def test_contact_item():
    c = ContactItem(org="东航", phone=["021-22379771"], role="7×24")
    assert c.email is None
    c2 = ContactItem(org="国航", phone=["010-12345"], email="a@b.com", role="AOG")
    assert c2.email == "a@b.com"


def test_warehouse_logistics():
    w = Warehouse(location="大兴", main=["B787 主轮"])
    l = Logistics(rail="京沪", air="国内 6h", road="京津冀 4h")
    assert w.location == "大兴"
    assert l.air == "国内 6h"


def test_city_minimal_required():
    c = City(
        code="B-北京大兴", name="北京大兴", airport="北京大兴国际机场", iata="PKX",
        pinyin="beijingdaxing", region="华北", status="现行", tags=[],
        fleet=[], parts=[], contacts=[],
        warehouse={"location": "大兴", "main": []},
        logistics={"rail": "京沪", "air": "国内 6h", "road": "京津冀 4h"},
        content_md="# 大兴", source_path="02_外战预案/B-北京大兴.md",
        updated_at="2026-07-15T00:00:00",
    )
    assert c.code == "B-北京大兴"
    assert c.region == "华北"


def test_city_invalid_region():
    with pytest.raises(ValidationError):
        City(
            code="B-北京大兴", name="北京大兴", airport="X", iata="X",
            pinyin="x", region="INVALID_REGION", status="现行", tags=[],
            fleet=[], parts=[], contacts=[],
            warehouse={"location": "", "main": []},
            logistics={"rail": "", "air": "", "road": ""},
            content_md="x", source_path="x", updated_at="2026-01-01T00:00:00",
        )


def test_city_invalid_status():
    with pytest.raises(ValidationError):
        City(
            code="X", name="X", airport="X", iata="X",
            pinyin="x", region="华北", status="INVALID", tags=[],
            fleet=[], parts=[], contacts=[],
            warehouse={"location": "", "main": []},
            logistics={"rail": "", "air": "", "road": ""},
            content_md="x", source_path="x", updated_at="2026-01-01T00:00:00",
        )


def test_experience_basic():
    e = Experience(
        id="exp-001", title="B787 风挡", category="案例", status="现行",
        tags=["B787"], summary="<200 字", content_md="# B787",
        related_pn=[], source_path="x", updated_at="2026-07-15T00:00:00",
    )
    assert e.category == "案例"


def test_experience_invalid_category():
    with pytest.raises(ValidationError):
        Experience(
            id="x", title="x", category="INVALID", status="现行",
            tags=[], summary="x", content_md="x",
            related_pn=[], source_path="x", updated_at="2026-01-01T00:00:00",
        )


def test_core_plan_basic():
    p = CorePlan(
        id="core-20260204", title="AOG 保障预案", type="master",
        content_md="# master", source_path="x", updated_at="2026-02-04T00:00:00",
    )
    assert p.type == "master"


def test_chat_request_basic():
    req = ChatRequest(q="B787")
    assert req.q == "B787"
    assert req.context_codes is None
    req2 = ChatRequest(q="B787", context_codes=["B-北京大兴"])
    assert req2.context_codes == ["B-北京大兴"]


def test_chat_request_q_required():
    with pytest.raises(ValidationError):
        ChatRequest(q="")


def test_reference_min_score():
    r = Reference(id="x", title="x", href="/x", snippet="x", score=0.5)
    assert r.score == 0.5


def test_chat_response_nsm2_min_references():
    """★ NSM-2 红线: 响应模型也校验 references ≥ 1"""
    # 0 ref → ValidationError
    with pytest.raises(ValidationError):
        ChatResponse(answer="x", references=[], model="mock", latency_ms=100)
    # 1 ref → OK
    resp = ChatResponse(
        answer="x", references=[Reference(id="x", title="x", href="/x", snippet="x", score=0.5)],
        model="mock", latency_ms=100,
    )
    assert len(resp.references) >= 1


def test_sync_status_basic():
    s = SyncStatus(status="idle", last_sync=None, queue=0, indexed_total=0)
    assert s.status == "idle"
    s2 = SyncStatus(status="error", last_sync="2026-07-15T00:00:00", queue=5, indexed_total=100, last_error="oops")
    assert s2.last_error == "oops"
