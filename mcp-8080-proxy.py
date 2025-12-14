#!/usr/bin/env python3
"""
Simple proxy from port 8080 to 8081 for MCP Inspector
"""
import sys
import asyncio
from aiohttp import web, ClientSession


async def proxy_handler(request):
    """Proxy request to localhost:8081"""
    url = f"http://localhost:8081{request.path_qs}"

    headers = dict(request.headers)
    # Ensure proper headers for MCP
    headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream'
    })

    async with ClientSession() as session:
        try:
            data = await request.json() if request.can_read_body else {}
        except:
            data = {}

        async with session.post(url, json=data, headers=headers) as resp:
            # Handle SSE response
            response_text = await resp.text()

            # If it's SSE format, extract the JSON data
            if response_text.startswith('event: message\ndata: '):
                data_line = response_text.split('\n')[1]
                if data_line.startswith('data: '):
                    json_data = data_line[6:]  # Remove 'data: ' prefix
                    return web.Response(
                        body=json_data,
                        headers={'Content-Type': 'application/json'}
                    )

            return web.Response(
                text=response_text,
                status=resp.status,
                headers=resp.headers
            )


if __name__ == '__main__':
    app = web.Application()
    app.router.add_route('*', '/mcp', proxy_handler)

    print("Starting MCP proxy on port 8080 -> 8081")
    print("MCP Inspector can now connect to: http://localhost:8080/mcp")
    web.run_app(app, host='0.0.0.0', port=8080)