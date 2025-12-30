import json
import threading
import logging
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from rollershutter import RollerShutter
from typing import List, Dict, Any


class SimpleRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # suppress access logging
        pass

    def do_GET(self):
        parsed_url = urlparse(self.path)
        shutter_name = parsed_url.path.lstrip("/")
        shutter = next((s for s in self.server.shutters if s.name == shutter_name), None)
        if shutter:
            query_params = parse_qs(parsed_url.query)
            if 'position' in query_params:
                try:
                    new_pos = int(query_params['position'][0])
                    target_pos = new_pos
                    shutter.set_position(target_pos)
                except ValueError:
                    self._send_json(400, {"error": "position must be a number"})
            else:
                self._send_json(200, {'position': shutter.position})
        else:
            html = "<h1>available shutters</h1><ul>"
            for s in self.server.shutters :
                html += f"<li><a href='/{s.name}'>{s.name}</a></li>"
            html += "</ul>"
            self._send_html(200, html)

    def _send_html(self, status, message):
        self.send_response(status)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))

    def _send_json(self, status, data: Dict[str, Any]):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

class RollershutterWebServer:
    def __init__(self, shutters: List[RollerShutter],  host='0000', port=8000):
        self.host = host
        self.port = port
        self.address = (self.host, self.port)
        self.server = HTTPServer(self.address, SimpleRequestHandler)
        self.server.shutters = shutters
        self.server_thread = None

    def start(self):
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        logging.info(f"web server started http://{self.host}:{self.port}")

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        logging.info("web server stopped")

