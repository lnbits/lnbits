from datetime import datetime, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient

from lnbits.core.crud.audit import create_audit_entry
from lnbits.core.models import AuditEntry


@pytest.mark.anyio
async def test_audit_api_requires_admin(client: AsyncClient, user_headers_from):
    response = await client.get("/audit/api/v1", headers=user_headers_from)
    assert response.status_code == 403


@pytest.mark.anyio
async def test_audit_api_returns_entries_and_stats(
    client: AsyncClient,
    superuser_token: str,
):
    component = f"audit_component_{uuid4().hex[:8]}"
    await create_audit_entry(
        AuditEntry(
            component=component,
            ip_address="127.0.0.1",
            user_id=uuid4().hex,
            path="/api/v1/test",
            request_method="GET",
            response_code="200",
            duration=0.12,
            created_at=datetime.now(timezone.utc),
        )
    )
    await create_audit_entry(
        AuditEntry(
            component=component,
            ip_address="127.0.0.2",
            user_id=uuid4().hex,
            path="/api/v1/test",
            request_method="POST",
            response_code="400",
            duration=2.5,
            created_at=datetime.now(timezone.utc),
        )
    )
    headers = {"Authorization": f"Bearer {superuser_token}"}

    page = await client.get(f"/audit/api/v1?component={component}", headers=headers)
    assert page.status_code == 200
    page_data = page.json()
    assert page_data["total"] == 2
    assert {item["request_method"] for item in page_data["data"]} == {"GET", "POST"}

    stats = await client.get(
        f"/audit/api/v1/stats?component={component}",
        headers=headers,
    )
    assert stats.status_code == 200
    payload = stats.json()
    assert {item["field"] for item in payload["request_method"]} == {"GET", "POST"}
    assert {item["field"] for item in payload["response_code"]} == {"200", "400"}
    assert payload["component"][0]["field"] == component
    assert payload["long_duration"][0]["field"] == "/api/v1/test"
