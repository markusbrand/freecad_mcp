from typing import Any, Dict
import os
import socket
import json
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("freecad-bridge")

# Avoid localhost → wrong interface; override via mcp.json "env" if needed.
FREECAD_HOST = os.environ.get("FREECAD_MCP_HOST", "127.0.0.1")
FREECAD_PORT = int(os.environ.get("FREECAD_MCP_PORT", "9877"))

async def send_to_freecad(command: Dict[str, Any]) -> Dict[str, Any]:
    """Send a command to FreeCAD and get the response."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((FREECAD_HOST, FREECAD_PORT))
        command_json = json.dumps(command)
        sock.sendall(command_json.encode('utf-8'))
        response = sock.recv(4096)
        sock.close()
        return json.loads(response.decode('utf-8'))
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def send_command(command: str) -> str:
    """Send a command to FreeCAD and get document context information.
    
    Args:
        command: Command to execute in FreeCAD
    
    Returns:
        JSON string containing:
        - Command execution result
        - Current document information
        - Active objects and their properties
        - View state
    """
    command_data = {
        "type": "send_command",
        "params": {
            "command": command,
            "get_context": True
        }
    }
    result = await send_to_freecad(command_data)
    return json.dumps(result, indent=2)

@mcp.tool()
async def run_script(script: str) -> str:
    """Run an arbitrary Python script in FreeCAD context.
    
    Args:
        script: Python script to execute in FreeCAD
    
    Returns:
        JSON string containing the execution result
    """
    command = {
        "type": "run_script",
        "params": {
            "script": script
        }
    }
    result = await send_to_freecad(command)
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')