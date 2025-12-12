#!/usr/bin/env python3
"""
Example script to register tools in the registry.

This script demonstrates how to:
1. Connect to the database
2. Create a ToolRegistry instance
3. Register multiple tools with auto-embedding

Usage:
    python examples/register_tools.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.registry import ToolRegistry
from app.tools.implementations.calculator import TOOL_METADATA as CALCULATOR_METADATA
from app.tools.implementations.string_tools import STRING_TOOLS


async def main():
    """Register example tools."""
    print("🔧 Tool Registry - Registration Example")
    print("=" * 50)

    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
    )

    # Create session factory
    async_session = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session() as session:
        registry = ToolRegistry(session=session)

        # Register calculator tool
        print("\n📊 Registering Calculator tool...")
        try:
            calculator = await registry.register_tool(
                name=CALCULATOR_METADATA["name"],
                description=CALCULATOR_METADATA["description"],
                category=CALCULATOR_METADATA["category"],
                tags=CALCULATOR_METADATA["tags"],
                input_schema=CALCULATOR_METADATA["input_schema"],
                output_schema=CALCULATOR_METADATA["output_schema"],
                implementation_type=CALCULATOR_METADATA["implementation_type"],
                implementation_code="app.tools.implementations.calculator.execute",
                version=CALCULATOR_METADATA["version"],
                auto_embed=True,
            )
            print(f"✅ Registered: {calculator.name} (ID: {calculator.id})")
        except ValueError as e:
            print(f"WARNING: Calculator already registered: {e}")

        # Register string tools
        print("\n📝 Registering String tools...")
        for tool_meta in STRING_TOOLS:
            try:
                tool = await registry.register_tool(
                    name=tool_meta["name"],
                    description=tool_meta["description"],
                    category=tool_meta["category"],
                    tags=tool_meta["tags"],
                    input_schema=tool_meta["input_schema"],
                    output_schema=tool_meta["output_schema"],
                    implementation_type=tool_meta["implementation_type"],
                    implementation_code=tool_meta["implementation_code"],
                    version=tool_meta["version"],
                    auto_embed=True,
                )
                print(f"✅ Registered: {tool.name} (ID: {tool.id})")
            except ValueError as e:
                print(f"WARNING: {tool_meta['name']} already registered")

        # Get tool statistics
        print("\n📊 Tool Registry Statistics:")
        tools = await registry.list_tools(active_only=True, limit=100)
        print(f"   Total active tools: {len(tools)}")

        # Count indexed tools
        from app.registry import VectorStore

        vector_store = VectorStore(session)
        indexed_count = await vector_store.count_indexed_tools()
        print(f"   Tools with embeddings: {indexed_count}")

        # List all tools
        print("\n📋 Registered Tools:")
        for tool in tools:
            print(f"   • {tool.name:20} - {tool.description[:60]}...")

    await engine.dispose()
    print("\n✅ Registration complete!")


if __name__ == "__main__":
    asyncio.run(main())
