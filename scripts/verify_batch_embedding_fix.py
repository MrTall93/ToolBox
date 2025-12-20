#!/usr/bin/env python3
"""
Verification script for batch embedding fix.

This script tests the batch embedding functionality with a real embedding service
to verify that the bug fix works correctly in production.

Usage:
    python scripts/verify_batch_embedding_fix.py [--endpoint URL] [--api-key KEY]

Examples:
    # Use default config from environment
    python scripts/verify_batch_embedding_fix.py

    # Override endpoint
    python scripts/verify_batch_embedding_fix.py --endpoint http://localhost:1234/v1/embeddings

    # Test with OpenAI
    python scripts/verify_batch_embedding_fix.py \\
        --endpoint https://api.openai.com/v1/embeddings \\
        --api-key sk-...
"""
import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.registry.embedding_client import EmbeddingClient
from app.config import settings


async def test_batch_embedding(
    endpoint_url: str = None,
    api_key: str = None
) -> dict:
    """
    Test batch embedding with real embedding service.

    Args:
        endpoint_url: Override endpoint URL
        api_key: Override API key

    Returns:
        Dict with test results
    """
    client = EmbeddingClient(
        endpoint_url=endpoint_url,
        api_key=api_key
    )

    print(f"\n{'='*60}")
    print("Batch Embedding Fix Verification")
    print(f"{'='*60}")
    print(f"Endpoint: {client.endpoint_url}")
    print(f"Model: {client.model}")
    print(f"Expected dimension: {client.dimension}")
    print(f"{'='*60}\n")

    results = {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "errors": []
    }

    # Test 1: Health check
    print("Test 1: Health Check")
    print("-" * 40)
    results["total_tests"] += 1

    try:
        is_healthy = await client.health_check()
        if is_healthy:
            print("✓ Embedding service is healthy")
            results["passed"] += 1
        else:
            print("✗ Embedding service is not healthy")
            results["failed"] += 1
            results["errors"].append("Health check failed")
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        results["failed"] += 1
        results["errors"].append(f"Health check error: {e}")
        return results

    print()

    # Test 2: Single text embedding
    print("Test 2: Single Text Embedding")
    print("-" * 40)
    results["total_tests"] += 1

    try:
        text = "This is a test"
        embedding = await client.embed_text(text)

        if len(embedding) == client.dimension:
            print(f"✓ Generated embedding with correct dimension: {len(embedding)}")
            print(f"  First 5 values: {embedding[:5]}")
            results["passed"] += 1
        else:
            print(f"✗ Wrong dimension: expected {client.dimension}, got {len(embedding)}")
            results["failed"] += 1
            results["errors"].append(f"Wrong dimension: {len(embedding)}")

    except Exception as e:
        print(f"✗ Single text embedding failed: {e}")
        results["failed"] += 1
        results["errors"].append(f"Single text error: {e}")

    print()

    # Test 3: Batch embedding with multiple texts
    print("Test 3: Batch Embedding (Multiple Texts)")
    print("-" * 40)
    results["total_tests"] += 1

    try:
        texts = [
            "The quick brown fox",
            "jumps over the lazy dog",
            "This is a test sentence"
        ]
        embeddings = await client.embed_batch(texts)

        # Check count
        if len(embeddings) != len(texts):
            print(f"✗ Wrong count: expected {len(texts)}, got {len(embeddings)}")
            results["failed"] += 1
            results["errors"].append(f"Wrong count: {len(embeddings)}")
        else:
            print(f"✓ Correct number of embeddings: {len(embeddings)}")

            # Check dimensions
            all_correct_dim = all(len(emb) == client.dimension for emb in embeddings)
            if all_correct_dim:
                print(f"✓ All embeddings have correct dimension: {client.dimension}")

                # Check uniqueness
                if embeddings[0] != embeddings[1] != embeddings[2]:
                    print("✓ All embeddings are unique (different texts produce different vectors)")
                    results["passed"] += 1

                    # Show sample values
                    print(f"\n  Embedding 1 (first 5): {embeddings[0][:5]}")
                    print(f"  Embedding 2 (first 5): {embeddings[1][:5]}")
                    print(f"  Embedding 3 (first 5): {embeddings[2][:5]}")
                else:
                    print("✗ Embeddings are not unique (bug not fixed!)")
                    results["failed"] += 1
                    results["errors"].append("Non-unique embeddings")
            else:
                print(f"✗ Some embeddings have wrong dimensions")
                results["failed"] += 1
                results["errors"].append("Wrong dimensions in batch")

    except Exception as e:
        print(f"✗ Batch embedding failed: {e}")
        results["failed"] += 1
        results["errors"].append(f"Batch error: {e}")

    print()

    # Test 4: Large batch
    print("Test 4: Large Batch (10 texts)")
    print("-" * 40)
    results["total_tests"] += 1

    try:
        texts = [f"Test sentence number {i}" for i in range(10)]
        embeddings = await client.embed_batch(texts)

        if len(embeddings) == 10:
            print(f"✓ Processed 10 texts successfully")

            # Check all unique
            unique_embeddings = len(set(tuple(emb) for emb in embeddings))
            if unique_embeddings == 10:
                print(f"✓ All 10 embeddings are unique")
                results["passed"] += 1
            else:
                print(f"✗ Only {unique_embeddings}/10 embeddings are unique")
                results["failed"] += 1
                results["errors"].append(f"Non-unique embeddings in large batch")
        else:
            print(f"✗ Wrong count: expected 10, got {len(embeddings)}")
            results["failed"] += 1
            results["errors"].append(f"Wrong large batch count")

    except Exception as e:
        print(f"✗ Large batch failed: {e}")
        results["failed"] += 1
        results["errors"].append(f"Large batch error: {e}")

    print()

    # Test 5: Empty batch
    print("Test 5: Empty Batch")
    print("-" * 40)
    results["total_tests"] += 1

    try:
        embeddings = await client.embed_batch([])

        if embeddings == []:
            print("✓ Empty batch returns empty list")
            results["passed"] += 1
        else:
            print(f"✗ Empty batch returned {len(embeddings)} embeddings")
            results["failed"] += 1
            results["errors"].append("Empty batch not handled")

    except Exception as e:
        print(f"✗ Empty batch test failed: {e}")
        results["failed"] += 1
        results["errors"].append(f"Empty batch error: {e}")

    print()

    return results


def print_summary(results: dict):
    """Print test summary."""
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    print(f"Total tests:  {results['total_tests']}")
    print(f"✓ Passed:     {results['passed']}")
    print(f"✗ Failed:     {results['failed']}")
    print(f"{'='*60}")

    if results['failed'] > 0:
        print("\nErrors:")
        for error in results['errors']:
            print(f"  - {error}")
        print()
        print("⚠️  Some tests failed. The batch embedding may not be working correctly.")
        print("   Please review the errors above.")
        sys.exit(1)
    else:
        print("\n✅ All tests passed! Batch embedding is working correctly.")
        print("   The bug fix has been verified successfully.")
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Verify batch embedding fix with real embedding service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default config
  python scripts/verify_batch_embedding_fix.py

  # Test with local LM Studio
  python scripts/verify_batch_embedding_fix.py \\
      --endpoint http://localhost:1234/v1/embeddings

  # Test with OpenAI
  python scripts/verify_batch_embedding_fix.py \\
      --endpoint https://api.openai.com/v1/embeddings \\
      --api-key sk-...
        """
    )

    parser.add_argument(
        "--endpoint",
        type=str,
        default=None,
        help=f"Embedding endpoint URL (default: {settings.EMBEDDING_ENDPOINT_URL})"
    )

    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for embedding service (default: from environment)"
    )

    args = parser.parse_args()

    async def run():
        results = await test_batch_embedding(
            endpoint_url=args.endpoint,
            api_key=args.api_key
        )
        print_summary(results)

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
