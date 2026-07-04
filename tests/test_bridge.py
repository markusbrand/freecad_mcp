import pytest
import json
import asyncio
import socket
import threading
from unittest.mock import MagicMock, patch
from src.freecad_bridge import get_scene_info, create_object, get_object_info, send_command, run_script

def mock_freecad_server(port, response_dict):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind(('127.0.0.1', port))
    server_sock.listen(1)

    def run():
        try:
            client, _ = server_sock.accept()
            data = client.recv(1024)
            if data:
                # We could verify the incoming command here if needed
                client.sendall(json.dumps(response_dict).encode('utf-8'))
            client.close()
        finally:
            server_sock.close()

    threading.Thread(target=run).start()

@pytest.mark.asyncio
async def test_get_scene_info():
    expected_response = {
        "status": "success",
        "result": {
            "document": {"name": "TestDoc"},
            "objects": [],
            "view": None
        }
    }

    with patch('os.environ.get', side_effect=lambda k, d: "9878" if k == "FREECAD_MCP_PORT" else d):
        mock_freecad_server(9878, expected_response)
        # We need to manually set the port because the decorator in bridge uses the one at import time
        from src import freecad_bridge
        with patch.object(freecad_bridge, 'FREECAD_PORT', 9878):
            result_json = await get_scene_info()
            result = json.loads(result_json)
            assert result == expected_response

@pytest.mark.asyncio
async def test_create_object():
    expected_response = {
        "status": "success",
        "result": {
            "name": "Box",
            "label": "MyBox",
            "type": "Part::Box"
        }
    }

    with patch('src.freecad_bridge.FREECAD_PORT', 9879):
        mock_freecad_server(9879, expected_response)
        result_json = await create_object("Part::Box", "MyBox", Length=10)
        result = json.loads(result_json)
        assert result == expected_response

@pytest.mark.asyncio
async def test_get_object_info():
    expected_response = {
        "status": "success",
        "result": {
            "name": "Box",
            "label": "MyBox",
            "type": "Part::Box",
            "Length": 10.0
        }
    }

    with patch('src.freecad_bridge.FREECAD_PORT', 9880):
        mock_freecad_server(9880, expected_response)
        result_json = await get_object_info("MyBox")
        result = json.loads(result_json)
        assert result == expected_response

@pytest.mark.asyncio
async def test_send_command():
    expected_response = {
        "status": "success",
        "result": {
            "command_result": "success",
            "context": {"document": {"name": "TestDoc"}}
        }
    }

    with patch('src.freecad_bridge.FREECAD_PORT', 9881):
        mock_freecad_server(9881, expected_response)
        result_json = await send_command("App.ActiveDocument.addObject('Part::Box')")
        result = json.loads(result_json)
        assert result == expected_response

@pytest.mark.asyncio
async def test_run_script():
    expected_response = {
        "status": "success",
        "result": {
            "script_result": "success"
        }
    }

    with patch('src.freecad_bridge.FREECAD_PORT', 9882):
        mock_freecad_server(9882, expected_response)
        result_json = await run_script("print('hello')")
        result = json.loads(result_json)
        assert result == expected_response
