# TICKET-002: Add call_tool_summarized MCP Tool

## Overview
Add a new MCP tool `call_tool_summarized` to the Toolbox FastMCP server that executes tools and optionally summarizes large outputs to reduce token usage.

## Priority
High

## Estimated Effort
3-4 hours

## Prerequisites
- TICKET-001 (Summarization Service) must be completed first

## Background
The existing `call_tool` function returns full tool output, which can be very large (internal docs, logs, API responses). This new tool allows the agent to request summarized output when the response exceeds a specified token limit.

## Requirements

### Functional Requirements
1. New MCP tool called `call_tool_summarized`
2. Accepts all parameters from `call_tool` plus:
   - `max_tokens`: Maximum tokens before summarization (default: 2000)
   - `summarization_context`: Optional hint about what information is important
3. Returns summarized output if it exceeds `max_tokens`
4. Indicates in response whether summarization occurred

### Non-Functional Requirements
1. Follow existing patterns in `mcp_fastmcp_server.py`
2. Reuse existing `call_tool` logic (don't duplicate code)
3. Add clear docstrings for MCP tool discovery

---

## Implementation Steps

### Step 1: Open the file to modify
Open: `app/mcp_fastmcp_server.py`

### Step 2: Add new import at the top of the file

Find the existing imports section and add:

```python
from app.services.summarization import get_summarization_service
```

Add this near the other imports from `app.` modules.

### Step 3: Add the new MCP tool

Add this new function AFTER the existing `call_tool` function (around line 178):

```python
@mcp.tool
async def call_tool_summarized(
    tool_name: str,
    arguments: dict[str, Any],
    max_tokens: int = 2000,
    summarization_context: str | None = None,
) -> dict[str, Any]:
    """
    Execute a registered tool and summarize the output if it exceeds the token limit.

    Use this instead of call_tool when you expect large outputs (logs, documents,
    API responses) and want to reduce token usage. The output will be automatically
    summarized using an LLM if it exceeds max_tokens.

    Args:
        tool_name: The exact name of the tool to execute (e.g., "confluence:search_docs")
        arguments: Dictionary of arguments matching the tool's input_schema
        max_tokens: Maximum output tokens before summarization kicks in (default: 2000)
                   Set higher (e.g., 5000) if you need more detail
                   Set lower (e.g., 500) for brief summaries
        summarization_context: Optional hint about what information is important
                              Example: "Focus on error messages and stack traces"
                              Example: "Extract only the deployment status"

    Returns:
        Dictionary with:
        - success: Whether the tool executed successfully
        - tool_name: Name of the executed tool
        - output: Tool output (possibly summarized)
        - was_summarized: True if output was summarized, False if original
        - original_tokens_estimate: Estimated tokens of original output (if summarized)
        - execution_time_ms: Tool execution time in milliseconds
        - error: Error message if execution failed
    """
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)
        executor = ToolExecutor()
        summarization_service = get_summarization_service()

        try:
            # Find the tool by name (same as call_tool)
            tool = await registry.get_tool_by_name(tool_name)

            if not tool:
                # Try to find similar tools to suggest
                similar = await registry.find_tool(query=tool_name, limit=3)
                suggestions = [t.name for t, _ in similar] if similar else []

                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' not found",
                    "suggestions": suggestions,
                    "was_summarized": False,
                }

            if not tool.is_active:
                return {
                    "success": False,
                    "error": f"Tool '{tool_name}' is currently inactive",
                    "was_summarized": False,
                }

            # Execute the tool
            result = await executor.execute_tool(
                tool=tool,
                arguments=arguments,
            )

            if not result.get("success"):
                # Don't summarize error responses - return as-is
                return {
                    "success": False,
                    "tool_name": tool_name,
                    "output": result.get("output"),
                    "error": result.get("error_message"),
                    "execution_time_ms": result.get("execution_time_ms"),
                    "was_summarized": False,
                }

            # Get the raw output
            raw_output = result.get("output")

            # Summarize if needed
            processed_output, was_summarized = await summarization_service.summarize_if_needed(
                content=raw_output,
                max_tokens=max_tokens,
                user_query=summarization_context,
                tool_name=tool_name,
            )

            response = {
                "success": True,
                "tool_name": tool_name,
                "output": processed_output,
                "was_summarized": was_summarized,
                "execution_time_ms": result.get("execution_time_ms"),
                "error": None,
            }

            # Add original token estimate if summarized
            if was_summarized:
                from app.services.summarization import estimate_tokens, serialize_output
                original_str = serialize_output(raw_output)
                response["original_tokens_estimate"] = estimate_tokens(original_str)
                response["summarized_tokens_estimate"] = estimate_tokens(processed_output)

            return response

        except Exception as e:
            logger.error(f"Error in call_tool_summarized: {e}")
            return {
                "success": False,
                "tool_name": tool_name,
                "error": str(e),
                "was_summarized": False,
            }
```

---

## Code Explanation for Junior Devs

### What this tool does (step by step):

1. **Receives request**: Agent calls `call_tool_summarized` with tool name, arguments, and optional max_tokens

2. **Finds the tool**: Uses ToolRegistry to look up the tool by name (same as `call_tool`)

3. **Executes the tool**: Uses ToolExecutor to run the tool (same as `call_tool`)

4. **Checks output size**: Passes output to SummarizationService.summarize_if_needed()

5. **Summarizes if needed**: If output > max_tokens, LLM summarizes it

6. **Returns response**: Includes `was_summarized` flag so agent knows what happened

### Key differences from `call_tool`:

| `call_tool` | `call_tool_summarized` |
|-------------|----------------------|
| Returns raw output | Returns raw OR summarized output |
| No size control | `max_tokens` parameter controls size |
| No context hints | `summarization_context` guides summary |
| No summarization flag | `was_summarized` tells agent what happened |

### Why we don't modify `call_tool`:

1. **Backward compatibility**: Existing integrations expect raw output
2. **Explicit choice**: Agent should consciously choose summarization
3. **Transparency**: Clear when summarization happened

---

## Testing Checklist

### Manual Testing

1. **Test with small output** (should NOT summarize):
```json
{
  "tool_name": "some_tool",
  "arguments": {"query": "simple"},
  "max_tokens": 5000
}
```
Expected: `was_summarized: false`

2. **Test with large output** (should summarize):
```json
{
  "tool_name": "internal_docs:search",
  "arguments": {"query": "deployment guide"},
  "max_tokens": 500
}
```
Expected: `was_summarized: true`, output is shorter

3. **Test with context**:
```json
{
  "tool_name": "k8s:get_pod_logs",
  "arguments": {"pod": "api-server-xyz"},
  "max_tokens": 1000,
  "summarization_context": "Focus on error messages"
}
```
Expected: Summary focuses on errors

4. **Test tool not found**:
```json
{
  "tool_name": "nonexistent_tool",
  "arguments": {}
}
```
Expected: `success: false`, `suggestions` array

5. **Test tool execution error**:
Use a tool that will fail, verify error is returned unsummarized

### Unit Tests to Write

Create `tests/test_call_tool_summarized.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

# Test 1: Small output not summarized
@pytest.mark.asyncio
async def test_small_output_not_summarized():
    # Mock tool execution returning small output
    # Assert was_summarized is False
    pass

# Test 2: Large output is summarized
@pytest.mark.asyncio
async def test_large_output_summarized():
    # Mock tool execution returning large output
    # Assert was_summarized is True
    pass

# Test 3: Error responses not summarized
@pytest.mark.asyncio
async def test_error_not_summarized():
    # Mock tool execution failing
    # Assert was_summarized is False
    pass

# Test 4: Tool not found returns suggestions
@pytest.mark.asyncio
async def test_tool_not_found_suggestions():
    # Call with nonexistent tool
    # Assert suggestions array exists
    pass
```

---

## Files to Modify

1. `app/mcp_fastmcp_server.py` - Add the new tool function
2. `tests/test_call_tool_summarized.py` - Create new test file

## Dependencies

- TICKET-001 must be completed (SummarizationService)

## Related Tickets

- TICKET-001: Create Summarization Service (prerequisite)
- TICKET-003: Add Summarization Configuration Settings (optional enhancement)
