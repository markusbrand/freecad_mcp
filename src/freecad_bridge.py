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

        # Buffer to store the response
        response_data = b""
        while True:
            chunk = sock.recv(8192)
            if not chunk:
                break
            response_data += chunk
            # Check if we have a complete JSON object
            try:
                data = json.loads(response_data.decode('utf-8'))
                sock.close()
                return data
            except json.JSONDecodeError:
                continue

        sock.close()
        if response_data:
            return json.loads(response_data.decode('utf-8'))
        return {"status": "error", "message": "No response from FreeCAD"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def send_command(command: str) -> str:
    """Send a raw Python command to FreeCAD and get document context information.
    
    Args:
        command: Python command to execute in FreeCAD (e.g., "App.ActiveDocument.addObject('Part::Box', 'myBox')")
    
    Returns:
        JSON string containing command execution result and current document context.
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

@mcp.tool()
async def get_scene_info() -> str:
    """Retrieve comprehensive information about the current FreeCAD document.

    Returns:
        JSON string containing document properties, object list, and view information.
    """
    command = {
        "type": "get_scene_info"
    }
    result = await send_to_freecad(command)
    return json.dumps(result, indent=2)

@mcp.tool()
async def create_object(obj_type: str, obj_name: str = None, **kwargs) -> str:
    """Create a new object in the FreeCAD document.

    Args:
        obj_type: Type of object to create (e.g., "Part::Box", "Part::Sphere", "Part::Cylinder")
        obj_name: Optional label for the new object.
        **kwargs: Optional properties to set (e.g., Length=10, Width=20, Radius=5).

    Returns:
        JSON string containing information about the created object.
    """
    command = {
        "type": "create_object",
        "params": {
            "obj_type": obj_type,
            "obj_name": obj_name,
            "properties": kwargs
        }
    }
    result = await send_to_freecad(command)
    return json.dumps(result, indent=2)

@mcp.tool()
async def get_object_info(obj_name: str) -> str:
    """Get detailed information about a specific object in FreeCAD.

    Args:
        obj_name: The name or label of the object.

    Returns:
        JSON string containing detailed properties of the object.
    """
    command = {
        "type": "get_object_info",
        "params": {
            "obj_name": obj_name
        }
    }
    result = await send_to_freecad(command)
    return json.dumps(result, indent=2)

if __name__ == "__main__":
    mcp.run(transport='stdio')
