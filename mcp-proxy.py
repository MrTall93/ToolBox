#!/usr/bin/env python3
"""
Simple MCP HTTP proxy for MCP Inspector compatibility.
Translates regular HTTP requests to MCP protocol over HTTP.
"""

import json
import sys
from typing import Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests


class MCPProxyHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/mcp':
            self.send_error(404)
            return

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        try:
            # Parse request
            request = json.loads(post_data.decode('utf-8'))

            # Forward to actual MCP server
            response = requests.post(
                'http://toolbox-mcp-http.toolbox:8080/mcp',
                json=request,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json, text/event-stream'
                }
            )

            # Return response
            self.send_response(response.status_code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()

            # Parse SSE response if needed
            if response.text.startswith('event: message\ndata: '):
                data = response.text.split('data: ')[1].strip()
                json_data = json.loads(data)
                self.wfile.write(json.dumps(json_data).encode())
            else:
                self.wfile.write(response.text.encode())

        except Exception as e:
            self.send_error(500, str(e))

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "name": "Toolbox MCP Proxy",
                "description": "Proxy for MCP Inspector compatibility",
                "endpoint": "/mcp"
            }).encode())
        else:
            self.send_error(404)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(('0.0.0.0', port), MCPProxyHandler)
    print(f"MCP Proxy running on port {port}")
    server.serve_forever()