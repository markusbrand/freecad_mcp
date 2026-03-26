# FreeCAD MCP + Cursor AI Setup (Linux)

This is a short, practical setup guide for running this plugin with Cursor AI on Linux, including the local fixes that were required.

## 1) Install plugin into FreeCAD Mod folder

Place the plugin at:

`~/.local/share/FreeCAD/Mod/freecad_mcp`

Note: on this machine, this path was required (not `~/.FreeCAD/Mod/...`).

## 2) Create a Python venv for MCP bridge deps

Arch-based Python is externally managed (PEP 668), so install MCP deps into a dedicated venv:

```bash
/usr/bin/python3 -m venv ~/.local/share/freecad-mcp-bridge-venv
~/.local/share/freecad-mcp-bridge-venv/bin/pip install "mcp>=1.2.0"
```

## 3) Configure Cursor MCP server

Edit `~/.cursor/mcp.json` and add/update:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "/home/<user>/.local/share/freecad-mcp-bridge-venv/bin/python",
      "args": [
        "/home/<user>/.local/share/FreeCAD/Mod/freecad_mcp/src/freecad_bridge.py"
      ],
      "env": {
        "FREECAD_MCP_HOST": "127.0.0.1",
        "FREECAD_MCP_PORT": "9877"
      }
    }
  }
}
```

Why `9877`? `9876` is commonly used by Blender MCP, which caused command routing conflicts.

## 4) Start FreeCAD server from plugin UI

1. Open FreeCAD
2. Switch to **FreeCAD MCP** workbench
3. Use **Start MCP Server** (toolbar button)

Expected state logic:
- Server stopped -> **Start enabled**, **Stop disabled**
- Server running -> **Start disabled**, **Stop enabled**

## 5) Restart Cursor MCP servers

In Cursor, restart MCP servers (or restart Cursor) after config changes.

## Included local plugin fixes

- Removed ambiguous `import Init` in `InitGui.py` (could import CAM Init by mistake).
- Added dedicated toolbar commands:
  - Show FreeCAD MCP Panel
  - Start MCP Server
  - Stop MCP Server
- Added distinct command icons:
  - `assets/icon_panel.svg`
  - `assets/icon_start.svg`
  - `assets/icon_stop.svg`
- Implemented deterministic Start/Stop enable state logic.
- Bound plugin TCP server to `127.0.0.1:9877`.
- Updated bridge (`src/freecad_bridge.py`) to use env-configurable host/port:
  - `FREECAD_MCP_HOST`
  - `FREECAD_MCP_PORT`
- Improved panel reliability (`QtWidgets`, task-panel behavior, clearer status/feedback).

## Quick troubleshooting

- **Cursor error: connection refused**
  - FreeCAD server not running. Start via toolbar/panel in FreeCAD.
- **Unknown command type**
  - Usually talking to wrong service/port (for example Blender on `9876`).
- **No module named mcp**
  - Venv missing package; reinstall in `~/.local/share/freecad-mcp-bridge-venv`.
- **Buttons not updating**
  - Fully restart FreeCAD after plugin code updates.
