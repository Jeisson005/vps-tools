#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import socket

PORT = int(os.environ.get("PORT", "9000"))

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        hostname = socket.gethostname()
        body = (
            "OK: test_server.py\n"
            f"path={self.path}\n"
            f"host_header={self.headers.get('Host')}\n"
            f"listening_port={PORT}\n"
            f"container_seen_by_host={hostname}\n"
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # log sencillo a stdout
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args))

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Listening on http://0.0.0.0:{PORT}")
    server.serve_forever()
