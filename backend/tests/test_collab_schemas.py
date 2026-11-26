"""Unit tests for Knowledge Base, Team Chat and Tasks schemas."""

import pytest
from pydantic import ValidationError

from app.modules.collab.schemas import (
    KnowledgeDocCreateRequest,
    TeamChannelCreateRequest,
    TeamTaskCreateRequest,
)


def test_knowledge_doc_normalizes_and_deduplicates_tags() -> None:
    doc = KnowledgeDocCreateRequest(
        title="Onboarding Architecture",
        content="# Welcome",
        tags=["Backend", " backend ", "Docker", ""],
    )
    assert doc.tags == ["backend", "docker"]


def test_team_channel_slug_validation() -> None:
    valid = TeamChannelCreateRequest(name="Backend Core", slug="backend-core")
    assert valid.slug == "backend-core"

    for bad_slug in ["A", "-bad", "bad-", "Bad_Slug"]:
        with pytest.raises(ValidationError):
            TeamChannelCreateRequest(name="Bad", slug=bad_slug)


def test_team_task_defaults() -> None:
    task = TeamTaskCreateRequest(title="Revisar aislamiento de red")
    assert task.priority == "medium"
