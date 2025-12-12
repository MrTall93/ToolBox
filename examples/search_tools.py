#!/usr/bin/env python3
"""
Example script to search for tools using semantic search.

This script demonstrates how to:
1. Perform semantic search with natural language queries
2. Use hybrid search (vector + text)
3. Find similar tools
4. Filter by category and threshold

Usage:
    python examples/search_tools.py "calculate numbers"
    python examples/search_tools.py "text manipulation"
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


async def search_example(query: str):
    """Perform semantic search."""
    print(f"SEARCH: Tool Registry - Semantic Search Example")
    print("=" * 50)
    print(f"Query: '{query}'")
    print()

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

        # Pure vector search
        print("Vector Search Results:")
        print("-" * 50)
        results = await registry.find_tool(
            query=query,
            limit=5,
            threshold=0.5,
            use_hybrid=False,
        )

        if not results:
            print("   No results found")
        else:
            for i, (tool, score) in enumerate(results, 1):
                print(f"\n{i}. {tool.name} (score: {score:.3f})")
                print(f"   Category: {tool.category}")
                print(f"   Description: {tool.description}")
                print(f"   Tags: {', '.join(tool.tags)}")

        # Hybrid search (vector + text)
        print("\n\n🔀 Hybrid Search Results (Vector + Text):")
        print("-" * 50)
        results = await registry.find_tool(
            query=query,
            limit=5,
            threshold=0.3,
            use_hybrid=True,
        )

        if not results:
            print("   No results found")
        else:
            for i, (tool, score) in enumerate(results, 1):
                print(f"\n{i}. {tool.name} (score: {score:.3f})")
                print(f"   Category: {tool.category}")
                print(f"   Description: {tool.description}")

        # Find similar tools to the top result
        if results:
            top_tool = results[0][0]
            print(f"\n\n🔗 Tools Similar to '{top_tool.name}':")
            print("-" * 50)

            similar = await registry.find_similar_tools(
                tool_id=top_tool.id,
                limit=3,
            )

            if not similar:
                print("   No similar tools found")
            else:
                for i, (tool, score) in enumerate(similar, 1):
                    print(f"\n{i}. {tool.name} (similarity: {score:.3f})")
                    print(f"   Description: {tool.description}")

    await engine.dispose()
    print("\n✅ Search complete!")


async def list_all_tools():
    """List all available tools."""
    print("📋 All Available Tools")
    print("=" * 50)

    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        registry = ToolRegistry(session=session)

        # List all tools grouped by category
        tools = await registry.list_tools(active_only=True, limit=100)

        # Group by category
        by_category = {}
        for tool in tools:
            if tool.category not in by_category:
                by_category[tool.category] = []
            by_category[tool.category].append(tool)

        for category, category_tools in sorted(by_category.items()):
            print(f"\n📁 {category.upper()}:")
            for tool in category_tools:
                print(f"   • {tool.name:20} - {tool.description[:60]}...")

        print(f"\n📊 Total: {len(tools)} tools across {len(by_category)} categories")

    await engine.dispose()


async def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        await search_example(query)
    else:
        print("Usage: python search_tools.py <query>")
        print("       python search_tools.py --list")
        print()
        print("Examples:")
        print("  python search_tools.py 'calculate numbers'")
        print("  python search_tools.py 'manipulate text'")
        print("  python search_tools.py --list")
        print()

        # Show example with default query
        if len(sys.argv) == 1:
            print("Running example with default query...\n")
            await search_example("tool for math operations")


if __name__ == "__main__":
    if "--list" in sys.argv:
        asyncio.run(list_all_tools())
    else:
        asyncio.run(main())
