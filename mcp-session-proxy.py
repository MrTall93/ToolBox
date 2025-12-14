#!/usr/bin/env python3
"""
MCP Proxy with session management for MCP Inspector
"""
import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import uuid
import threading


class MCPSessionProxy(http.server.BaseHTTPRequestHandler):
    # Store session data
    sessions = {}

    def do_POST(self):
        if self.path != '/mcp':
            self.send_error(404)
            return

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        try:
            request = json.loads(post_data.decode('utf-8'))
        except:
            self.send_error(400, "Invalid JSON")
            return

        # Get session ID from header or create new one
        session_id = self.headers.get('Mcp-Session-Id')
        if not session_id:
            session_id = str(uuid.uuid4())

            # Initialize session with initialize call
            init_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "mcp-inspector",
                        "version": "1.0.0"
                    }
                },
                "id": 0
            }

            # Send initialize request
            try:
                req = urllib.request.Request(
                    'http://localhost:8081/mcp',
                    data=json.dumps(init_request).encode(),
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json, text/event-stream'
                    }
                )

                with urllib.request.urlopen(req) as response:
                    response_data = response.read().decode('utf-8')
                    if 'data: ' in response_data:
                        for line in response_data.split('\n'):
                            if line.startswith('data: '):
                                init_response = json.loads(line[6:])
                                self.sessions[session_id] = init_response.get('result', {})
                                break
            except Exception as e:
                print(f"Failed to initialize session: {e}")

        # Forward the actual request with session
        try:
            req = urllib.request.Request(
                'http://localhost:8081/mcp',
                data=post_data,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json, text/event-stream',
                    'Mcp-Session-Id': session_id
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
                                self.send_header('Mcp-Session-Id', session_id)
                                self.end_headers()

                                self.wfile.write(json.dumps(json_data).encode())
                                return
                            except json.JSONDecodeError:
                                continue

                # If no SSE data found, return error
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid response from MCP server"}).encode())

        except Exception as e:
            print(f"Error forwarding request: {e}")
            self.send_error(500, str(e))

    def do_OPTIONS(self):
        # Handle CORS preflight
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS, GET')
        self.send_header('Access-Control-Allow-Headers', 'Mcp-Session-Id, Content-Type, Accept')
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
                "message": "MCP Session Proxy is running",
                "endpoint": "/mcp",
                "sessions": len(self.sessions)
            }).encode())
        else:
            self.send_error(404)


if __name__ == '__main__':
    PORT = 8080
    Handler = MCPSessionProxy

    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Starting MCP session proxy on port {PORT}")
        print(f"MCP Inspector can connect to: http://localhost:{PORT}/mcp")
        print("Proxy handles session management automatically")
        httpd.serve_forever()