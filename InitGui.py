import FreeCAD as App
import FreeCADGui as Gui
import os
import socket
import sys

# Last known state fallback. Default: stopped -> Start enabled.
_last_known_running = False


def _probe_server_running(host="127.0.0.1", port=9877):
    """Probe TCP listener directly; avoids import timing issues in IsActive()."""
    try:
        with socket.create_connection((host, port), timeout=0.15):
            return True
    except Exception:
        return False


def _sync_running_state():
    global _last_known_running
    _last_known_running = bool(_probe_server_running())
    return _last_known_running


def _mcp_running():
    global _last_known_running
    try:
        import freecad_mcp
        running = bool(freecad_mcp.mcp_server_running())
        _last_known_running = running
        return running
    except Exception:
        # Keep deterministic fallback if module import isn't ready yet.
        return _last_known_running


def _refresh_command_ui():
    """Refresh toolbar/menu command enabled state."""
    try:
        Gui.updateGui()
    except Exception:
        pass

# Create the command class
class FreeCADMCPShowCommand:
    """Command to show the FreeCAD MCP panel"""
    
    def GetResources(self):
        user_dir = App.getUserAppDataDir()
        icon_path = os.path.join(user_dir, "Mod", "freecad_mcp", "assets", "icon_panel.svg")
        return {
            'Pixmap': icon_path,
            'MenuText': 'Show FreeCAD MCP Panel',
            'ToolTip': 'Show the FreeCAD Model Control Protocol panel'
        }
        
    def IsActive(self):
        return True
        
    def Activated(self):
        import freecad_mcp
        freecad_mcp.show_panel()


class FreeCADMCPStartCommand:
    """Start MCP TCP server (same as panel Start Server)."""

    def GetResources(self):
        user_dir = App.getUserAppDataDir()
        icon_path = os.path.join(user_dir, "Mod", "freecad_mcp", "assets", "icon_start.svg")
        return {
            "Pixmap": icon_path,
            "MenuText": "Start MCP Server",
            "ToolTip": "Start listening on 127.0.0.1:9877 for the Cursor MCP bridge",
        }

    def IsActive(self):
        return not _last_known_running

    def Activated(self):
        global _last_known_running
        import freecad_mcp

        ok, msg = freecad_mcp.mcp_server_start(show_dialog_on_ok=False)
        _last_known_running = bool(ok)
        freecad_mcp._mcp_message_box("FreeCAD MCP", msg, error=not ok)
        try:
            Gui.updateGui()
        except Exception:
            pass


class FreeCADMCPStopCommand:
    """Stop MCP TCP server."""

    def GetResources(self):
        user_dir = App.getUserAppDataDir()
        icon_path = os.path.join(user_dir, "Mod", "freecad_mcp", "assets", "icon_stop.svg")
        return {
            "Pixmap": icon_path,
            "MenuText": "Stop MCP Server",
            "ToolTip": "Stop the MCP bridge listener on port 9877",
        }

    def IsActive(self):
        return _last_known_running

    def Activated(self):
        global _last_known_running
        import freecad_mcp

        ok, msg = freecad_mcp.mcp_server_stop(show_dialog=False)
        _last_known_running = False
        freecad_mcp._mcp_message_box("FreeCAD MCP", msg, error=False)
        try:
            Gui.updateGui()
        except Exception:
            pass


# Register commands
if not hasattr(Gui, "freecad_mcp_command"):
    Gui.freecad_mcp_command = FreeCADMCPShowCommand()
    Gui.addCommand("FreeCAD_MCP_Show", Gui.freecad_mcp_command)

if not hasattr(Gui, "freecad_mcp_start_command"):
    Gui.freecad_mcp_start_command = FreeCADMCPStartCommand()
    Gui.addCommand("FreeCAD_MCP_Start", Gui.freecad_mcp_start_command)

if not hasattr(Gui, "freecad_mcp_stop_command"):
    Gui.freecad_mcp_stop_command = FreeCADMCPStopCommand()
    Gui.addCommand("FreeCAD_MCP_Stop", Gui.freecad_mcp_stop_command)

class FreeCADMCPWorkbench(Gui.Workbench):
    MenuText = "FreeCAD MCP"
    ToolTip = "FreeCAD Model Control Protocol"
    
    def GetIcon(self):
        """Return the icon for this workbench"""
        user_dir = App.getUserAppDataDir()
        icon_path = os.path.join(user_dir, "Mod", "freecad_mcp", "assets", "icon.svg")
        return icon_path
    
    def Initialize(self):
        """This function is called at workbench creation."""
        # Add current directory to Python path
        mod_dir = os.path.join(App.getUserAppDataDir(), "Mod", "freecad_mcp")
        if mod_dir not in sys.path:
            sys.path.append(mod_dir)
        
        # List of commands in the workbench
        self.command_list = [
            "FreeCAD_MCP_Show",
            "FreeCAD_MCP_Start",
            "FreeCAD_MCP_Stop",
        ]
        
        # Create the toolbar
        self.appendToolbar("FreeCAD MCP Tools", self.command_list)
        
        # Create the menu
        self.appendMenu("&FreeCAD MCP", self.command_list)
        
    def Activated(self):
        """This function is called when the workbench is activated."""
        global _last_known_running
        try:
            _last_known_running = bool(_probe_server_running())
        except Exception:
            _last_known_running = False
        try:
            Gui.updateGui()
        except Exception:
            pass
        
    def Deactivated(self):
        """This function is called when the workbench is deactivated."""
        pass
        
    def GetClassName(self):
        """Return the name of the associated C++ class."""
        return "Gui::PythonWorkbench"

# Add the workbench if it hasn't been added already
if not hasattr(Gui, "freecad_mcp_workbench"):
    Gui.freecad_mcp_workbench = FreeCADMCPWorkbench()
    Gui.addWorkbench(Gui.freecad_mcp_workbench) 