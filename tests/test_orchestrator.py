"""Tests for the orchestrator's JSON-decision parsing (no network / API keys required)."""
from __future__ import annotations

import pytest

from agentic_platform.agents.orchestrator import Step, _build_orchestrator_message, _extract_json


def test_extract_json_plain():
    assert _extract_json('{"agent": "Researcher", "instruction": "look this up"}') == {
        "agent": "Researcher",
        "instruction": "look this up",
    }


def test_extract_json_with_surrounding_prose():
    text = 'Sure, here is my decision:\n```json\n{"agent": "FINAL", "instruction": "done"}\n```\nHope that helps!'
    assert _extract_json(text) == {"agent": "FINAL", "instruction": "done"}


def test_extract_json_raises_on_no_json():
    with pytest.raises(ValueError):
        _extract_json("I don't know what to do next.")


def test_build_orchestrator_message_includes_task_and_empty_transcript():
    message = _build_orchestrator_message("Do the thing", [])
    assert "Do the thing" in message
    assert "none yet" in message


def test_build_orchestrator_message_includes_prior_steps():
    steps = [Step(agent="Researcher", instruction="find X", output="X is Y")]
    message = _build_orchestrator_message("Do the thing", steps)
    assert "[Researcher]" in message
    assert "X is Y" in message
