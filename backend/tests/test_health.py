"""Baseline unit tests for OriginLabs Core contracts and metadata endpoints."""

from fastapi.testclient import TestClient

from app.main import app
from app.modules.extensions import CommunityLicenseProvider, build_default_registry


def test_community_license_provider_defaults_to_community() -> None:
    license_info = CommunityLicenseProvider().get_license()
    assert license_info.edition == "community"
    assert license_info.valid is True
    assert license_info.features == ()


def test_default_extension_registry_includes_projects_and_workspaces() -> None:
    modules = {item.id: item for item in build_default_registry().list_all()}
    assert set(modules.keys()) == {"projects", "workspaces"}
    assert modules["projects"].kind == "core_included"
    assert modules["workspaces"].kind == "core_included"


def test_instance_meta_endpoint() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/meta")
    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "OriginLabs"
    assert payload["edition"] == "community"
    assert len(payload["modules"]) == 2
