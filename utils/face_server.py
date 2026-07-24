import os
import json
import socket
import logging
import asyncio
import threading
import http.server
import websockets
from utils.event_bus import EventBus

class FaceHTTPServerHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler that serves files from the view/face directory."""
    def __init__(self, *args, directory=None, **kwargs):
        if directory is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            directory = os.path.join(base_dir, "view", "face")
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, format, *args):
        # Quiet standard HTTP request logs to keep terminal clean
        pass


class FaceServer:
    """
    Local Network Face HTTP & WebSocket Server.
    Serves the animated robot face interface over HTTP and streams real-time
    eye gaze states and event animations over WebSockets.
    """
    def __init__(self, host="0.0.0.0", http_port=8080, ws_port=8081):
        self.logger = logging.getLogger("FaceServer")
        
        # Load configuration from config/network_config.json
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(base_dir, "config", "network_config.json")
        
        enabled = True
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    enabled = cfg.get("face_server_enabled", True)
                    if host == "0.0.0.0":
                        host = cfg.get("face_server_host", host)
                    if http_port == 8080:
                        http_port = cfg.get("face_server_port", http_port)
                    if ws_port == 8081:
                        ws_port = cfg.get("face_ws_port", ws_port)
            except Exception as e:
                self.logger.error(f"Failed to load face server config: {e}. Using defaults.")

        self.enabled = enabled
        self.host = host
        self.http_port = http_port
        self.ws_port = ws_port
        
        self.active_clients = set()
        self.loop = None
        self.http_server = None
        self.ws_server = None
        self.current_main_state = "center"
        self.current_override = None

        if not self.enabled:
            self.logger.info("FaceServer is disabled in configuration.")
            return

        # Subscribe to application EventBus events
        EventBus.subscribe("robot_connected", self._on_robot_connected)
        EventBus.subscribe("robot_disconnected", self._on_robot_disconnected)
        EventBus.subscribe("replay_started", self._on_replay_started)
        EventBus.subscribe("fault", self._on_fault)
        EventBus.subscribe("fault_cleared", self._on_fault_cleared)
        EventBus.subscribe("estop", self._on_fault)
        EventBus.subscribe("set_eye_gaze", self.set_eye_position)

        # 1. Start HTTP Server Thread
        self.http_thread = threading.Thread(target=self._run_http_server, daemon=True)
        self.http_thread.start()

        # 2. Start WebSocket Server Thread
        self.ws_thread = threading.Thread(target=self._run_ws_server, daemon=True)
        self.ws_thread.start()

        local_ip = self._get_local_ip()
        self.logger.info(f"Face Server initialized!")
        self.logger.info(f"  -> Face Web Interface: http://{local_ip}:{self.http_port}")
        self.logger.info(f"  -> WebSocket Endpoint: ws://{local_ip}:{self.ws_port}/ws")

    def _get_local_ip(self):
        """Helper to get primary local IP address for logging."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _run_http_server(self):
        """Background thread worker for static HTTP file server."""
        try:
            handler_factory = lambda *args, **kwargs: FaceHTTPServerHandler(*args, **kwargs)
            self.http_server = http.server.ThreadingHTTPServer((self.host, self.http_port), handler_factory)
            self.logger.info(f"HTTP Server listening on {self.host}:{self.http_port}")
            self.http_server.serve_forever()
        except Exception as e:
            self.logger.error(f"Error running HTTP server: {e}")

    def _run_ws_server(self):
        """Background thread worker running asyncio event loop for WebSockets."""
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        async def handler(websocket):
            self.active_clients.add(websocket)
            self.logger.info(f"New Face WebSocket client connected from {websocket.remote_address}")
            try:
                # Sync current state upon client connection
                init_msg = {
                    "type": "set_main_state",
                    "position": self.current_main_state
                }
                await websocket.send(json.dumps(init_msg))
                if self.current_override:
                    await websocket.send(json.dumps({"type": "set_override", "override": self.current_override}))

                async for message in websocket:
                    # Handle client incoming messages (e.g. key presses sent from client)
                    try:
                        data = json.loads(message)
                        if data.get("type") in ["set_main_state", "gaze_command"]:
                            pos = data.get("position") or data.get("gaze")
                            if pos:
                                self.set_eye_position(pos)
                    except Exception:
                        pass
            except websockets.exceptions.ConnectionClosed:
                pass
            finally:
                self.active_clients.remove(websocket)
                self.logger.info(f"Face WebSocket client disconnected.")

        async def main_ws():
            async with websockets.serve(handler, self.host, self.ws_port):
                self.logger.info(f"WebSocket Server listening on {self.host}:{self.ws_port}")
                self.stop_future = self.loop.create_future()
                await self.stop_future

        try:
            self.loop.run_until_complete(main_ws())
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Error running WebSocket server: {e}")

    def broadcast(self, payload: dict):
        """Broadcasts JSON payload to all connected WebSocket clients thread-safely."""
        if not self.loop or not self.loop.is_running():
            return
        
        msg_str = json.dumps(payload)

        async def _send_all():
            if self.active_clients:
                # Use asyncio.gather to broadcast to all connected web clients
                await asyncio.gather(
                    *[client.send(msg_str) for client in self.active_clients],
                    return_exceptions=True
                )

        asyncio.run_coroutine_threadsafe(_send_all(), self.loop)

    def set_eye_position(self, position: str):
        """Programmatically changes the active Main Face State ('center', 'down_left', 'down_right', 'down_center')."""
        self.current_main_state = position
        self.broadcast({"type": "set_main_state", "position": position})

    def _on_robot_connected(self):
        self.current_override = None
        self.broadcast({"type": "clear_override", "override": "disconnected"})

    def _on_robot_disconnected(self, block=False):
        self.current_override = "disconnected"
        self.broadcast({"type": "set_override", "override": "disconnected"})

    def _on_replay_started(self):
        self.broadcast({"type": "trigger_animation", "animation": "short_twinkle"})

    def _on_fault(self):
        self.current_override = "fault"
        self.broadcast({"type": "set_override", "override": "fault"})

    def _on_fault_cleared(self):
        self.current_override = None
        self.broadcast({"type": "clear_override", "override": "fault"})

    def close(self):
        """Clean up HTTP and WebSocket servers upon application exit."""
        try:
            # Broadcast disconnected override so connected face interface enters sleep mode
            self._on_robot_disconnected()
            time.sleep(0.1)
        except Exception:
            pass

        EventBus.unsubscribe("robot_connected", self._on_robot_connected)
        EventBus.unsubscribe("robot_disconnected", self._on_robot_disconnected)
        EventBus.unsubscribe("replay_started", self._on_replay_started)
        EventBus.unsubscribe("fault", self._on_fault)
        EventBus.unsubscribe("fault_cleared", self._on_fault_cleared)
        EventBus.unsubscribe("estop", self._on_fault)
        EventBus.unsubscribe("set_eye_gaze", self.set_eye_position)

        if self.http_server:
            try:
                self.http_server.shutdown()
                self.http_server.server_close()
            except Exception as e:
                self.logger.error(f"Error shutting down HTTP server: {e}")

        if self.loop and self.loop.is_running():
            def _stop_ws():
                if hasattr(self, "stop_future") and not self.stop_future.done():
                    self.stop_future.set_result(True)
            self.loop.call_soon_threadsafe(_stop_ws)
        
        self.logger.info("FaceServer shutdown successfully.")
