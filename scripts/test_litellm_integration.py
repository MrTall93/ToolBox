#!/usr/bin/env python3
"""
Test script for LiteLLM + Tool Registry MCP integration.

This script tests the connection between your Tool Registry MCP Server
and an existing LiteLLM deployment.
"""

import asyncio
import httpx
import json
import os
import sys
from typing import Dict, Any, List


class LiteLLMIntegrationTester:
    """Test suite for LiteLLM + Tool Registry integration."""

    def __init__(self, tool_registry_url: str = "http://localhost:8000", api_key: str = None):
        self.tool_registry_url = tool_registry_url.rstrip('/')
        self.api_key = api_key or os.getenv("TOOL_REGISTRY_API_KEY", "your-api-key")
        self.base_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

    async def test_health_check(self) -> bool:
        """Test Tool Registry health endpoint."""
        print("🏥 Testing Tool Registry health check...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.tool_registry_url}/health")

                if response.status_code == 200:
                    health_data = response.json()
                    print(f"✅ Tool Registry is healthy: {health_data.get('status', 'unknown')}")
                    return True
                else:
                    print(f"❌ Health check failed: {response.status_code}")
                    print(f"Response: {response.text}")
                    return False

        except Exception as e:
            print(f"❌ Health check error: {str(e)}")
            return False

    async def test_mcp_tool_listing(self) -> bool:
        """Test MCP tool listing endpoint."""
        print("📋 Testing MCP tool listing...")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.tool_registry_url}/mcp/list_tools",
                    json={"limit": 5},
                    headers=self.base_headers
                )

                if response.status_code == 200:
                    tools_data = response.json()
                    tools = tools_data.get("tools", [])
                    print(f"✅ Found {len(tools)} tools via MCP")

                    # Display first few tools
                    for i, tool in enumerate(tools[:3], 1):
                        print(f"  {i}. {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}")

                    return True
                else:
                    print(f"❌ Tool listing failed: {response.status_code}")
                    print(f"Response: {response.text}")
                    return False

        except Exception as e:
            print(f"❌ Tool listing error: {str(e)}")
            return False

    async def test_mcp_tool_search(self) -> bool:
        """Test MCP tool search endpoint."""
        print("🔍 Testing MCP tool search...")

        test_queries = [
            "calculator",
            "data processing",
            "json parser"
        ]

        try:
            async with httpx.AsyncClient() as client:
                for query in test_queries:
                    print(f"  Searching for: '{query}'")

                    response = await client.post(
                        f"{self.tool_registry_url}/mcp/find_tool",
                        json={"query": query, "limit": 3},
                        headers=self.base_headers
                    )

                    if response.status_code == 200:
                        search_data = response.json()
                        results = search_data.get("results", [])
                        print(f"    Found {len(results)} results")

                        for result in results[:2]:  # Show first 2 results
                            tool = result.get("tool", {})
                            score = result.get("score", 0)
                            print(f"      - {tool.get('name', 'Unknown')} (score: {score:.3f})")
                    else:
                        print(f"    ❌ Search failed: {response.status_code}")
                        return False

                print("✅ All search queries completed successfully")
                return True

        except Exception as e:
            print(f"❌ Tool search error: {str(e)}")
            return False

    async def test_tool_execution(self) -> bool:
        """Test MCP tool execution."""
        print("⚡ Testing MCP tool execution...")

        try:
            # First, find a calculator tool
            async with httpx.AsyncClient() as client:
                search_response = await client.post(
                    f"{self.tool_registry_url}/mcp/find_tool",
                    json={"query": "calculator", "limit": 1},
                    headers=self.base_headers
                )

                if search_response.status_code != 200:
                    print("❌ Could not find calculator tool for execution test")
                    return False

                search_data = search_response.json()
                results = search_data.get("results", [])

                if not results:
                    print("❌ No calculator tools found")
                    return False

                tool_name = results[0]["tool"]["name"]
                print(f"  Found tool: {tool_name}")

                # Test tool execution
                execution_request = {
                    "tool_name": tool_name,
                    "arguments": {
                        "operation": "add",
                        "a": 15,
                        "b": 27
                    },
                    "metadata": {
                        "test_execution": True,
                        "timestamp": "2024-01-01T00:00:00Z"
                    }
                }

                exec_response = await client.post(
                    f"{self.tool_registry_url}/mcp/call_tool",
                    json=execution_request,
                    headers=self.base_headers
                )

                if exec_response.status_code == 200:
                    exec_data = exec_response.json()
                    if exec_data.get("success", False):
                        result = exec_data.get("output", {})
                        execution_time = exec_data.get("execution_time_ms", 0)
                        print(f"  ✅ Tool executed successfully in {execution_time}ms")
                        print(f"  Result: {result}")
                        return True
                    else:
                        error = exec_data.get("error", "Unknown error")
                        print(f"  ❌ Tool execution failed: {error}")
                        return False
                else:
                    print(f"  ❌ Execution request failed: {exec_response.status_code}")
                    print(f"  Response: {exec_response.text}")
                    return False

        except Exception as e:
            print(f"❌ Tool execution error: {str(e)}")
            return False

    async def test_cors_configuration(self) -> bool:
        """Test CORS configuration for LiteLLM."""
        print("🌐 Testing CORS configuration...")

        # Test with LiteLLM origin
        litellm_origin = "http://localhost:4000"

        try:
            async with httpx.AsyncClient() as client:
                # Send OPTIONS request to test CORS
                response = await client.options(
                    f"{self.tool_registry_url}/mcp/list_tools",
                    headers={
                        "Origin": litellm_origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "Content-Type, Authorization"
                    }
                )

                cors_headers = {
                    "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin"),
                    "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods"),
                    "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers")
                }

                print(f"  CORS Headers: {cors_headers}")

                # Check if LiteLLM origin is allowed
                allowed_origin = cors_headers["Access-Control-Allow-Origin"]
                if allowed_origin in [litellm_origin, "*"]:
                    print("✅ CORS is properly configured for LiteLLM")
                    return True
                else:
                    print(f"❌ CORS does not allow LiteLLM origin: {litellm_origin}")
                    return False

        except Exception as e:
            print(f"❌ CORS test error: {str(e)}")
            return False

    async def test_litellm_compatibility(self) -> bool:
        """Test LiteLLM-specific compatibility."""
        print("🔧 Testing LiteLLM compatibility...")

        try:
            # Test that tools are in the correct format for LiteLLM
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.tool_registry_url}/mcp/list_tools",
                    json={"limit": 1},
                    headers=self.base_headers
                )

                if response.status_code != 200:
                    print("❌ Could not retrieve tools for compatibility test")
                    return False

                tools_data = response.json()
                tools = tools_data.get("tools", [])

                if not tools:
                    print("❌ No tools available for compatibility test")
                    return False

                tool = tools[0]

                # Check required LiteLLM fields
                required_fields = ["name", "description", "input_schema"]
                for field in required_fields:
                    if field not in tool:
                        print(f"❌ Tool missing required field for LiteLLM: {field}")
                        return False

                # Check input schema format
                input_schema = tool.get("input_schema", {})
                if not isinstance(input_schema, dict) or "type" not in input_schema:
                    print("❌ Tool input schema is not in valid JSON Schema format")
                    return False

                print("✅ Tools are compatible with LiteLLM format")
                print(f"  Sample tool: {tool['name']}")
                print(f"  Schema: {input_schema.get('type', 'unknown')}")
                return True

        except Exception as e:
            print(f"❌ LiteLLM compatibility test error: {str(e)}")
            return False

    async def run_all_tests(self) -> bool:
        """Run all integration tests."""
        print("🧪 Starting LiteLLM + Tool Registry Integration Tests")
        print("=" * 60)

        tests = [
            ("Health Check", self.test_health_check),
            ("Tool Listing", self.test_mcp_tool_listing),
            ("Tool Search", self.test_mcp_tool_search),
            ("Tool Execution", self.test_tool_execution),
            ("CORS Configuration", self.test_cors_configuration),
            ("LiteLLM Compatibility", self.test_liteLLM_compatibility),
        ]

        results = []
        for test_name, test_func in tests:
            print(f"\n{test_name}")
            print("-" * 40)

            try:
                result = await test_func()
                results.append(result)
                status = "✅ PASSED" if result else "❌ FAILED"
                print(f"Status: {status}")
            except Exception as e:
                print(f"❌ Test crashed: {str(e)}")
                results.append(False)

        print("\n" + "=" * 60)
        print("🏁 Test Results Summary")
        print("=" * 60)

        passed = sum(results)
        total = len(results)

        for i, (test_name, _) in enumerate(tests):
            status = "✅" if results[i] else "❌"
            print(f"{status} {test_name}")

        print(f"\nOverall: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 All tests passed! Your integration is ready for LiteLLM.")
            return True
        else:
            print("⚠️ Some tests failed. Please review the issues above.")
            return False


async def main():
    """Main test runner."""
    # Configuration
    tool_registry_url = os.getenv("TOOL_REGISTRY_URL", "http://localhost:8000")
    api_key = os.getenv("TOOL_REGISTRY_API_KEY")

    if not api_key:
        print("⚠️ Warning: TOOL_REGISTRY_API_KEY not set, using default")
        print("Set the environment variable for proper authentication")

    print(f"Testing against Tool Registry at: {tool_registry_url}")
    print(f"API Key: {'✅ Configured' if api_key else '❌ Not configured'}")

    # Create tester and run tests
    tester = LiteLLMIntegrationTester(
        tool_registry_url=tool_registry_url,
        api_key=api_key
    )

    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())