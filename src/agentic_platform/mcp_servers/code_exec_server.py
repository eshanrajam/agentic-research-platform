"""MCP server exposing a sandboxed Python execution tool for the Coder agent.

Security note: arbitrary code execution is inherently high-risk (OWASP A03/A08).
This tool is disabled by default and must be explicitly opted into via
ENABLE_CODE_EXECUTION=true. Even when enabled it is a *demo-grade* sandbox
only: a subprocess with a stripped environment, a temp working directory, and
a hard timeout - it does NOT block filesystem or network access. For a
production-grade version, swap this for a real isolation boundary such as
Azure Container Apps dynamic sessions, gVisor, or Firecracker microVMs.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from mcp.server import MCPServer

mcp = MCPServer("code-exec")

_ENABLED = os.getenv("ENABLE_CODE_EXECUTION", "false").strip().lower() in {"1", "true", "yes", "on"}
_TIMEOUT_SECONDS = 10
_MAX_OUTPUT_CHARS = 4000


@mcp.tool()
def run_python(code: str) -> str:
    """Execute a short Python snippet in an isolated subprocess and return stdout/stderr."""
    if not _ENABLED:
        return (
            "Code execution is disabled in this deployment. Set ENABLE_CODE_EXECUTION=true "
            "in a trusted dev/demo environment to enable this tool."
        )

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = os.path.join(tmp_dir, "snippet.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_SECONDS,
                env={"PATH": os.environ.get("PATH", "")},  # minimal env; never forward secrets/API keys
            )
        except subprocess.TimeoutExpired:
            return f"Execution timed out after {_TIMEOUT_SECONDS} seconds."

        output = result.stdout[-_MAX_OUTPUT_CHARS:]
        if result.returncode != 0:
            output += f"\n[stderr]\n{result.stderr[-2000:]}"
        return output.strip() or "(no output)"


if __name__ == "__main__":
    mcp.run()
