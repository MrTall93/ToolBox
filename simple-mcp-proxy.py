#!/usr/bin/env python3
"""
Simple HTTP proxy to translate SSE responses to JSON for MCP Inspector
"""
import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import threading


class MCPProxy(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/mcp':
            self.send_error(404)
            return

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        try:
            # Forward request to actual MCP server
            req = urllib.request.Request(
                'http://localhost:8081/mcp',
                data=post_data,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json, text/event-stream'
                }
            )

            with urllib.request.urlopen(req) as response:
                response_data = response.read().decode('utf-8')

                # Parse SSE response and extract JSON
                if 'data: ' in response_data:
                    for line in response_data.split('\n'):
                        if line.startswith('data: '):
                            try:
                                json_data = json.loads(line[6:])

                                # Send JSON response
                                self.send_response(200)
                                self.send_header('Content-Type', 'application/json')
                                self.send_header('Access-Control-Allow-Origin', '*')
                                self.end_headers()

                                self.wfile.write(json.dumps(json_data).encode())
                                return
                            except json.JSONDecodeError:
                                continue

                # If no SSE data found, return as-is
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(response_data.encode())

        except Exception as e:
            self.send_error(500, str(e))

    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS, GET')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_GET(self):
        # Handle health checks
        if self.path == '/mcp':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "message": "MCP Proxy is running",
                "endpoint": "/mcp"
            }).encode())
        else:
            self.send_error(404)


if __name__ == '__main__':
    PORT = 8080
    Handler = MCPProxy

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Starting MCP proxy on port {PORT}")
        print(f"MCP Inspector can connect to: http://localhost:{PORT}/mcp")
        print("Proxy forwards to: http://localhost:8081/mcp")
        httpd.serve_forever()