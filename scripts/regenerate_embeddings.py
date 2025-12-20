#!/usr/bin/env python3
"""
Regenerate embeddings for all tools in the database.

This script is useful after:
- Running the embedding dimension migration
- Changing embedding models
- Fixing corrupted embeddings

Usage:
    python scripts/regenerate_embeddings.py [--concurrent N] [--active-only] [--category CATEGORY]

Examples:
    # Regenerate all active tools sequentially
    python scripts/regenerate_embeddings.py

    # Regenerate with 10 concurrent workers
    python scripts/regenerate_embeddings.py --concurrent 10

    # Regenerate only math category tools
    python scripts/regenerate_embeddings.py --category math

    # Regenerate all tools including inactive
    python scripts/regenerate_embeddings.py --active-only false
"""
import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import Tool
from app.registry import ToolRegistry
from app.config import settings


async def regenerate_tool_embedding(
    tool_id: int,
    tool_name: str,
    semaphore: asyncio.Semaphore = None
) -> tuple[bool, str]:
    """
    Regenerate embedding for a single tool.

    Args:
        tool_id: Tool ID
        tool_name: Tool name (for logging)
        semaphore: Optional semaphore for concurrency control

    Returns:
        Tuple of (success, message)
    """
    async def _regenerate():
        async with AsyncSessionLocal() as session:
            try:
                registry = ToolRegistry(session=session)
                await registry.update_tool_embedding(tool_id)
                return True, f"✓ {tool_name}"
            except Exception as e:
                return False, f"✗ {tool_name}: {str(e)}"

    if semaphore:
        async with semaphore:
            return await _regenerate()
    else:
        return await _regenerate()


async def regenerate_all_embeddings(
    active_only: bool = True,
    category: str = None,
    max_concurrent: int = 1
) -> dict:
    """
    Regenerate embeddings for all matching tools.

    Args:
        active_only: Only regenerate for active tools
        category: Only regenerate for specific category
        max_concurrent: Maximum concurrent regeneration tasks

    Returns:
        Dictionary with statistics
    """
    async with AsyncSessionLocal() as session:
        # Build query
        query = select(Tool.id, Tool.name, Tool.category)

        if active_only:
            query = query.where(Tool.is_active == True)

        if category:
            query = query.where(Tool.category == category)

        # Get tools
        result = await session.execute(query)
        tools = result.all()

        if not tools:
            print("No tools found matching criteria")
            return {
                "total": 0,
                "success": 0,
                "failed": 0,
                "skipped": 0
            }

        print(f"\n{'='*60}")
        print(f"Regenerating embeddings for {len(tools)} tools")
        print(f"Configuration:")
        print(f"  - Embedding dimension: {settings.EMBEDDING_DIMENSION}")
        print(f"  - Embedding model: {settings.EMBEDDING_MODEL}")
        print(f"  - Concurrent workers: {max_concurrent}")
        print(f"  - Active only: {active_only}")
        if category:
            print(f"  - Category filter: {category}")
        print(f"{'='*60}\n")

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent) if max_concurrent > 1 else None

        # Create tasks
        tasks = [
            regenerate_tool_embedding(tool.id, tool.name, semaphore)
            for tool in tools
        ]

        # Execute with progress tracking
        stats = {
            "total": len(tools),
            "success": 0,
            "failed": 0,
            "skipped": 0
        }

        # Process results as they complete
        for i, coro in enumerate(asyncio.as_completed(tasks), 1):
            success, message = await coro
            print(f"[{i}/{len(tools)}] {message}")

            if success:
                stats["success"] += 1
            else:
                stats["failed"] += 1

        return stats


async def verify_embedding_service() -> bool:
    """
    Verify that the embedding service is reachable.

    Returns:
        True if service is healthy, False otherwise
    """
    from app.registry.embedding_client import get_embedding_client

    try:
        client = get_embedding_client()
        is_healthy = await client.health_check()

        if is_healthy:
            print("✓ Embedding service is healthy")
            # Test embedding generation
            test_embedding = await client.embed_text("test")
            if len(test_embedding) == settings.EMBEDDING_DIMENSION:
                print(f"✓ Embedding dimension is correct: {len(test_embedding)}")
                return True
            else:
                print(f"✗ Embedding dimension mismatch!")
                print(f"  Expected: {settings.EMBEDDING_DIMENSION}")
                print(f"  Got: {len(test_embedding)}")
                return False
        else:
            print("✗ Embedding service is not healthy")
            return False

    except Exception as e:
        print(f"✗ Failed to connect to embedding service: {e}")
        print(f"  Endpoint: {settings.EMBEDDING_ENDPOINT_URL}")
        return False


def print_stats(stats: dict):
    """Print regeneration statistics."""
    print(f"\n{'='*60}")
    print("Regeneration Complete")
    print(f"{'='*60}")
    print(f"Total tools:     {stats['total']}")
    print(f"✓ Successful:    {stats['success']}")
    print(f"✗ Failed:        {stats['failed']}")
    print(f"⊘ Skipped:       {stats['skipped']}")
    print(f"{'='*60}\n")

    if stats['failed'] > 0:
        print("⚠️  Some tools failed to regenerate.")
        print("   Check the error messages above and retry those tools individually.")
        sys.exit(1)
    else:
        print("✅ All tools successfully regenerated!")
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Regenerate embeddings for tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Regenerate all active tools
  python scripts/regenerate_embeddings.py

  # Use 10 concurrent workers for faster processing
  python scripts/regenerate_embeddings.py --concurrent 10

  # Regenerate only math category
  python scripts/regenerate_embeddings.py --category math

  # Regenerate all tools including inactive
  python scripts/regenerate_embeddings.py --active-only false
        """
    )

    parser.add_argument(
        "--concurrent",
        type=int,
        default=1,
        help="Number of concurrent workers (default: 1)"
    )

    parser.add_argument(
        "--active-only",
        type=lambda x: x.lower() != 'false',
        default=True,
        help="Only regenerate active tools (default: true)"
    )

    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Only regenerate tools in this category"
    )

    parser.add_argument(
        "--skip-health-check",
        action="store_true",
        help="Skip embedding service health check"
    )

    args = parser.parse_args()

    # Validate concurrent workers
    if args.concurrent < 1:
        print("Error: --concurrent must be at least 1")
        sys.exit(1)

    if args.concurrent > 50:
        print("Warning: Using more than 50 concurrent workers may overwhelm the embedding service")
        response = input("Continue anyway? [y/N]: ")
        if response.lower() != 'y':
            sys.exit(0)

    async def run():
        # Verify embedding service
        if not args.skip_health_check:
            print("\nVerifying embedding service...")
            is_healthy = await verify_embedding_service()
            if not is_healthy:
                print("\n⚠️  Embedding service is not available or misconfigured.")
                print("   Please check your EMBEDDING_ENDPOINT_URL and EMBEDDING_API_KEY settings.")
                response = input("\nContinue anyway? [y/N]: ")
                if response.lower() != 'y':
                    sys.exit(1)

        # Regenerate embeddings
        stats = await regenerate_all_embeddings(
            active_only=args.active_only,
            category=args.category,
            max_concurrent=args.concurrent
        )

        # Print results
        print_stats(stats)

    # Run async main
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
