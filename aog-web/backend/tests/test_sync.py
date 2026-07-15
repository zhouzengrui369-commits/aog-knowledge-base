"""GET /api/sync/status + POST /api/reindex + GET /api/reindex/{job_id} + /files/"""
import pytest


@pytest.mark.asyncio
async def test_sync_status_default(client, seeded_sqlite):
    r = await client.get("/api/sync/status")
    assert r.status_code == 200
    body = r.json()
    for key in ["status", "last_sync", "queue", "indexed_total"]:
        assert key in body
    assert body["status"] in {"idle", "running", "error"}
    assert isinstance(body["queue"], int)
    assert isinstance(body["indexed_total"], int)


@pytest.mark.asyncio
async def test_reindex_full(client):
    """POST /api/reindex 不传 paths = 全量"""
    r = await client.post("/api/reindex", json={})
    assert r.status_code == 200
    body = r.json()
    assert "job_id" in body
    assert body["status"] in {"queued", "running", "done"}
    job_id = body["job_id"]

    # 查询 job
    r2 = await client.get(f"/api/reindex/{job_id}")
    assert r2.status_code == 200
    job = r2.json()
    assert job["job_id"] == job_id
    assert job["status"] in {"running", "done"}
    assert "progress" in job
    assert 0 <= job["progress"] <= 100


@pytest.mark.asyncio
async def test_reindex_with_paths(client):
    r = await client.post("/api/reindex", json={"paths": ["/tmp/a.md", "/tmp/b.md"]})
    assert r.status_code == 200
    body = r.json()
    assert "job_id" in body


@pytest.mark.asyncio
async def test_reindex_job_not_found(client):
    r = await client.get("/api/reindex/nonexistent-job-id")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_files_404(client):
    """空根目录 → 404"""
    r = await client.get("/files/anything.docx")
    assert r.status_code == 404
