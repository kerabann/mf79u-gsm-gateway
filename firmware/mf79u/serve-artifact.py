#!/usr/bin/env python3
"""Serve exactly one build artifact once over the isolated USB LAN."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("artifact", type=Path)
parser.add_argument("--bind", default="192.168.0.169")
parser.add_argument("--peer", default="192.168.0.1")
args = parser.parse_args()
data = args.artifact.read_bytes()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.client_address[0] != args.peer or self.path != "/artifact":
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()
        self.server.delivered = True

    def log_message(self, *_):
        pass


server = HTTPServer((args.bind, 18089), Handler)
server.timeout = 10
server.delivered = False
while not server.delivered:
    server.handle_request()
print(f"served {len(data)} bytes")
