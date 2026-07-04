import os
import FreeCAD as App
import FreeCADGui as Gui
import json
import socket
import threading
import time
import traceback
from PySide import QtCore, QtWidgets

# Single TCP server for MCP (shared by task panel and toolbar commands).
_mcp_server = None


class FreeCADMCPServer:
    # Default 9877: 9876 is commonly used by Blender MCP; avoid port clash.
    # 127.0.0.1 matches the Cursor bridge (FREECAD_MCP_HOST).
    def __init__(self, host="127.0.0.1", port=9877):
        self.host = host
        self.port = port
        self.running = False
        self.socket = None
        self.client = None
        self.buffer = b''
        self.timer = None
    
    def start(self):
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(1)
            self.socket.setblocking(False)
            # QTimer must belong to the GUI thread / main window or it may never fire in FreeCAD.
            try:
                timer_parent = Gui.getMainWindow()
            except Exception:
                timer_parent = None
            self.timer = QtCore.QTimer(timer_parent)
            self.timer.timeout.connect(self._process_server)
            self.timer.start(100)
            App.Console.PrintMessage(
                f"FreeCAD MCP server started on {self.host}:{self.port}\n"
            )
        except Exception as e:
            App.Console.PrintError(f"Failed to start server: {str(e)}\n")
            self.stop()
            
    def stop(self):
        self.running = False
        if self.timer:
            self.timer.stop()
            self.timer = None
        if self.socket:
            self.socket.close()
        if self.client:
            self.client.close()
        self.socket = None
        self.client = None
        App.Console.PrintMessage("FreeCAD MCP server stopped\n")

    def _process_server(self):
        if not self.running:
            return
            
        try:
            if not self.client and self.socket:
                try:
                    self.client, address = self.socket.accept()
                    self.client.setblocking(False)
                    App.Console.PrintMessage(f"Connected to client: {address}\n")
                except BlockingIOError:
                    pass
                except Exception as e:
                    App.Console.PrintError(f"Error accepting connection: {str(e)}\n")
                
            if self.client:
                try:
                    try:
                        data = self.client.recv(8192)
                        if data:
                            self.buffer += data
                            try:
                                command = json.loads(self.buffer.decode('utf-8'))
                                self.buffer = b''
                                response = self.execute_command(command)
                                response_json = json.dumps(response)
                                self.client.sendall(response_json.encode('utf-8'))
                                # For MCP, we usually close connection after one command if using short-lived connections
                                # but the bridge script currently opens/closes per tool call.
                            except json.JSONDecodeError:
                                pass
                        else:
                            App.Console.PrintMessage("Client disconnected\n")
                            self.client.close()
                            self.client = None
                            self.buffer = b''
                    except BlockingIOError:
                        pass
                    except Exception as e:
                        App.Console.PrintError(f"Error receiving data: {str(e)}\n")
                        self.client.close()
                        self.client = None
                        self.buffer = b''
                        
                except Exception as e:
                    App.Console.PrintError(f"Error with client: {str(e)}\n")
                    if self.client:
                        self.client.close()
                        self.client = None
                    self.buffer = b''
                    
        except Exception as e:
            App.Console.PrintError(f"Server error: {str(e)}\n")

    def execute_command(self, command):
        try:
            cmd_type = command.get("type")
            params = command.get("params", {})
            
            handlers = {
                "send_command": self.handle_send_command,
                "run_script": self.handle_run_script,
                "get_scene_info": self.handle_get_scene_info,
                "create_object": self.handle_create_object,
                "get_object_info": self.handle_get_object_info
            }
            
            handler = handlers.get(cmd_type)
            if handler:
                try:
                    App.Console.PrintMessage(f"Executing handler for {cmd_type}\n")
                    result = handler(**params)
                    return {"status": "success", "result": result}
                except Exception as e:
                    App.Console.PrintError(f"Error in handler {cmd_type}: {str(e)}\n")
                    traceback.print_exc()
                    return {"status": "error", "message": str(e)}
            else:
                return {"status": "error", "message": f"Unknown command type: {cmd_type}"}
                
        except Exception as e:
            App.Console.PrintError(f"Error executing command: {str(e)}\n")
            traceback.print_exc()
            return {"status": "error", "message": str(e)}

    def handle_send_command(self, command, get_context=True):
        """Handle a send_command request with document context"""
        try:
            # Execute the command
            exec(command, {"App": App, "Gui": Gui})
            
            # Get document context if requested
            context = {}
            if get_context:
                context = self.get_document_context()
            
            return {
                "command_result": "success",
                "context": context
            }
        except Exception as e:
            return {
                "command_result": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    def handle_run_script(self, script):
        """Handle a run_script request"""
        try:
            # Create a new local namespace for the script
            namespace = {
                "App": App,
                "Gui": Gui,
                "doc": App.ActiveDocument
            }
            
            # Execute the script
            exec(script, namespace)
            
            return {
                "script_result": "success"
            }
        except Exception as e:
            return {
                "script_result": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    def handle_get_scene_info(self):
        """Handle get_scene_info request"""
        return self.get_document_context()

    def handle_create_object(self, obj_type, obj_name=None, properties=None):
        """Handle create_object request"""
        doc = App.ActiveDocument
        if not doc:
            doc = App.newDocument("Unnamed")

        if obj_name:
            obj = doc.addObject(obj_type, obj_name)
        else:
            obj = doc.addObject(obj_type)

        if properties:
            for key, value in properties.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)

        doc.recompute()

        return self._get_obj_info_dict(obj)

    def handle_get_object_info(self, obj_name):
        """Handle get_object_info request"""
        doc = App.ActiveDocument
        if not doc:
            raise Exception("No active document")

        obj = doc.getObject(obj_name)
        if not obj:
            # Try by label
            for o in doc.Objects:
                if o.Label == obj_name:
                    obj = o
                    break

        if not obj:
            raise Exception(f"Object not found: {obj_name}")

        return self._get_obj_info_dict(obj)

    def _get_obj_info_dict(self, obj):
        """Internal helper to get object info as a dict"""
        obj_info = {
            "name": obj.Name,
            "label": obj.Label,
            "type": obj.TypeId,
            "visibility": obj.ViewObject.Visibility if hasattr(obj, "ViewObject") else None
        }

        # Add placement
        if hasattr(obj, "Placement"):
            pos = obj.Placement.Base
            rot = obj.Placement.Rotation
            obj_info["placement"] = {
                "position": [float(pos.x), float(pos.y), float(pos.z)],
                "rotation": [float(rot.Axis.x), float(rot.Axis.y), float(rot.Axis.z), float(rot.Angle)]
            }

        # Add shape properties
        if hasattr(obj, "Shape"):
            shape = obj.Shape
            obj_info["shape"] = {
                "type": shape.ShapeType,
                "volume": float(shape.Volume) if hasattr(shape, "Volume") else None,
                "area": float(shape.Area) if hasattr(shape, "Area") else None,
                "nb_faces": len(shape.Faces),
                "nb_edges": len(shape.Edges),
                "nb_vertexes": len(shape.Vertexes)
            }

        # Add other common properties
        for prop in ["Length", "Width", "Height", "Radius", "Angle"]:
            if hasattr(obj, prop):
                val = getattr(obj, prop)
                if hasattr(val, "Value"):
                    obj_info[prop] = float(val.Value)
                else:
                    obj_info[prop] = float(val)

        return obj_info

    def get_document_context(self):
        """Get comprehensive information about the current document state"""
        doc = App.ActiveDocument
        if not doc:
            return {
                "document": None,
                "objects": [],
                "view": None
            }

        # Document info
        doc_info = {
            "name": doc.Name,
            "label": doc.Label,
            "filename": doc.FileName if hasattr(doc, "FileName") else None,
            "object_count": len(doc.Objects)
        }

        # Objects info
        objects = []
        for obj in doc.Objects:
            objects.append(self._get_obj_info_dict(obj))

        # View state
        view_info = None
        if Gui.ActiveDocument:
            try:
                view = Gui.ActiveDocument.ActiveView
                cam = view.getCameraNode()
                view_info = {
                    "camera_type": cam.getTypeId(),
                    "camera_position": [float(x) for x in cam.position.getValue()],
                    "camera_orientation": [float(x) for x in cam.orientation.getValue()]
                }
            except Exception:
                pass

        return {
            "document": doc_info,
            "objects": objects,
            "view": view_info
        }


def mcp_server_running():
    global _mcp_server
    return _mcp_server is not None and getattr(_mcp_server, "socket", None) is not None


def _mcp_message_box(title, text, *, error=False):
    """Visible feedback; Report view is easy to miss."""
    try:
        parent = Gui.getMainWindow()
    except Exception:
        parent = None
    box = QtWidgets.QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(
        QtWidgets.QMessageBox.Critical
        if error
        else QtWidgets.QMessageBox.Information
    )
    if hasattr(box, "exec"):
        box.exec()
    else:
        box.exec_()


def mcp_server_start(*, show_dialog_on_ok=False):
    """Start the MCP TCP server (idempotent).

    Returns (ok: bool, message: str) for UI / logging.
    """
    global _mcp_server
    if mcp_server_running():
        msg = "MCP server is already running."
        App.Console.PrintMessage(f"FreeCAD {msg}\n")
        return True, msg
    try:
        _mcp_server = FreeCADMCPServer()
        _mcp_server.start()
        if _mcp_server.socket is None:
            _mcp_server = None
            err = (
                "Could not listen on 127.0.0.1:9877 (bind failed). "
                "Another program may be using that port."
            )
            App.Console.PrintError(err + "\n")
            return False, err
        ok_msg = f"Listening on {_mcp_server.host}:{_mcp_server.port}"
        App.Console.PrintMessage(ok_msg + "\n")
        if show_dialog_on_ok:
            _mcp_message_box("FreeCAD MCP", ok_msg, error=False)
        return True, ok_msg
    except Exception as e:
        _mcp_server = None
        App.Console.PrintError(f"MCP start error: {e}\n")
        traceback.print_exc()
        return False, str(e)


def mcp_server_stop(*, show_dialog=False):
    """Stop the MCP TCP server. Returns (ok, message)."""
    global _mcp_server
    if _mcp_server is None:
        msg = "MCP server was not running."
        if show_dialog:
            _mcp_message_box("FreeCAD MCP", msg, error=False)
        return False, msg
    _mcp_server.stop()
    _mcp_server = None
    msg = "MCP server stopped."
    App.Console.PrintMessage(msg + "\n")
    if show_dialog:
        _mcp_message_box("FreeCAD MCP", msg, error=False)
    return True, msg


class FreeCADMCPPanel:
    """Task panel: must use QtWidgets + getStandardButtons() or the combo view stays blank."""

    def __init__(self):
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("FreeCAD MCP")
        self.form.setMinimumWidth(280)

        layout = QtWidgets.QVBoxLayout(self.form)

        self.help_label = QtWidgets.QLabel(
            "Start the server so Cursor (MCP bridge on port 9877) can run scripts in FreeCAD.\n"
            "You can also use the toolbar: Start MCP / Stop MCP."
        )
        self.help_label.setWordWrap(True)
        layout.addWidget(self.help_label)

        self.status_label = QtWidgets.QLabel("Server: Stopped")
        layout.addWidget(self.status_label)

        button_layout = QtWidgets.QHBoxLayout()
        self.start_button = QtWidgets.QPushButton("Start Server")
        self.stop_button = QtWidgets.QPushButton("Stop Server")
        self.stop_button.setEnabled(False)

        # QueuedConnection avoids lost clicks when the task panel opens in the same event loop tick.
        self.start_button.clicked.connect(
            self.start_server, QtCore.Qt.QueuedConnection
        )
        self.stop_button.clicked.connect(
            self.stop_server, QtCore.Qt.QueuedConnection
        )

        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        self._sync_ui_from_server()

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Close

    def _sync_ui_from_server(self):
        if mcp_server_running():
            srv = _mcp_server
            addr = f"{srv.host}:{srv.port}"
            self.status_label.setText(f"Server: Running on {addr}")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
        else:
            self.status_label.setText("Server: Stopped (port 9877)")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    @QtCore.Slot()
    def start_server(self):
        ok, msg = mcp_server_start(show_dialog_on_ok=False)
        self._sync_ui_from_server()
        if not ok:
            _mcp_message_box("FreeCAD MCP — could not start", msg, error=True)

    @QtCore.Slot()
    def stop_server(self):
        mcp_server_stop(show_dialog=False)
        self._sync_ui_from_server()


def show_panel():
    panel = FreeCADMCPPanel()
    Gui.Control.showDialog(panel)
