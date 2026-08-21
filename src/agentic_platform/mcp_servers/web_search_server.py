"""MCP server exposing web research tools: `web_search` and `fetch_url`.

Security note (SSRF): `fetch_url` accepts a user/model-influenced URL, so
before fetching we resolve the hostname and reject requests to loopback,
private, link-local, or otherwise non-public IP ranges. This mitigates the
classic "agent fetches http://169.254.169.254/ (cloud metadata)" SSRF vector.
"""
from __future__ import annotations

import ipaddress
import os
import socket
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from mcp.server import MCPServer

mcp = MCPServer("web-research")

_USER_AGENT = "agentic-research-platform/0.1 (+https://github.com/)"
_MAX_CHARS = 4000


def _is_public_host(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http/https URLs are allowed.")
    if not parsed.hostname:
        raise ValueError("URL is missing a hostname.")
    if not _is_public_host(parsed.hostname):
        raise ValueError("Refusing to fetch a non-public / internal network address.")
    return url


@mcp.tool()
def fetch_url(url: str) -> str:
    """Fetch a web page and return its main text content (truncated), for citing sources."""
    try:
        _validate_url(url)
        with httpx.Client(follow_redirects=True, timeout=10.0, headers={"User-Agent": _USER_AGENT}) as client:
            response = client.get(url)
            # Re-validate after redirects in case the final host differs from the requested one.
            _validate_url(str(response.url))
            response.raise_for_status()
    except (httpx.HTTPError, ValueError) as exc:
        return f"Error fetching {url}: {exc}"

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    return text[:_MAX_CHARS] or "(page had no extractable text)"


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web and return numbered results with title, URL, and snippet."""
    tavily_key = os.getenv("TAVILY_API_KEY")
    try:
        if tavily_key:
            return _search_tavily(query, max_results, tavily_key)
        return _search_duckduckgo(query, max_results)
    except httpx.HTTPError as exc:
        return f"Search failed: {exc}"


def _search_tavily(query: str, max_results: int, api_key: str) -> str:
    with httpx.Client(timeout=10.0) as client:
        response = client.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": max_results},
        )
        response.raise_for_status()
        results = response.json().get("results", [])
    return _format_results((r.get("title", ""), r.get("url", ""), r.get("content", "")) for r in results)


def _search_duckduckgo(query: str, max_results: int) -> str:
    with httpx.Client(timeout=10.0, headers={"User-Agent": _USER_AGENT}) as client:
        response = client.post("https://html.duckduckgo.com/html/", data={"q": query})
        response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    rows = []
    for result in soup.select(".result")[:max_results]:
        link = result.select_one(".result__a")
        snippet = result.select_one(".result__snippet")
        if not link:
            continue
        rows.append((link.get_text(strip=True), link.get("href", ""), snippet.get_text(strip=True) if snippet else ""))
    return _format_results(rows)


def _format_results(rows) -> str:
    lines = [f"{i}. {title}\n   {url}\n   {snippet}" for i, (title, url, snippet) in enumerate(rows, start=1)]
    return "\n".join(lines) if lines else "No results found."


if __name__ == "__main__":
    mcp.run()
