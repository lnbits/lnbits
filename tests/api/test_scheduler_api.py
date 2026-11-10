import time
from uuid import uuid4

import pytest

from lnbits.core.crud import scheduler as crud
from lnbits.core.crud.settings import get_settings_field
from lnbits.core.crud.users import create_account, delete_account
from lnbits.core.models.scheduler import ScheduledJob
from lnbits.core.models.users import Account


@pytest.fixture
async def scheduled_jobs(http_client):
    prefix = f"scheduler-{uuid4().hex}"
    namespace = f"extension:{prefix}"
    now = int(time.time())
    jobs = [
        ScheduledJob(
            id=f"{prefix}-core",
            namespace="core",
            handler="refresh",
            cron_expression="0 * * * *",
            next_run_at=now + 300,
        ),
        ScheduledJob(
            id=f"{prefix}-shared",
            namespace=namespace,
            handler="collect_prices",
            cron_expression="* * * * *",
            next_run_at=now + 60,
            payload_json='{"secret":"private-scheduler-payload"}',
        ),
        ScheduledJob(
            id=f"{prefix}-user",
            namespace=namespace,
            handler="check_alerts",
            cron_expression="*/10 * * * *",
            timezone="Europe/Bucharest",
            next_run_at=now + 120,
            user_id="private-scheduler-owner",
            enabled=False,
        ),
    ]
    for job in jobs:
        await crud.save_scheduled_job(job)
    await crud.claim_scheduled_job(
        jobs[1].id, "private-scheduler-lease", now + 60, now + 120
    )
    yield jobs
    for job in jobs:
        await crud.delete_scheduled_job(job.id, job.namespace, job.user_id, now + 120)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/scheduler/api/v1",
        "/scheduler/api/v1/sources",
        "/scheduler/api/v1/runs",
        "/scheduler/runs",
    ],
)
@pytest.mark.parametrize("role", ["anonymous", "user", "admin"])
async def test_scheduler_api_access(
    http_client, user_headers_from, admin_user, path, role
):
    headers = user_headers_from if role == "user" else {}
    if role == "admin":
        login = await http_client.post(
            "/api/v1/auth",
            json={"username": admin_user.username, "password": "secret1234"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    response = await http_client.get(path, headers=headers)
    assert response.status_code == {"anonymous": 401, "user": 403, "admin": 200}[role]
    if path == "/scheduler/runs" and role == "admin":
        assert 'id="page-scheduler-runs"' in response.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/scheduler/api/v1",
        "/scheduler/api/v1/sources",
        "/scheduler/api/v1/runs",
        "/scheduler/runs",
    ],
)
async def test_scheduler_api_respects_disabled_admin_ui(
    http_client, settings, superuser_token, path
):
    settings.lnbits_admin_ui = False
    response = await http_client.get(
        path, headers={"Authorization": f"Bearer {superuser_token}"}
    )
    assert response.status_code == 503


@pytest.mark.anyio
async def test_scheduler_overview_paginates_and_omits_private_fields(
    http_client, superuser_token, scheduled_jobs
):
    prefix = scheduled_jobs[0].id.removesuffix("-core")
    headers = {"Authorization": f"Bearer {superuser_token}"}
    response = await http_client.get(
        "/scheduler/api/v1", params={"search": prefix, "limit": 2}, headers=headers
    )
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 3
    assert [job["scope"] for job in page["data"]] == ["extension", "user"]
    assert page["data"][1]["timezone"] == "Europe/Bucharest"
    assert page["data"][1]["enabled"] is False
    for job in page["data"]:
        assert set(job) == {
            "id",
            "namespace",
            "handler",
            "scope",
            "user_id",
            "username",
            "email",
            "cron_expression",
            "timezone",
            "enabled",
            "next_run_at",
            "last_run_at",
            "last_result",
        }
        assert job["last_run_at"] is None
        assert job["last_result"] is None
        assert job["username"] is None
        assert job["email"] is None
    assert page["data"][0]["user_id"] is None
    assert page["data"][1]["user_id"] == scheduled_jobs[2].user_id
    assert "private-scheduler-payload" not in response.text
    assert "private-scheduler-lease" not in response.text

    response = await http_client.get(
        "/scheduler/api/v1",
        params={"search": prefix, "limit": 2, "offset": 2},
        headers=headers,
    )
    assert response.json()["total"] == 3
    assert [job["scope"] for job in response.json()["data"]] == ["core"]

    response = await http_client.get(
        "/scheduler/api/v1",
        params={"search": prefix, "sortby": "next_run_at", "direction": "desc"},
        headers=headers,
    )
    assert [job["scope"] for job in response.json()["data"]] == [
        "core",
        "user",
        "extension",
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "username,email",
    [
        ("scheduler_owner", "scheduler@example.com"),
        (None, "scheduler@example.com"),
        (None, None),
    ],
)
async def test_scheduler_overview_returns_user_identity(
    http_client, superuser_token, scheduled_jobs, username, email
):
    account = await create_account(
        Account(id=uuid4().hex, username=username, email=email)
    )
    job = scheduled_jobs[2].model_copy(
        update={"id": f"{scheduled_jobs[2].id}-account", "user_id": account.id}
    )
    await crud.save_scheduled_job(job)
    try:
        response = await http_client.get(
            "/scheduler/api/v1",
            params={"namespace": job.namespace, "user_id": job.user_id},
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1
        summary = response.json()["data"][0]
        assert summary["user_id"] == job.user_id
        assert summary["username"] == username
        assert summary["email"] == email
    finally:
        await crud.delete_scheduled_job(
            job.id, job.namespace, job.user_id, int(time.time())
        )
        await delete_account(account.id)


@pytest.mark.anyio
async def test_scheduler_overview_partial_user_filter_paginates(
    http_client, superuser_token, scheduled_jobs
):
    job = scheduled_jobs[2]
    second = job.model_copy(update={"id": f"{job.id}-second"})
    other = job.model_copy(update={"id": f"{job.id}-other", "user_id": "another-owner"})
    await crud.save_scheduled_job(second)
    await crud.save_scheduled_job(other)
    headers = {"Authorization": f"Bearer {superuser_token}"}
    try:
        for fragment in ["private", "scheduler"]:
            ids = []
            for offset in range(3):
                response = await http_client.get(
                    "/scheduler/api/v1",
                    params={
                        "namespace": job.namespace,
                        "user_id[like]": fragment,
                        "enabled": "false",
                        "limit": 1,
                        "offset": offset,
                    },
                    headers=headers,
                )
                assert response.status_code == 200
                page = response.json()
                assert page["total"] == 2
                assert len(page["data"]) == (1 if offset < 2 else 0)
                ids.extend(entry["id"] for entry in page["data"])
            assert set(ids) == {job.id, second.id}
        for fragment in ["missing-owner", "' OR 1=1 --"]:
            response = await http_client.get(
                "/scheduler/api/v1",
                params={"namespace": job.namespace, "user_id[like]": fragment},
                headers=headers,
            )
            assert response.status_code == 200
            assert response.json() == {"data": [], "total": 0}
    finally:
        for added in [second, other]:
            await crud.delete_scheduled_job(
                added.id, added.namespace, added.user_id, int(time.time())
            )


@pytest.mark.anyio
@pytest.mark.parametrize("job_index", [1, 2])
async def test_scheduler_crud_preserves_owner_scope(scheduled_jobs, job_index):
    job = scheduled_jobs[job_index]
    page = await crud.get_scheduled_jobs_paginated(job.namespace, job.user_id)
    assert [entry.id for entry in page.data] == [job.id]
    assert page.total == 1
    page = await crud.get_scheduled_jobs_paginated(job.namespace, "another-owner")
    assert page.data == []
    assert page.total == 0

    # Let the fixture's lease expire so only ownership can prevent deletion.
    now = int(time.time()) + 120
    other_owner = None if job.user_id else scheduled_jobs[2].user_id
    assert not await crud.delete_scheduled_job(job.id, job.namespace, other_owner, now)
    assert not await crud.delete_scheduled_job(
        job.id, f"{job.namespace}-other", job.user_id, now
    )
    assert await crud.delete_scheduled_job(job.id, job.namespace, job.user_id, now)
    page = await crud.get_scheduled_jobs_paginated(job.namespace, job.user_id)
    assert page.data == []
    assert page.total == 0


@pytest.mark.anyio
@pytest.mark.parametrize("job_index", [1, 2])
async def test_scheduler_crud_pagination_counts_only_owner_jobs(
    scheduled_jobs, job_index
):
    job = scheduled_jobs[job_index]
    second = job.model_copy(update={"id": f"{job.id}-second"})
    await crud.save_scheduled_job(second)
    try:
        for offset, expected_ids in [(0, [job.id]), (1, [second.id]), (2, [])]:
            page = await crud.get_scheduled_jobs_paginated(
                job.namespace, job.user_id, limit=1, offset=offset
            )
            assert [entry.id for entry in page.data] == expected_ids
            assert page.total == 2
    finally:
        await crud.delete_scheduled_job(
            second.id, second.namespace, second.user_id, int(time.time())
        )


@pytest.mark.anyio
async def test_scheduler_overview_filters_and_lists_sources(
    http_client, superuser_token, scheduled_jobs
):
    namespace = scheduled_jobs[1].namespace
    headers = {"Authorization": f"Bearer {superuser_token}"}
    for enabled, job in [(True, scheduled_jobs[1]), (False, scheduled_jobs[2])]:
        response = await http_client.get(
            "/scheduler/api/v1",
            params={"namespace": namespace, "enabled": str(enabled).lower()},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["data"][0]["id"] == job.id

    response = await http_client.get(
        "/scheduler/api/v1",
        params={"namespace": namespace, "scope": "user", "search": "CHECK_ALERTS"},
        headers=headers,
    )
    assert response.json()["total"] == 1
    assert response.json()["data"][0]["id"] == scheduled_jobs[2].id

    response = await http_client.get("/scheduler/api/v1/sources", headers=headers)
    assert response.status_code == 200
    assert response.json().count(namespace) == 1
    assert "core" in response.json()

    response = await http_client.get(
        "/scheduler/api/v1", params={"namespace": "' OR 1=1 --"}, headers=headers
    )
    assert response.json() == {"data": [], "total": 0}


@pytest.mark.anyio
@pytest.mark.parametrize("params", [{"limit": -1}, {"limit": 1001}, {"offset": -1}])
@pytest.mark.parametrize("path", ["/scheduler/api/v1", "/scheduler/api/v1/runs"])
async def test_scheduler_overview_rejects_invalid_pagination(
    http_client, superuser_token, params, path
):
    response = await http_client.get(
        path,
        params=params,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_scheduler_history_filters_paginates_and_survives_deletion(
    http_client, superuser_token, scheduled_jobs
):
    job = await crud.get_scheduled_job(scheduled_jobs[1].id)
    assert job
    now = time.time()
    first = await crud.create_scheduled_job_run(job, now)
    await crud.finish_scheduled_job_run(
        first.id, "failed", now + 0.25, "Scheduled callback failed."
    )
    latest = await crud.create_scheduled_job_run(job, now + 1)
    await crud.finish_scheduled_job_run(latest.id, "succeeded", now + 1.5)
    headers = {"Authorization": f"Bearer {superuser_token}"}
    params = {"job_id": job.id, "namespace": job.namespace, "limit": 1}

    response = await http_client.get(
        "/scheduler/api/v1/runs", params=params, headers=headers
    )
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 2
    assert page["data"] == [
        latest.model_copy(
            update={"status": "succeeded", "finished_at": now + 1.5}
        ).model_dump()
    ]
    assert "private-scheduler" not in response.text
    assert not {"lease_token", "user_id", "payload_json"} & page["data"][0].keys()

    response = await http_client.get(
        "/scheduler/api/v1/runs", params={**params, "offset": 1}, headers=headers
    )
    assert response.json()["data"][0]["id"] == first.id
    response = await http_client.get(
        "/scheduler/api/v1/runs", params={**params, "status": "failed"}, headers=headers
    )
    assert response.json()["total"] == 1
    assert response.json()["data"][0]["id"] == first.id
    response = await http_client.get(
        "/scheduler/api/v1/runs",
        params={**params, "namespace": "core"},
        headers=headers,
    )
    assert response.json() == {"data": [], "total": 0}

    response = await http_client.get(
        "/scheduler/api/v1", params={"search": job.id}, headers=headers
    )
    summary = response.json()["data"][0]
    assert summary["last_run_at"] == latest.started_at
    assert summary["last_result"] == "succeeded"

    await crud.finish_scheduled_job(job, int(now) + 60)
    assert await crud.delete_scheduled_job(job.id, job.namespace, job.user_id, int(now))
    response = await http_client.get(
        "/scheduler/api/v1/runs", params={"search": job.id.upper()}, headers=headers
    )
    assert response.json()["total"] == 2
    assert {run["job_id"] for run in response.json()["data"]} == {job.id}


@pytest.mark.anyio
async def test_scheduler_history_filters_user_after_job_deletion(
    http_client, superuser_token, scheduled_jobs
):
    now = int(time.time())
    owned_runs = []
    for index, user_id in enumerate(("alice", "alice", "bob", None)):
        job = await crud.save_scheduled_job(
            scheduled_jobs[1].model_copy(
                update={"id": f"{scheduled_jobs[1].id}-{index}", "user_id": user_id}
            )
        )
        claimed = await crud.claim_scheduled_job(
            job.id, uuid4().hex, now + 60, now + 120
        )
        assert claimed
        run = await crud.create_scheduled_job_run(claimed, now + index)
        status = "failed" if index == 0 else "succeeded"
        await crud.finish_scheduled_job_run(run.id, status, now + index + 0.5)
        await crud.finish_scheduled_job(claimed, now + 180)
        assert await crud.delete_scheduled_job(job.id, job.namespace, user_id, now)
        if user_id == "alice":
            owned_runs.append(run)

    headers = {"Authorization": f"Bearer {superuser_token}"}
    params = {"namespace": scheduled_jobs[1].namespace, "user_id": "alice", "limit": 1}
    response = await http_client.get(
        "/scheduler/api/v1/runs", params=params, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["data"][0]["id"] == owned_runs[1].id
    assert "user_id" not in response.json()["data"][0]

    response = await http_client.get(
        "/scheduler/api/v1/runs", params={**params, "offset": 1}, headers=headers
    )
    assert response.json()["data"][0]["id"] == owned_runs[0].id
    response = await http_client.get(
        "/scheduler/api/v1/runs",
        params={**params, "job_id": owned_runs[0].job_id, "status": "failed"},
        headers=headers,
    )
    assert response.json()["total"] == 1
    assert response.json()["data"][0]["id"] == owned_runs[0].id
    response = await http_client.get(
        "/scheduler/api/v1/runs",
        params={"namespace": scheduled_jobs[1].namespace},
        headers=headers,
    )
    assert response.json()["total"] == 4


@pytest.mark.anyio
@pytest.mark.parametrize("role", ["anonymous", "user", "admin", "superuser"])
async def test_scheduler_enabled_setting_updates_live_and_persists(
    http_client, user_headers_from, admin_user, superuser_token, settings, role
):
    headers = user_headers_from if role == "user" else {}
    if role == "superuser":
        headers = {"Authorization": f"Bearer {superuser_token}"}
    elif role == "admin":
        response = await http_client.put(
            "/admin/api/v1/settings",
            json={"lnbits_admin_users": [admin_user.id]},
            headers={"Authorization": f"Bearer {superuser_token}"},
        )
        assert response.status_code == 200
        login = await http_client.post(
            "/api/v1/auth",
            json={"username": admin_user.username, "password": "secret1234"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    field = "lnbits_scheduler_enabled"
    for enabled in (False, True):
        response = await http_client.put(
            "/admin/api/v1/settings", json={field: enabled}, headers=headers
        )
        if role in {"anonymous", "user"}:
            assert response.status_code == (401 if role == "anonymous" else 403)
            assert settings.lnbits_scheduler_enabled is True
            continue
        assert response.status_code == 200
        assert settings.lnbits_scheduler_enabled is enabled
        stored = await get_settings_field(field)
        assert stored and stored.value is enabled
        response = await http_client.get("/admin/api/v1/settings", headers=headers)
        assert response.status_code == 200
        assert response.json()[field] is enabled


@pytest.mark.anyio
@pytest.mark.parametrize(
    "field",
    [
        "lnbits_scheduler_history_retention_days",
        "lnbits_scheduler_history_failed_retention_days",
        "lnbits_scheduler_history_max_runs_per_user",
        "lnbits_scheduler_history_max_runs_per_extension",
    ],
)
async def test_scheduler_history_retention_settings(
    http_client, superuser_token, settings, field
):
    headers = {"Authorization": f"Bearer {superuser_token}"}
    response = await http_client.put(
        "/admin/api/v1/settings", json={field: 30}, headers=headers
    )
    assert response.status_code == 200
    assert getattr(settings, field) == 30
    stored = await get_settings_field(field)
    assert stored and stored.value == 30
    response = await http_client.get("/admin/api/v1/settings", headers=headers)
    assert response.json()[field] == 30
    response = await http_client.put(
        "/admin/api/v1/settings", json={field: 0}, headers=headers
    )
    assert response.status_code == 400
    assert getattr(settings, field) == 30
