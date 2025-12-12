#!/bin/bash
# MCP API Usage Examples
# Demonstrates how to use the MCP protocol endpoints with curl

set -e

API_URL="${API_URL:-http://localhost:8000}"

echo "MCP MCP API Examples"
echo "================================"
echo "API URL: $API_URL"
echo

# Check if server is running
echo "1. Health Check"
echo "-----------------------------------"
curl -s "$API_URL/health" | python3 -m json.tool
echo
echo

# List all tools
echo "2. List All Tools"
echo "-----------------------------------"
curl -s -X POST "$API_URL/mcp/list_tools" \
  -H "Content-Type: application/json" \
  -d '{
    "limit": 10,
    "offset": 0,
    "active_only": true
  }' | python3 -m json.tool
echo
echo

# Find tools with semantic search
echo "3. Find Tool - Semantic Search"
echo "-----------------------------------"
echo "Query: 'calculate numbers'"
curl -s -X POST "$API_URL/mcp/find_tool" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "calculate numbers",
    "limit": 3,
    "threshold": 0.5,
    "use_hybrid": true
  }' | python3 -m json.tool
echo
echo

# Find tools - text manipulation
echo "4. Find Tool - Text Tools"
echo "-----------------------------------"
echo "Query: 'manipulate text strings'"
curl -s -X POST "$API_URL/mcp/find_tool" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "manipulate text strings",
    "limit": 3,
    "threshold": 0.5,
    "use_hybrid": true
  }' | python3 -m json.tool
echo
echo

# Register a new tool
echo "5. Register New Tool"
echo "-----------------------------------"
echo "Registering: uuid_generator"
curl -s -X POST "$API_URL/admin/tools" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "uuid_generator",
    "description": "Generate a random UUID (Universally Unique Identifier)",
    "category": "utility",
    "tags": ["uuid", "generator", "random", "identifier"],
    "input_schema": {
      "type": "object",
      "properties": {
        "version": {
          "type": "integer",
          "enum": [1, 4],
          "default": 4,
          "description": "UUID version (1 or 4)"
        }
      }
    },
    "output_schema": {
      "type": "object",
      "properties": {
        "uuid": {"type": "string"}
      }
    },
    "implementation_type": "python_function",
    "version": "1.0.0",
    "auto_embed": true
  }' | python3 -m json.tool
echo
echo

# Get tool details
echo "6. Get Tool Details"
echo "-----------------------------------"
echo "Getting details for tool ID: 1"
curl -s "$API_URL/admin/tools/1" | python3 -m json.tool
echo
echo

# Get tool stats
echo "7. Get Tool Statistics"
echo "-----------------------------------"
echo "Getting stats for tool ID: 1"
curl -s "$API_URL/admin/tools/1/stats" | python3 -m json.tool
echo
echo

# Call a tool
echo "8. Call Tool"
echo "-----------------------------------"
echo "Calling: calculator (add 5 + 3)"
curl -s -X POST "$API_URL/mcp/call_tool" \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "calculator",
    "arguments": {
      "operation": "add",
      "a": 5,
      "b": 3
    }
  }' | python3 -m json.tool
echo
echo

echo "✅ Examples complete!"
echo
echo "TIP: Tips:"
echo "  - Explore interactive docs: $API_URL/docs"
echo "  - View all endpoints: $API_URL/"
echo "  - Health check: $API_URL/health"
