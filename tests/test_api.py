"""Tests for the FastAPI layer, with the agent team mocked out (no API key / network needed)."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import agentic_platform.api.main as main
from agentic_platform.agents.orchestrator import OrchestrationResult, Step


@pytest.fixture
def client(monkeypatch):
    # Enter the TestClient context first so the real (no-API-key) lifespan startup runs and
    # settles _team=None, *then* override it - otherwise startup would clobber our monkeypatch.
    with TestClient(main.app) as test_client:
        monkeypatch.setattr(main, "_team", object())  # any non-None sentinel marks the team "ready"
        yield test_client


def test_health_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "agent_team_ready": True}


def test_chat_returns_answer_and_trace(client, monkeypatch):
    fake_result = OrchestrationResult(
        final_answer="42",
        steps=[Step(agent="Coder", instruction="compute 6*7", output="42")],
    )
    monkeypatch.setattr(main, "run_task", AsyncMock(return_value=fake_result))

    response = client.post("/chat", json={"message": "what is 6 times 7?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "42"
    assert body["steps"][0]["agent"] == "Coder"


def test_chat_rejects_empty_message(client):
    response = client.post("/chat", json={"message": ""})
    assert response.status_code == 422


def test_chat_503_when_team_not_ready(client, monkeypatch):
    monkeypatch.setattr(main, "_team", None)
    response = client.post("/chat", json={"message": "hello"})
    assert response.status_code == 503
