# VeraGridMcp

## What this is

`VeraGridMcp` is a Model Context Protocol (MCP) server for VeraGrid.
It is a plain stdio server and does **not** include any chat/provider logic.

It exposes two tools:
- `veragrid_status`
- `veragrid_stack_status`

## 1) Install

Use the repo editables (recommended for local use):

```bash
cd /home/santi/Git/eRoots/VeraGrid
python -m pip install -e src/VeraGridEngine
python -m pip install -e src/VeraGridMcp
```

Or install from PyPI:

```bash
python -m pip install VeraGridMcp
```

## 2) Start the MCP server

```bash
veragridmcp
```

This runs the server.

`veragridmcp serve` does the same thing.

## 3) Register in clients (important)

This package adds a CLI register helper:

```bash
veragridmcp register --client codex
veragridmcp register --client claude
veragridmcp register --client cursor --cursor-scope global
veragridmcp register --client all
```

Common options:
- `--client` (`codex`, `claude`, `cursor`, `claude-code`, `cursor-project`, `cursor-global`)
- `--cursor-scope global|project` (used only when `--client cursor`)
- `--server-name` (default: `veragrid`)
- `--python` (interpreter used by MCP client)
- `--cwd` (working directory, defaults to current dir)
- `--dry-run` (preview only, does not write files)

Output paths:
- Codex → `~/.codex/config.toml`
- Claude Desktop → `claude_desktop_config.json`
- Cursor global → `~/.cursor/mcp.json`
- Cursor project → `./.cursor/mcp.json`
- Claude Code → `./.mcp.json`

## 4) Quick smoke test

Ask any connected client:
`Are you connected to the VeraGrid MCP server?`

Then call:
`veragrid_stack_status`

Expected output includes:
- `VeraGridMcp: <version>`
- `VeraGridEngine: <version>`

## 5) OpenAI/ChatGPT (publish path)

For ChatGPT custom MCP apps, this is **workspace registration**, not PyPI publishing.

You still must:
1. Enable Developer mode.
2. Register the MCP app.
3. Test in draft.
4. Publish in workspace.

ChatGPT currently expects remote MCP connections, so private/local servers usually
need a secure tunnel if not publicly reachable.

## 6) Remove this package from MCP client config

Open your client config file and delete the `veragrid` block (or run your own config overwrite manually).

## 7) Troubleshooting (fast)

- `veragridmcp` command not found: install the package in the active environment.
- Bad command path: use `--python` and `--cwd` to point to the exact Python and repo root.
- Missing version text from `veragrid_stack_status`: that means `VeraGridEngine` is not importable in the client environment.

## 8) Regenerate knowledge assets (optional)

```bash
cd /home/santi/Git/eRoots/VeraGrid
PYTHONPATH=src python -m VeraGridMcp.generate_knowledge_assets
```
