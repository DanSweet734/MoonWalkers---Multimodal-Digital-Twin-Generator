# 0003 - For the PoC, Claude Code is the agent, through our own MCP tools

- **Status:** accepted
- **Date:** 2026-10-16
- **Decided by:** team

## Context
The aim is for an AI assistant or agent to drive the platform (create, edit, submit twins), as cheaply as
possible. Daniel has the Claude Pro plan, which includes Claude Code, with usage limits shared with
claude.ai that reset every five hours
(https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan).
Claude Code can connect to local stdio MCP servers, including project-scoped servers in `.mcp.json`, and
asks for approval before using project-scoped servers in interactive sessions
(https://code.claude.com/docs/en/mcp).

## Options considered
1. Claude Code (subscription) as the agent, driving MCP tools our backend exposes. No API cost.
2. An agent loop inside our backend calling a model API. Per-call cost; needs an API key.
3. A local open model. No API cost, but setup and quality are unknown.

## Decision
Option 1 for the PoC. The platform's actions are MCP tools, so a different agent (option 2 or 3) can drive
the same tools later. The AI model and agent runtime for the final product remain to be researched.

## Consequences
Runs are interactive and count against Pro usage limits. The support article says Pro can use Sonnet but
not Opus in Claude Code (may be dated; check `/model`). Whether unattended `claude -p` runs stay on the
subscription is not confirmed, so we do not rely on them.
