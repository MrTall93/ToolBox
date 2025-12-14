#!/usr/bin/env python3
"""
Test client for Toolbox MCP Server.

This script connects to the Toolbox MCP server and tests various operations.
"""
import asyncio
import json
import logging
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)


async def test_mcp_server():
    """Test the MCP server functionality."""
    # Create server parameters for stdio transport
    server_params = StdioServerParameters(
        command="python3.9",
        args=["-m", "app.mcp_server"],
        env=None,
    )

    logger.info("Connecting to Toolbox MCP Server...")

    # Connect to the server
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()

            logger.info("✅ Connected to MCP Server")

            # Test 1: List tools
            logger.info("\n--- Testing: List Tools ---")
            tools_result = await session.list_tools()
            logger.info(f"Found {len(tools_result.tools)} tools:")
            for tool in tools_result.tools[:5]:  # Show first 5
                logger.info(f"  - {tool.name}: {tool.description}")
            if len(tools_result.tools) > 5:
                logger.info(f"  ... and {len(tools_result.tools) - 5} more")

            # Test 2: Call a simple tool
            logger.info("\n--- Testing: Call Tool ---")
            if tools_result.tools:
                # Try to find the calculator tool
                calc_tool = None
                for tool in tools_result.tools:
                    if "calculate" in tool.name.lower():
                        calc_tool = tool
                        break

                if calc_tool:
                    logger.info(f"Calling tool: {calc_tool.name}")
                    try:
                        result = await session.call_tool(
                            calc_tool.name,
                            {
                                "operation": "add",
                                "a": 10,
                                "b": 5
                            }
                        )
                        logger.info("✅ Tool executed successfully")
                        for content in result.content:
                            if hasattr(content, 'text'):
                                logger.info(f"Result: {content.text[:200]}...")  # Show first 200 chars
                    except Exception as e:
                        logger.error(f"❌ Error calling tool: {e}")

            # Test 3: List prompts
            logger.info("\n--- Testing: List Prompts ---")
            prompts_result = await session.list_prompts()
            logger.info(f"Found {len(prompts_result.prompts)} prompts:")
            for prompt in prompts_result.prompts:
                logger.info(f"  - {prompt.name}: {prompt.description}")

            # Test 4: Get a prompt
            if prompts_result.prompts:
                prompt = prompts_result.prompts[0]
                logger.info(f"\n--- Testing: Get Prompt '{prompt.name}' ---")
                try:
                    if prompt.name == "find-tools":
                        prompt_result = await session.get_prompt(
                            prompt.name,
                            {"query": "calculator", "threshold": 0.7}
                        )
                    else:
                        prompt_result = await session.get_prompt(prompt.name, {})

                    logger.info("✅ Prompt retrieved successfully")
                    for message in prompt_result.messages:
                        if hasattr(message.content, 'text'):
                            logger.info(f"Message: {message.content.text[:200]}...")
                except Exception as e:
                    logger.error(f"❌ Error getting prompt: {e}")

            # Test 5: List resources
            logger.info("\n--- Testing: List Resources ---")
            resources_result = await session.list_resources()
            logger.info(f"Found {len(resources_result.resources)} resources:")
            for resource in resources_result.resources:
                logger.info(f"  - {resource.name}: {resource.description}")

            # Test 6: Read a resource
            if resources_result.resources:
                resource = resources_result.resources[0]
                logger.info(f"\n--- Testing: Read Resource '{resource.name}' ---")
                try:
                    resource_result = await session.read_resource(resource.uri)
                    logger.info("✅ Resource read successfully")
                    for content in resource_result.contents:
                        if hasattr(content, 'text'):
                            logger.info(f"Content (first 200 chars): {content.text[:200]}...")
                except Exception as e:
                    logger.error(f"❌ Error reading resource: {e}")

            logger.info("\n✅ All MCP server tests completed!")


async def main():
    """Main function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    try:
        await test_mcp_server()
    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())