"""
LiteLLM + Tool Registry MCP Integration Examples

This script demonstrates how to use your Tool Registry MCP Server
through LiteLLM's unified interface for tool discovery and execution.
"""

import asyncio
import json
import os
from typing import List, Dict, Any

# LiteLLM import (pip install litellm)
import litellm
from litellm import completion

# Tool Registry MCP adapter
from app.adapters.litellm_mcp import get_litellm_mcp_adapter


async def example_basic_tool_usage():
    """Example: Basic tool discovery and usage with LiteLLM."""
    print("🔧 Basic Tool Usage Example")
    print("=" * 50)

    # Initialize the MCP adapter
    adapter = get_litellm_mcp_adapter()

    try:
        # List available tools
        print("\n📋 Discovering available tools...")
        tools = await adapter.list_tools(limit=5)

        print(f"Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.function['name']}: {tool.function['description']}")

        # Search for specific tools
        print("\n🔍 Searching for calculator tools...")
        search_results = await adapter.find_tools(query="calculator math arithmetic", limit=3)

        print(f"Found {len(search_results)} calculator tools:")
        for tool in search_results:
            print(f"  - {tool.function['name']}: {tool.function['description']}")

        # Execute a tool with LiteLLM
        if search_results:
            tool_name = search_results[0].function['name']
            print(f"\n⚡ Executing tool: {tool_name}")

            # Configure LiteLLM to use the tool
            litellm_tools = [tool.dict() for tool in search_results]

            response = completion(
                model="gpt-4",  # Or your preferred model
                messages=[
                    {
                        "role": "user",
                        "content": "What is 15 + 27?"
                    }
                ],
                tools=litellm_tools,
                tool_choice="auto"
            )

            print("Response:", response.choices[0].message.content)

            # Check if tool was called
            if response.choices[0].message.tool_calls:
                tool_call = response.choices[0].message.tool_calls[0]
                print(f"Tool called: {tool_call.function.name}")
                print(f"Arguments: {tool_call.function.arguments}")

    finally:
        await adapter.close()


async def example_advanced_search_and_execution():
    """Example: Advanced search and batch tool execution."""
    print("\n🚀 Advanced Search and Execution Example")
    print("=" * 50)

    adapter = get_litellm_mcp_adapter()

    try:
        # Category-based search
        print("\n📂 Searching by category...")
        dev_tools = await adapter.list_tools(
            category="development",
            limit=3,
            tags=["api", "json"]
        )

        print(f"Found {len(dev_tools)} development tools:")
        for tool in dev_tools:
            metadata = tool.function.get('metadata', {})
            print(f"  - {tool.function['name']}")
            print(f"    Category: {metadata.get('category', 'N/A')}")
            print(f"    Tags: {', '.join(metadata.get('tags', []))}")

        # Semantic search with custom threshold
        print("\n🎯 Semantic search with custom threshold...")
        search_results = await adapter.find_tools(
            query="data analysis csv processing",
            limit=5,
            threshold=0.8,  # Higher similarity threshold
            use_hybrid_search=True
        )

        print(f"High-precision search results: {len(search_results)} tools")
        for i, tool in enumerate(search_results, 1):
            print(f"  {i}. {tool.function['name']}")

        # Execute multiple tools in sequence
        if search_results:
            print("\n⚙️ Sequential tool execution...")

            # First tool: Data processor
            tool1 = search_results[0]
            print(f"Executing: {tool1.function['name']}")

            response1 = completion(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": "Process this CSV data: name,age,city\\nJohn,25,NYC\\nJane,30,LA"
                    }
                ],
                tools=[tool1.dict()],
                tool_choice="auto"
            )

            # Second tool: Data analyzer (if available)
            if len(search_results) > 1:
                tool2 = search_results[1]
                print(f"Executing: {tool2.function['name']}")

                # Use results from first tool as input to second
                response2 = completion(
                    model="gpt-3.5-turbo",
                    messages=[
                        {
                            "role": "user",
                            "content": f"Analyze this processed data: {response1.choices[0].message.content}"
                        }
                    ],
                    tools=[tool2.dict()],
                    tool_choice="auto"
                )

                print("Final result:", response2.choices[0].message.content)

    finally:
        await adapter.close()


async def example_error_handling_and_monitoring():
    """Example: Error handling and monitoring with LiteLLM."""
    print("\n🛡️ Error Handling and Monitoring Example")
    print("=" * 50)

    adapter = get_litellm_mcp_adapter()

    try:
        # Health check
        print("\n💓 Checking MCP server health...")
        is_healthy = await adapter.health_check()
        print(f"MCP Server Health: {'✅ Healthy' if is_healthy else '❌ Unhealthy'}")

        if not is_healthy:
            print("Cannot proceed with tool execution - server is unhealthy")
            return

        # Simulate tool execution with error handling
        print("\n🧪 Testing tool execution with error handling...")

        # Test with invalid tool name (should fail gracefully)
        from app.adapters.litellm_mcp import LiteLLMToolCall

        invalid_tool_call = LiteLLMToolCall(
            id="test-call-1",
            function={
                "name": "non-existent-tool",
                "arguments": '{"test": "value"}'
            }
        )

        result = await adapter.call_tool(invalid_tool_call)
        print(f"Invalid tool result: {result.error}")

        # Test with valid arguments but tool-specific error
        # (This depends on your actual tools having error conditions)
        valid_tools = await adapter.list_tools(limit=1)
        if valid_tools:
            # Try to call with invalid arguments (example)
            tool_call = LiteLLMToolCall(
                id="test-call-2",
                function={
                    "name": valid_tools[0].function['name'],
                    "arguments": '{"invalid_param": "test"}'  # Likely to cause validation error
                }
            )

            result = await adapter.call_tool(tool_call)
            if result.error:
                print(f"Expected validation error: {result.error}")
            else:
                print(f"Unexpected success: {result.content}")

        # Performance monitoring example
        print("\n📊 Performance monitoring...")
        import time

        start_time = time.time()
        tools = await adapter.list_tools(limit=10)
        list_time = time.time() - start_time

        start_time = time.time()
        search_results = await adapter.find_tools("test", limit=5)
        search_time = time.time() - start_time

        print(f"Tool listing time: {list_time:.2f}s")
        print(f"Tool search time: {search_time:.2f}s")
        print(f"Total tools available: {len(tools)}")
        print(f"Search results: {len(search_results)}")

    finally:
        await adapter.close()


async def example_production_usage():
    """Example: Production-ready usage pattern with retries and caching."""
    print("\n🏭 Production Usage Example")
    print("=" * 50)

    adapter = get_litellm_mcp_adapter()

    try:
        # Configure LiteLLM for production
        litellm.set_verbose = False  # Disable verbose logging in production
        litellm.api_base = None  # Use default API bases

        # Example: Implementing a tool orchestrator
        class ToolOrchestrator:
            def __init__(self, adapter):
                self.adapter = adapter
                self.tool_cache = {}  # Simple in-memory cache

            async def get_best_tool(self, query: str) -> Dict[str, Any]:
                """Find the best tool for a given query with caching."""
                cache_key = f"search:{query}"

                # Check cache first
                if cache_key in self.tool_cache:
                    print(f"📦 Cache hit for query: {query}")
                    return self.tool_cache[cache_key]

                # Search for tools
                tools = await self.adapter.find_tools(
                    query=query,
                    limit=1,
                    threshold=0.7
                )

                if tools:
                    best_tool = tools[0].dict()
                    self.tool_cache[cache_key] = best_tool
                    print(f"🆕 Found and cached tool for: {query}")
                    return best_tool

                return None

            async def execute_with_retry(
                self,
                tool: Dict[str, Any],
                arguments: Dict[str, Any],
                max_retries: int = 3
            ) -> Any:
                """Execute tool with retry logic."""
                from app.adapters.litellm_mcp import LiteLLMToolCall

                for attempt in range(max_retries):
                    try:
                        tool_call = LiteLLMToolCall(
                            id=f"retry-{attempt}",
                            function={
                                "name": tool['function']['name'],
                                "arguments": json.dumps(arguments)
                            }
                        )

                        result = await self.adapter.call_tool(tool_call)

                        if result.error:
                            raise Exception(f"Tool execution failed: {result.error}")

                        return result.content

                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise

                        wait_time = 2 ** attempt  # Exponential backoff
                        print(f"⚠️ Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)

        # Use the orchestrator
        orchestrator = ToolOrchestrator(adapter)

        # Example workflow
        print("\n🔄 Running production workflow...")

        # Step 1: Find data transformation tool
        print("Step 1: Finding data transformation tool...")
        transform_tool = await orchestrator.get_best_tool("transform json data")

        if not transform_tool:
            print("❌ No suitable tool found")
            return

        print(f"✅ Found tool: {transform_tool['function']['name']}")

        # Step 2: Execute with sample data
        print("Step 2: Executing transformation...")
        sample_data = {
            "input": '{"users": [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]}',
            "operation": "extract_names"
        }

        result = await orchestrator.execute_with_retry(
            transform_tool,
            sample_data
        )

        print(f"✅ Transformation result: {result}")

        # Step 3: Find and use analysis tool
        print("Step 3: Finding analysis tool...")
        analysis_tool = await orchestrator.get_best_tool("analyze data statistics")

        if analysis_tool:
            print(f"✅ Found analysis tool: {analysis_tool['function']['name']}")

            analysis_result = await orchestrator.execute_with_retry(
                analysis_tool,
                {"data": result}
            )
            print(f"✅ Analysis result: {analysis_result}")

        print("✅ Production workflow completed successfully")

    finally:
        await adapter.close()


async def main():
    """Run all examples."""
    print("🚀 LiteLLM + Tool Registry MCP Integration Examples")
    print("=" * 60)

    # Set up environment (in production, use proper secret management)
    os.environ.setdefault("LITELM_MCP_SERVER_URL", "http://localhost:8000")
    os.environ.setdefault("OPENAI_API_KEY", "your-openai-api-key")  # Set your API key

    try:
        # Run examples
        await example_basic_tool_usage()
        await example_advanced_search_and_execution()
        await example_error_handling_and_monitoring()
        await example_production_usage()

    except Exception as e:
        print(f"❌ Error running examples: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())