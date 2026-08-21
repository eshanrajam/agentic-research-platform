"""Custom MCP (Model Context Protocol) tool servers used by the specialist agents.

Each server is a standalone stdio process (built with the official MCP Python
SDK's `MCPServer` helper) launched on demand via `MCPStdioTool`. This keeps tool
implementations decoupled from the agent orchestration layer - any MCP-
compatible client (not just this app) can use them.
"""
