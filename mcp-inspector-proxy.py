#!/usr/bin/env python3
"""
Simple proxy to forward MCP Inspector requests from port 8080 to 8081
"""
import sys
import asyncio
from aiohttp import web, ClientSession


async def proxy_handler(request):
    """Proxy request to the actual MCP server on port 8081"""
    if request.path != '/mcp':
        return web.Response(status=404, text="Not Found")

    # Forward headers
    headers = dict(request.headers)
    headers.update({
        'Content-Type': 'application/json',
        'Accept': 'application/json, text/event-stream'
    })

    # Get request body
    try:
        data = await request.json()
    except:
        data = {}

    async with ClientSession() as session:
        async with session.post(
            'http://localhost:8081/mcp',
            json=data,
            headers=headers
        ) as resp:
            # Handle SSE response
            if resp.status == 200:
                text = await resp.text()
                # Extract JSON from SSE format
                if 'data: ' in text:
                    lines = text.split('\n')
                    for line in lines:
                        if line.startswith('data: '):
                            json_data = line[6:]  # Remove 'data: ' prefix
                            return web.Response(
                                body=json_data,
                                headers={'Content-Type': 'application/json'}
                            )
                return web.Response(text=text, headers=resp.headers)
            else:
                return web.Response(
                    status=resp.status,
                    text=await resp.text()
                )


if __name__ == '__main__':
    app = web.Application()
    app.router.add_post('/mcp', proxy_handler)
    app.router.add_get('/mcp', proxy_handler)

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"Starting MCP proxy on port {port}")
    print("Forwarding requests to http://localhost:8081/mcp")
    web.run_app(app, host='0.0.0.0', port=port)