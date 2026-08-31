# solidworks-mcp-example

A throwaway project that exists only to point an MCP client at
[`../solidworks-mcp`](../solidworks-mcp) and drive it. Nothing here is imported by the
server; it is config, a preflight script, and a scratch directory the server is allowed
to write into.

## Prerequisites

The server must already be installed. From a shell:

```powershell
cd ..\solidworks-mcp
uv venv
uv pip install -e .
```

SOLIDWORKS itself is only needed for the modelling tools. The handshake and every
read-only diagnostic answer with SOLIDWORKS stopped.

## Preflight

Run this before wiring up a client, so a failure tells you *which* layer broke:

```powershell
powershell -ExecutionPolicy Bypass -File .\smoke.ps1
```

It checks three things in order — that the exact command line from `.mcp.json` launches,
that a real MCP handshake returns tool schemas, and what `--doctor` says about the
install. Add `-SkipDoctor` to stop before the step that looks at the machine. If your
checkout lives elsewhere, pass `-ServerDir C:\path\to\solidworks-mcp`.

## Wiring up a client

**Claude Code** picks up [`.mcp.json`](.mcp.json) automatically — just start it with this
folder as the working directory and approve the server when prompted. `/mcp` shows
whether it connected.

**Claude Desktop** — merge the `mcpServers` block from `.mcp.json` into
`%APPDATA%\Claude\claude_desktop_config.json`, then restart the app.

**VS Code** — copy the same block into `.vscode/mcp.json` under a `servers` key.

Any client works; the shape is always the same:

```json
{
  "command": "uv",
  "args": ["run", "--directory", "C:/projects/cad-mcp-comparisons/solidworks-mcp", "solidworks-mcp"],
  "env": { "SWMCP_ALLOWED_ROOTS": "C:/projects/cad-mcp-comparisons/solidworks-mcp-example/work" }
}
```

All four paths in `.mcp.json` are absolute. If you move either folder, update them —
`uv run --directory` sets the server's working directory, so a relative path would
resolve against the *server* checkout, not this one.

## What the settings do here

| Variable | Value here | Why |
|---|---|---|
| `SWMCP_ALLOWED_ROOTS` | `./work` | The only place the server may write. Unset means **nothing** can be written anywhere — the guard fails closed, so this is the one setting you cannot skip. |
| `SWMCP_TOOL_TIER` | `all` | Registers all 113 operations, because the point of this project is to poke at them (a client sees 114 tools, counting `sw_search_tools`). Drop to `core` for a realistic list of 89; `sw_search_tools` searches the whole catalog either way and tells you which tier a hidden operation needs. |
| `SWMCP_AUDIT_PATH` | `./.mcp-audit/audit.jsonl` | Keeps the append-only write log with this project instead of in the server checkout. |
| `SWMCP_CHECKPOINT_DIR` | `./.checkpoints` | Snapshots land here rather than beside each document, so `work/` stays readable. |

Deliberately left at their defaults: `SWMCP_ENABLE_LOWLEVEL_WRITE` (off, so
`sw_api_invoke_write` stays unavailable) and `SWMCP_ALLOW_UNCHECKPOINTED` (off, so a
destructive edit to a document that cannot be snapshotted is refused). Turn either on
only when you are specifically testing that path. The full table is in the server's
README.

## Things to try, in order

Start read-only, with SOLIDWORKS closed:

1. *"Run sw_health and tell me whether SOLIDWORKS is installed and running."*
2. *"What does sw_capabilities report for launch_mode?"* — `com_activation` means the
   server can start SOLIDWORKS itself; `platform_manual` means you have to launch it
   from the 3DEXPERIENCE shortcut first.
3. *"Search the tool catalog for anything about fillets."*
4. *"Explain error code SOLIDWORKS_NOT_RUNNING."*

Then start SOLIDWORKS and try a mutation:

5. *"Connect to SOLIDWORKS, make a new part, sketch a 50 mm square on the front plane
   and extrude it 10 mm."* Read the `verification` block in each result — an operation
   is done when the read-back says so, not when the call returned.
6. *"Save that part into the work folder and export it as a STEP file."* The save
   succeeds only because `work/` is inside `SWMCP_ALLOWED_ROOTS`; ask it to write to
   `C:\Temp` instead and watch the path guard refuse.
7. *"Show me the last few audit entries."* Every write is in
   `.mcp-audit/audit.jsonl`.
8. *"Delete the extrude."* This is destructive, so it needs `confirm=true` and takes a
   checkpoint first — you should see one appear under `.checkpoints/`.

## When it does not connect

| Symptom | Cause |
|---|---|
| Client shows the server as failed, no output | `uv` not on PATH for the client's environment, or the venv was never created. Run `smoke.ps1`. |
| `SOLIDWORKS_NOT_INSTALLED` | The `SldWorks.Application` ProgID is not in the registry. A repair install re-registers it. |
| `SOLIDWORKS_NOT_RUNNING` | Start SOLIDWORKS, or pass `start_if_missing: true`. Note COM cannot attach across elevation levels — if one process is elevated and the other is not, attach fails. |
| `SOLIDWORKS_PLATFORM_LAUNCH_REQUIRED` | A 3DEXPERIENCE-managed install. It cannot be started automatically; the error names the shortcut to run. Launch it, sign in, then connect. |
| `PATH_NOT_ALLOWED` | The target is outside `SWMCP_ALLOWED_ROOTS`. Working as designed. |
| A tool you expected is missing | It is above the active tier. Ask `sw_search_tools`; it reports the tier each operation needs. |

`work/`, `.checkpoints/`, and `.mcp-audit/` are gitignored — delete them freely between
runs.
