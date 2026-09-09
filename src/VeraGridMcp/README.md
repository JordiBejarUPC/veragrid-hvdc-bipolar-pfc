# VeraGridMcp

`VeraGridMcp` is the external Model Context Protocol package for VeraGrid. It
sits on top of `VeraGrid` and imports `VeraGridEngine` directly. It does not
use the VeraGrid REST server package, and it does not contain local chat or
model-provider plumbing.

The MCP layer uses `FastMCP` from the `mcp<2` SDK family.

The package exposes a stdio MCP server:

```bash
python -m VeraGridMcp.mcp_server
```

The package also installs a console entry point:

```bash
veragridmcp
```

## Package Direction

The dependency direction is:

```text
VeraGridEngine
    ^
    |
VeraGrid
    ^
    |
VeraGridMcp
```

`VeraGridMcp` depends on matching `VeraGrid` and `VeraGridEngine` versions.
`VeraGrid` does not depend on `VeraGridMcp`.

## Install From This Repository

From the repository root:

```bash
cd /home/santi/Git/eRoots/VeraGrid
python -m pip install -e src/VeraGridEngine
python -m pip install -e src/VeraGrid
python -m pip install -e src/VeraGridMcp
```

For direct development checks without installing:

```bash
cd /home/santi/Git/eRoots/VeraGrid
PYTHONPATH=src python -m VeraGridMcp.mcp_server
```

## Install From PyPI

After publishing matching versions:

```bash
python -m pip install VeraGridMcp
```

## Available MCP Tools

| Tool | Purpose |
| --- | --- |
| `veragrid_status` | Checks that the MCP server is reachable. |
| `veragrid_stack_status` | Reports the available `VeraGrid` and `VeraGridEngine` versions. |

## Quick Local Test

Run this from the repository root:

```bash
PYTHONPATH=src python - <<'PY'
import json
import subprocess
import sys


def encode(payload):
    raw = json.dumps(payload).encode("utf-8")
    return b"Content-Length: " + str(len(raw)).encode("ascii") + b"\r\n\r\n" + raw


process = subprocess.Popen(
    [sys.executable, "-m", "VeraGridMcp.mcp_server"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    cwd="/home/santi/Git/eRoots/VeraGrid/src",
)

initialize_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "vera-check", "version": "1.0"},
    },
}

initialized_request = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
}

request = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {},
}

process.stdin.write(encode(initialize_request))
process.stdin.flush()
header = process.stdout.readline()
process.stdout.readline()
length = int(header.decode("ascii").split(":", 1)[1].strip())
print(process.stdout.read(length).decode("utf-8"))

process.stdin.write(encode(initialized_request))
process.stdin.flush()
process.stdin.write(encode(request))
process.stdin.flush()
header = process.stdout.readline()
process.stdout.readline()
length = int(header.decode("ascii").split(":", 1)[1].strip())
print(process.stdout.read(length).decode("utf-8"))
process.terminate()
process.wait(timeout=1.0)
PY
```

Expected tools:

```text
veragrid_status
veragrid_stack_status
```

## Use From Codex

Add an MCP server entry to the Codex config file:

```bash
nano /home/santi/.codex/config.toml
```

For this development checkout:

```toml
[mcp_servers.veragrid]
command = "/home/santi/Git/eRoots/VeraGrid/.venv/bin/python"
args = ["-m", "VeraGridMcp.mcp_server"]
cwd = "/home/santi/Git/eRoots/VeraGrid/src"
```

If `VeraGridMcp` is installed in the Python environment used by Codex:

```toml
[mcp_servers.veragrid]
command = "python"
args = ["-m", "VeraGridMcp.mcp_server"]
```

Restart Codex after editing the config. In a new Codex session, ask:

```text
Are you connected to the VeraGrid MCP server? Use veragrid_stack_status.
```

Codex should call `veragrid_stack_status` and report the installed `VeraGrid`
and `VeraGridEngine` versions.

## Use From Another MCP Client

Register the server as a stdio MCP server:

```json
{
  "mcpServers": {
    "veragrid": {
      "command": "python",
      "args": ["-m", "VeraGridMcp.mcp_server"],
      "cwd": "/home/santi/Git/eRoots/VeraGrid/src"
    }
  }
}
```

For an installed package, omit `cwd` unless the client requires it.

## Knowledge Assets

The static knowledge files live in:

```text
src/VeraGridMcp/knowledge
```

Regenerate them with:

```bash
cd /home/santi/Git/eRoots/VeraGrid
PYTHONPATH=src python -m VeraGridMcp.generate_knowledge_assets
```

The VeraGrid retrieval layer loads them as package resources from:

```text
VeraGridMcp.knowledge
```

## Publishing

The repository publishing script includes `VeraGridMcp`:

```bash
cd /home/santi/Git/eRoots/VeraGrid/src
python upload_to_pypi.py
```

That script performs real uploads. Run it only when versions and PyPI
credentials are ready.

For `VeraGridMcp`, the relevant publish order is:

```text
VeraGridEngine
VeraGrid
VeraGridMcp
```

## Troubleshooting

Check that the configured Python can import the package:

```bash
/home/santi/Git/eRoots/VeraGrid/.venv/bin/python -c "import VeraGridMcp"
```

Check that the server starts:

```bash
cd /home/santi/Git/eRoots/VeraGrid/src
/home/santi/Git/eRoots/VeraGrid/.venv/bin/python -m VeraGridMcp.mcp_server
```

If `veragrid_stack_status` reports a missing package, install the missing
package into the Python environment used by the MCP client.
