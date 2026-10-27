# Quick setup

Requirements: Windows, Python 3.11+, [uv](https://docs.astral.sh/uv/), and SOLIDWORKS
running and signed in. Launch SOLIDWORKS yourself; the tools attach to it but cannot
start it.

## Install

```bash
cd C:/path/to/solidworks-mcp
uv venv && uv pip install -e .
uv run solidworks-mcp --doctor        # checks the install and the SOLIDWORKS session
```

Run the `uv run solidworks-mcp ...` commands below from inside the `solidworks-mcp`
folder, unless they say otherwise. Files can only be written into directories you
allow. Pick one, for example `C:/cad/work`.

## As a Python library

```python
from swmcp import SolidWorks

with SolidWorks(allowed_roots=["C:/cad/work"]) as sw:
    sw.doc_new(doc_type="part")
    sw.sketch_start(on={"standard_plane": "front"})
    sw.sketch_add_geometry(
        entities=[{"type": "rect_corner", "corner": [0, 0], "opposite": [100, 60]}]
    )
    sw.sketch_exit()
    sw.feature_extrude_boss(depth=8)
    sw.export(output_path="C:/cad/work/plate.step")
```

Run your script with `uv run python my_script.py`. To use the library from another
project, install it there with `uv pip install -e C:/path/to/solidworks-mcp`.

Each method is an operation name without the `sw_` prefix. To list or inspect
operations:

```bash
uv run solidworks-mcp tools extrude              # search
uv run solidworks-mcp describe sw_doc_new        # arguments for one operation
```

## As an agent skill

Run this from any folder:

```bash
# for every project: installs to ~/.claude/skills/solidworks
uv run --project C:/path/to/solidworks-mcp solidworks-mcp install-skill

# for one project only: run it inside that project's folder
uv run --project C:/path/to/solidworks-mcp solidworks-mcp install-skill --dest .claude/skills/solidworks
```

`--project` tells `uv` where this package is installed. A plain `uv run solidworks-mcp`
only works from inside the `solidworks-mcp` folder. Anywhere else it fails with
`program not found`. Add `--force` to update an earlier install. Claude Code then picks
up the skill automatically, and the skill already knows which Python to use.

From inside the `solidworks-mcp` folder, you can also run any single operation yourself:

```bash
uv run solidworks-mcp call sw_doc_list
```

## As an MCP server

Add this to your MCP client's configuration:

```json
{
  "mcpServers": {
    "solidworks": {
      "command": "uv",
      "args": ["run", "--directory", "C:/path/to/solidworks-mcp", "solidworks-mcp"],
      "env": { "SWMCP_ALLOWED_ROOTS": "C:/cad/work" }
    }
  }
}
```

For Claude Code, the same thing as one command:

```bash
claude mcp add solidworks -e SWMCP_ALLOWED_ROOTS=C:/cad/work -- uv run --directory C:/path/to/solidworks-mcp solidworks-mcp
```

The server shows MCP clients a core set of tools by default. Set
`SWMCP_TOOL_TIER=all` to show every operation.

More detail is in the [README](../README.md).
