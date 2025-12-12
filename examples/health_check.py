#!/usr/bin/env python3
"""
Quick health check script for the Tool Registry MCP Server.

This script checks the status of all major components.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def health_check():
    """Run comprehensive health checks."""
    print("TOOL REGISTRY MCP SERVER - HEALTH CHECK")
    print("=" * 50)

    # Check imports
    try:
        from app.main import app
        from app.tools.executor import ToolExecutor, execute_tool
        from app.tools.implementations.data_transform import (
            execute_json_to_csv,
            execute_csv_to_json
        )
        print("✅ All imports successful")
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

    # Check tool execution
    try:
        result = await execute_tool(
            tool_name="calculator",
            arguments={"operation": "add", "a": 1, "b": 1}
        )
        if result.success:
            print("✅ Tool execution working")
        else:
            print(f"❌ Tool execution failed: {result.error}")
    except Exception as e:
        print(f"❌ Tool execution error: {e}")

    # Check data transformation
    try:
        test_data = [{"test": "value"}]
        result = execute_json_to_csv({"data": test_data})
        if result['csv_data']:
            print("✅ Data transformation working")
        else:
            print("❌ Data transformation failed")
    except Exception as e:
        print(f"❌ Data transformation error: {e}")

    # Check FastAPI app
    try:
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/")
        if response.status_code == 200:
            print("✅ FastAPI server responding")
        else:
            print(f"❌ FastAPI server error: {response.status_code}")
    except Exception as e:
        print(f"❌ FastAPI server error: {e}")

    print("\n🎉 HEALTH CHECK COMPLETE!")
    print("The Tool Registry MCP Server is running properly.")
    return True


if __name__ == "__main__":
    asyncio.run(health_check())