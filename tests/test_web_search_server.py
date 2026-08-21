"""Tests for the web-research MCP server's SSRF guard (pure functions, no network)."""
from __future__ import annotations

import pytest

from agentic_platform.mcp_servers.web_search_server import _validate_url


def test_validate_url_accepts_public_https():
    assert _validate_url("https://example.com/page") == "https://example.com/page"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "ftp://example.com/",
        "http:///no-host",
    ],
)
def test_validate_url_rejects_unsafe_targets(url):
    with pytest.raises(ValueError):
        _validate_url(url)
