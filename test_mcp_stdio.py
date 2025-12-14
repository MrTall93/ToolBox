#!/usr/bin/env python3
"""
Test client for Toolbox MCP Server (stdio version).

This script connects to the Toolbox MCP server and tests various operations.
"""
import asyncio
import json
import logging
import subprocess
import sys
from typing import Any, Dict

logger = logging.getLogger(__name__)


async def test_mcp_stdio_server():
    """Test the MCP server functionality via stdio."""
    logger.info("Testing Toolbox MCP Server (stdio transport)")

    # Start the MCP server process
    process = await asyncio.create_subprocess_exec(
        "python3.9",
        "-m",
        "app.mcp_stdio_server",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={
            "DATABASE_URL": "postgresql+asyncpg://toolregistry:devpassword@localhost:5432/toolregistry",
            "EMBEDDING_ENDPOINT_URL": "http://host.docker.internal:1234/v1/embeddings",
            "EMBEDDING_API_KEY": "dummy-key",
            "EMBEDDING_DIMENSION": "768",
            "LOG_LEVEL": "INFO",
            "PYTHONPATH": "/app",
        }
    )

    try:
        # Test 1: Initialize
        logger.info("\n--- Testing: Initialize ---")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }

        # Send request
        request_json = json.dumps(init_request) + "\n"
        process.stdin.write(request_json.encode())
        await process.stdin.drain()

        # Read response
        response_line = await process.stdout.readline()
        response = json.loads(response_line.decode())

        if "result" in response:
            logger.info("✅ Initialization successful")
            logger.info(f"Server: {response['result']['serverInfo']}")
        else:
            logger.error(f"❌ Initialization failed: {response}")
            return

        # Test 2: List tools
        logger.info("\n--- Testing: List Tools ---")
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        request_json = json.dumps(list_tools_request) + "\n"
        process.stdin.write(request_json.encode())
        await process.stdin.drain()

        response_line = await process.stdout.readline()
        response = json.loads(response_line.decode())

        if "result" in response and "tools" in response["result"]:
            tools = response["result"]["tools"]
            logger.info(f"✅ Found {len(tools)} tools")
            for tool in tools[:3]:  # Show first 3
                logger.info(f"  - {tool['name']}: {tool['description']}")
        else:
            logger.error(f"❌ Failed to list tools: {response}")

        # Test 3: Call a tool
        if tools:
            calc_tool = None
            for tool in tools:
                if "calculate" in tool["name"].lower():
                    calc_tool = tool
                    break

            if calc_tool:
                logger.info("\n--- Testing: Call Tool ---")
                call_tool_request = {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": calc_tool["name"],
                        "arguments": {
                            "operation": "add",
                            "a": 10,
                            "b": 5
                        }
                    }
                }

                request_json = json.dumps(call_tool_request) + "\n"
                process.stdin.write(request_json.encode())
                await process.stdin.drain()

                response_line = await process.stdout.readline()
                response = json.loads(response_line.decode())

                if "result" in response:
                    result = response["result"]
                    if result.get("isError"):
                        logger.error(f"❌ Tool execution failed")
                    else:
                        logger.info("✅ Tool executed successfully")
                        for content in result.get("content", []):
                            if content.get("type") == "text":
                                text = content["text"]
                                # Show first 200 chars
                                logger.info(f"Result: {text[:200]}...")
                else:
                    logger.error(f"❌ Tool call failed: {response}")

    finally:
        # Close stdin to signal server to stop
        process.stdin.close()
        await process.wait()


async def main():
    """Main function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    try:
        await test_mcp_stdio_server()
        logger.info("\n✅ MCP server test completed successfully!")
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())