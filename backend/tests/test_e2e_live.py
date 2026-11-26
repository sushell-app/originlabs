"""Live end-to-end API tests against real PostgreSQL and Redis services."""

import os

import httpx
import pytest

from app.core.database import engine
from app.main import app

pytestmark = pytest.mark.skipif(
    os.getenv("ORIGINLABS_RUN_E2E") != "1",
    reason="Live E2E requires PostgreSQL and Redis",
)


async def test_full_api_lifecycle_e2e() -> None:
    """Verify setup, auth, forward_auth, projects, collab, audit, updates and logout."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        health_resp = await client.get("/api/v1/health")
        assert health_resp.status_code == 200
        health = health_resp.json()
        assert health["status"] == "ok"
        assert health["services"]["database"]["ok"] is True
        assert health["services"]["redis"]["ok"] is True

        meta_resp = await client.get("/api/v1/meta")
        assert meta_resp.status_code == 200
        assert meta_resp.json()["setup_required"] is True

        setup_resp = await client.post(
            "/api/v1/auth/setup",
            json={
                "full_name": "CI Admin",
                "email": "ci-admin@example.com",
                "password": "SuperSecure123!",
                "organization_name": "Sushell CI",
                "organization_slug": "sushell-ci",
            },
        )
        assert setup_resp.status_code == 201
        org_id = setup_resp.json()["organizations"][0]["id"]

        me_resp = await client.get("/api/v1/auth/me")
        assert me_resp.status_code == 200
        assert me_resp.json()["user"]["email"] == "ci-admin@example.com"

        fwd_resp = await client.get("/api/v1/internal/forward-auth")
        assert fwd_resp.status_code == 200
        assert fwd_resp.headers.get("x-originlabs-is-admin") == "true"

        proj_resp = await client.post(
            f"/api/v1/organizations/{org_id}/projects",
            json={
                "name": "Core API",
                "slug": "core-api",
                "description": "CI E2E project",
                "git_provider": "internal",
                "default_branch": "main",
                "default_workspace_class": "standard",
            },
        )
        assert proj_resp.status_code == 201
        project_id = proj_resp.json()["id"]

        env_resp = await client.put(
            f"/api/v1/organizations/{org_id}/projects/{project_id}/env-vars",
            json={"key": "API_SECRET", "value": "ci-secret-value", "is_secret": True},
        )
        assert env_resp.status_code == 200
        assert env_resp.json()["value"] is None

        folder_resp = await client.post(
            f"/api/v1/organizations/{org_id}/knowledge/folders",
            json={"name": "Onboarding", "slug": "onboarding"},
        )
        assert folder_resp.status_code == 201
        folder_id = folder_resp.json()["id"]

        doc_resp = await client.post(
            f"/api/v1/organizations/{org_id}/knowledge/docs",
            json={
                "title": "Quickstart",
                "content": "# Ready",
                "folder_id": folder_id,
                "tags": ["Docs", "ci"],
            },
        )
        assert doc_resp.status_code == 201
        assert doc_resp.json()["tags"] == ["docs", "ci"]

        channels_resp = await client.get(f"/api/v1/organizations/{org_id}/chat/channels")
        assert channels_resp.status_code == 200
        channels = channels_resp.json()
        assert len(channels) >= 1
        channel_id = channels[0]["id"]

        msg_resp = await client.post(
            f"/api/v1/organizations/{org_id}/chat/channels/{channel_id}/messages",
            json={"body": "Deploy verified", "is_private_note": False},
        )
        assert msg_resp.status_code == 201
        msg_id = msg_resp.json()["id"]

        task_resp = await client.post(
            f"/api/v1/organizations/{org_id}/tasks",
            json={
                "title": "Verify release",
                "priority": "high",
                "source_message_id": msg_id,
            },
        )
        assert task_resp.status_code == 201
        task_id = task_resp.json()["id"]

        patch_task = await client.patch(
            f"/api/v1/organizations/{org_id}/tasks/{task_id}",
            json={"status": "in_progress"},
        )
        assert patch_task.status_code == 200
        assert patch_task.json()["status"] == "in_progress"

        audit_resp = await client.get(f"/api/v1/audit?organization_id={org_id}")
        assert audit_resp.status_code == 200
        assert len(audit_resp.json()) >= 1

        ws_resp = await client.post(
            f"/api/v1/organizations/{org_id}/workspaces",
            json={
                "project_id": project_id,
                "name": "API Sandbox",
                "slug": "api-sandbox",
                "workspace_class": "light",
                "idle_timeout_minutes": 45,
                "auto_start": False,
            },
        )
        assert ws_resp.status_code == 201
        ws_id = ws_resp.json()["id"]
        assert (await client.get(f"/api/v1/organizations/{org_id}/workspaces")).status_code == 200
        assert (
            await client.delete(f"/api/v1/organizations/{org_id}/workspaces/{ws_id}")
        ).status_code == 204

        metrics_resp = await client.get("/api/v1/system/metrics")
        assert metrics_resp.status_code == 200
        assert len(metrics_resp.json()["admission"]) == 3

        backup_cfg_resp = await client.get("/api/v1/system/backups/config")
        assert backup_cfg_resp.status_code == 200
        backup_patch = await client.patch(
            "/api/v1/system/backups/config",
            json={"provider": "local", "repository": "/var/backups/ci-test", "enabled": True},
        )
        assert backup_patch.status_code == 200
        assert backup_patch.json()["repository"] == "/var/backups/ci-test"
        assert (await client.get("/api/v1/system/backups/snapshots")).status_code == 200

        updates_resp = await client.get("/api/v1/system/updates")
        assert updates_resp.status_code == 200
        notif_resp = await client.get("/api/v1/system/notifications")
        assert notif_resp.status_code == 200

        logout_resp = await client.post("/api/v1/auth/logout")
        assert logout_resp.status_code == 204
        assert (await client.get("/api/v1/auth/me")).status_code == 401

    await engine.dispose()
