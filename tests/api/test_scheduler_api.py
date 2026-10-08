import time
from uuid import uuid4

import pytest

from lnbits.core.crud import scheduler as crud
from lnbits.core.models.scheduler import ScheduledJob


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
@pytest.mark.parametrize("path", ["/scheduler/api/v1", "/scheduler/api/v1/sources"])
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


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/scheduler/api/v1", "/scheduler/api/v1/sources"])
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
            "cron_expression",
            "timezone",
            "enabled",
            "next_run_at",
        }
    assert "private-scheduler" not in response.text

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
async def test_scheduler_overview_rejects_invalid_pagination(
    http_client, superuser_token, params
):
    response = await http_client.get(
        "/scheduler/api/v1",
        params=params,
        headers={"Authorization": f"Bearer {superuser_token}"},
    )
    assert response.status_code == 400
