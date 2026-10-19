"""The MCP server: the platform's actions as tools for an AI agent (Phase 4, decision 0013).

Claude Code, the PoC's agent (decision 0003), starts it from the project's ``.mcp.json``. The agent
follows ``docs/agent-procedure.md``.
"""

from moonwalkers.workspace import Workspace

from .server import create_server, default_data_dir

__all__ = ["Workspace", "create_server", "default_data_dir"]
