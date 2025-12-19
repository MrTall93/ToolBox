#!/usr/bin/env python3
"""
Demonstration of the call_tool_summarized feature.

This example shows how to use the new call_tool_summarized MCP tool to
automatically summarize large tool outputs to reduce token usage.
"""

import asyncio
import json
from app.services.summarization import get_summarization_service, estimate_tokens


async def demo_token_estimation():
    """Demonstrate token estimation functionality."""
    print("=" * 60)
    print("DEMO: Token Estimation")
    print("=" * 60)

    service = get_summarization_service()

    # Small text
    small_text = "This is a small piece of text that won't trigger summarization."
    tokens = estimate_tokens(small_text)
    print(f"Small text ({len(small_text)} chars): ~{tokens} tokens")

    # Large text (simulating log output)
    large_text = "Error log entry: " * 1000
    tokens = estimate_tokens(large_text)
    print(f"Large text ({len(large_text)} chars): ~{tokens} tokens")

    # Demonstrate summarization threshold
    print(f"\nWith max_tokens=2000:")
    print(f"Small text: {'WILL NOT' if tokens < 2000 else 'WILL'} be summarized")
    print(f"Large text: {'WILL NOT' if tokens < 2000 else 'WILL'} be summarized")


async def demo_summarization_decision():
    """Demonstrate the summarization decision logic."""
    print("\n" + "=" * 60)
    print("DEMO: Summarization Decision Logic")
    print("=" * 60)

    service = get_summarization_service()

    # Example outputs
    small_output = {
        "status": "success",
        "data": {"id": 123, "name": "test"}
    }

    large_output = {
        "logs": [
            f"[INFO] Processing item {i}: {'x' * 100}"
            for i in range(500)
        ]
    }

    print("\n1. Small output test:")
    print(f"   Output size: {len(json.dumps(small_output))} chars")
    processed, was_summarized = await service.summarize_if_needed(
        content=small_output,
        max_tokens=1000
    )
    print(f"   Was summarized: {was_summarized}")
    print(f"   Result length: {len(processed)} chars")

    print("\n2. Large output test:")
    print(f"   Output size: {len(json.dumps(large_output))} chars")

    # Since we don't have a real LiteLLM instance, this will fall back to truncation
    processed, was_summarized = await service.summarize_if_needed(
        content=large_output,
        max_tokens=500
    )
    print(f"   Was summarized: {was_summarized}")
    print(f"   Result length: {len(processed)} chars")
    print(f"   Result preview: {processed[:200]}...")


def demo_mcp_tool_usage():
    """Show example usage of the call_tool_summarized MCP tool."""
    print("\n" + "=" * 60)
    print("DEMO: MCP Tool Usage Examples")
    print("=" * 60)

    print("\nExample 1: Getting brief summary of logs")
    example1 = {
        "tool": "k8s:get_pod_logs",
        "arguments": {"pod": "api-server-xyz", "namespace": "default"},
        "max_tokens": 500,
        "summarization_context": "Focus on errors and warnings"
    }
    print(json.dumps(example1, indent=2))

    print("\nExample 2: Searching documentation with detailed summary")
    example2 = {
        "tool": "confluence:search_docs",
        "arguments": {"query": "deployment guide", "space": "DEV"},
        "max_tokens": 2000,
        "summarization_context": "Extract deployment steps and requirements"
    }
    print(json.dumps(example2, indent=2))

    print("\nExample 3: Analyzing large dataset")
    example3 = {
        "tool": "analytics:query_metrics",
        "arguments": {"metric": "response_time", "time_range": "7d"},
        "max_tokens": 1000,
        "summarization_context": "Focus on outliers and trends"
    }
    print(json.dumps(example3, indent=2))

    print("\nExample response format:")
    response = {
        "success": True,
        "tool_name": "k8s:get_pod_logs",
        "output": "Summary: Pod processed 10,000 requests. Found 3 HTTP 500 errors at 14:32, 15:01, and 15:45. Memory usage peaked at 85% but recovered.",
        "was_summarized": True,
        "original_tokens_estimate": 8750,
        "summarized_tokens_estimate": 45,
        "execution_time_ms": 234,
        "error": None
    }
    print(json.dumps(response, indent=2))


def demo_configuration():
    """Show configuration options."""
    print("\n" + "=" * 60)
    print("DEMO: Configuration Options")
    print("=" * 60)

    print("\nEnvironment variables for summarization:")
    config_vars = [
        ("SUMMARIZATION_ENABLED", "true", "Enable/disable summarization"),
        ("SUMMARIZATION_MODEL", "claude-3-5-haiku-latest", "Model for summarization"),
        ("SUMMARIZATION_DEFAULT_MAX_TOKENS", "2000", "Default token threshold"),
        ("SUMMARIZATION_TIMEOUT", "30.0", "Timeout in seconds"),
        ("SUMMARIZATION_MAX_INPUT_CHARS", "50000", "Max input characters"),
    ]

    for var, default, desc in config_vars:
        print(f"  {var:<35} (default: {default:<20}) - {desc}")

    print("\nExample .env configuration:")
    print("""
# Summarization Settings
SUMMARIZATION_ENABLED=true
SUMMARIZATION_MODEL=claude-3-5-haiku-latest
SUMMARIZATION_DEFAULT_MAX_TOKENS=2000
SUMMARIZATION_TIMEOUT=30.0
""")


async def main():
    """Run all demonstrations."""
    print("Summarization Feature Demonstration")
    print("=================================")
    print("This demo shows the new call_tool_summarized feature that")
    print("automatically summarizes large tool outputs to save tokens.")

    await demo_token_estimation()
    await demo_summarization_decision()
    demo_mcp_tool_usage()
    demo_configuration()

    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nKey Benefits:")
    print("• 80-90% reduction in token usage for large outputs")
    print("• Preserves important information while reducing verbosity")
    print("• Configurable thresholds and summarization context")
    print("• Falls back to truncation if summarization fails")
    print("\nTo use in your agent:")
    print("1. Use call_tool_summarized instead of call_tool for large outputs")
    print("2. Set appropriate max_tokens based on your needs")
    print("3. Provide summarization_context to guide the summary")


if __name__ == "__main__":
    asyncio.run(main())