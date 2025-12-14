# FastMCP Server Documentation

Toolbox provides a high-performance MCP (Model Context Protocol) server built with the fastmcp framework, exposing its tool registry to external applications via the standardized MCP protocol.

## Overview

The FastMCP server allows external applications to:
- Discover all available tools in the Toolbox registry
- Execute tools with proper argument validation
- Access tool metadata and descriptions
- Use prompts for tool discovery
- Read resources like tool categories
- Perform semantic search for tools

## Key Features

- **High Performance**: Built with fastmcp for optimal speed
- **Full MCP Compliance**: Implements the complete MCP protocol
- **Semantic Search**: Natural language tool discovery
- **External Server Sync**: Automatically syncs tools from external MCP servers
- **Multiple Transport Modes**: Supports stdio, HTTP, and SSE transports
- **Tool Registry Integration**: Direct access to all registered tools

## Running the FastMCP Server

### Method 1: Direct stdio Execution

```bash
# Using Docker
docker run --rm -i \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname" \
  -e EMBEDDING_ENDPOINT_URL="http://embedding-service:port/v1/embeddings" \
  -e EMBEDDING_API_KEY="your-key" \
  toolbox:mcp python3.9 -m app.mcp_fastmcp_server

# Using Python directly
python3.9 -m app.mcp_fastmcp_server
```

### Method 2: HTTP Server Mode

```bash
# Run the FastMCP server in HTTP mode
python3.9 -m app.mcp_http_server
```

### Method 3: With LiteLLM Integration

Add to your LiteLLM configuration:

```yaml
model_list:
  # ... your models

mcp_servers:
  - name: "toolbox"
    description: "Tool Registry with semantic search capabilities"
    command: ["python3.9", "-m", "app.mcp_fastmcp_server"]
    args: []
    cwd: "/app"
    env:
      DATABASE_URL: "postgresql+asyncpg://toolregistry:devpassword@postgres:5432/toolregistry"
      EMBEDDING_ENDPOINT_URL: "http://embedding-service:1234/v1/embeddings"
      EMBEDDING_API_KEY: "dummy-key"
      PYTHONPATH: "/app"
    transport_type: "stdio"
```

### Method 4: Claude Desktop Integration

Add to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "toolbox": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-e", "DATABASE_URL=postgresql+asyncpg://toolregistry:devpassword@postgres:5432/toolregistry",
        "-e", "EMBEDDING_ENDPOINT_URL=http://host.docker.internal:1234/v1/embeddings",
        "toolbox:mcp",
        "python3.9", "-m", "app.mcp_fastmcp_server"
      ]
    }
  }
}
```

## MCP Protocol Features

### Tools

All registered tools are exposed with their:
- Name (e.g., "server_name:tool_name")
- Description
- Input schema (JSON Schema)
- Categories and tags

Example tool call:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "external_server:tool_name",
    "arguments": {
      "param1": "value1",
      "param2": "value2"
    }
  }
}
```

### Semantic Search

The FastMCP server provides enhanced tool discovery through semantic search:

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/search",
  "params": {
    "query": "find tools for data transformation",
    "limit": 5,
    "threshold": 0.7
  }
}
```

### Prompts

Pre-defined prompts for tool discovery:
- `find-tools`: Find tools for a specific task
- `list-categories`: List all tool categories
- `search-tools`: Semantic search for tools

### Resources

Available resources:
- `toolbox://tools/all`: Complete list of all tools
- `toolbox://tools/categories`: Tool categories and counts
- `toolbox://tools/stats`: Tool registry statistics

## Testing the FastMCP Server

### Using the Test Client

```bash
# Docker test
docker run --rm --network host \
  -e DATABASE_URL="postgresql+asyncpg://toolregistry:devpassword@localhost:5432/toolregistry" \
  -e EMBEDDING_ENDPOINT_URL="http://host.docker.internal:1234/v1/embeddings" \
  toolbox:mcp python3.9 test_mcp_stdio.py

# Local test
python3 test_mcp_stdio.py
```

### Manual Testing

1. **List Tools**:
```bash
echo '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}' | python3.9 -m app.mcp_fastmcp_server
```

2. **Search Tools**:
```bash
echo '{"jsonrpc": "2.0", "id": 2, "method": "tools/search", "params": {"query": "calculator", "limit": 5}}' | python3.9 -m app.mcp_fastmcp_server
```

## Configuration

### Required Environment Variables

- `DATABASE_URL`: PostgreSQL connection string
- `EMBEDDING_ENDPOINT_URL`: Embedding service URL
- `EMBEDDING_API_KEY`: Embedding service API key
- `EMBEDDING_DIMENSION`: Embedding dimensions (default: 768)

### Optional Environment Variables

- `LOG_LEVEL`: Logging level (INFO, DEBUG, etc.)
- `OTEL_ENABLED`: Enable OpenTelemetry (default: false for MCP server)
- `PYTHONPATH`: Set to "/app" when running in Docker
- `MCP_SERVER_NAME`: Name for the MCP server (default: "toolbox")

### External MCP Server Configuration

To configure external MCP servers for auto-sync:

```json
[
  {
    "name": "external-server",
    "url": "http://external-server:3000",
    "description": "External MCP server",
    "category": "external",
    "tags": ["external", "tools"]
  }
]
```

## Architecture

The FastMCP server implementation:

1. **Built on fastmcp Framework**: Leverages the high-performance fastmcp library
2. **Uses stdio/HTTP Transport**: Supports both stdio and HTTP communication
3. **Implements JSON-RPC 2.0**: Full MCP protocol compliance
4. **Leverages Existing Registry**: Direct access to Toolbox tool registry
5. **Provides Real-time Access**: Always up-to-date with the registry
6. **Maintains Validation**: Same validation as HTTP API

## Benefits

1. **High Performance**: Optimized for speed with fastmcp
2. **Standardized Protocol**: Uses the widely-adopted MCP protocol
3. **Language Agnostic**: Any client that speaks MCP can connect
4. **Rich Tool Discovery**: Semantic search and categorization
5. **Real-time Updates**: Tools are always up-to-date with the registry
6. **Secure Execution**: Same validation and execution as HTTP API
7. **Flexible Transport**: Supports stdio, HTTP, and SSE transports

## Integration Examples

### Python Client

```python
import asyncio
import json
import sys
from app.mcp_fastmcp_server import FastMCPServer

async def run_client():
    # Initialize the FastMCP server
    server = FastMCPServer()

    # List tools
    tools = await server.list_tools()
    print("Available tools:", json.dumps(tools, indent=2))

    # Search for tools
    search_results = await server.search_tools("calculator")
    print("Search results:", json.dumps(search_results, indent=2))

if __name__ == "__main__":
    asyncio.run(run_client())
```

### Node.js Client

```javascript
const { spawn } = require('child_process');
const { createInterface } = require('readline');

// Spawn the FastMCP server
const server = spawn('python3.9', ['-m', 'app.mcp_fastmcp_server'], {
  stdio: ['pipe', 'pipe', 'pipe']
});

const readline = createInterface({
  input: server.stdout,
  output: server.stdin
});

// Send requests
const request = {
  jsonrpc: "2.0",
  id: 1,
  method: "tools/list",
  params: {}
};

server.stdin.write(JSON.stringify(request) + '\n');

// Handle responses
readline.on('line', (line) => {
  const response = JSON.parse(line);
  console.log('Response:', response);
});
```

## Troubleshooting

### Common Issues

1. **Server not starting**
   - Check environment variables are set correctly
   - Verify database connection
   - Check embedding service is accessible

2. **Tools not appearing**
   - Run database migrations
   - Check if tools are registered in the database
   - Verify embeddings are generated

3. **Semantic search not working**
   - Check embedding service configuration
   - Verify embeddings exist for tools
   - Check search threshold settings

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python3.9 -m app.mcp_fastmcp_server
```

### Health Check

The FastMCP server includes health endpoints when running in HTTP mode:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## Migration from Legacy MCP Servers

If you were using the legacy MCP server implementations:

1. **Update your client configuration** to use `app.mcp_fastmcp_server` instead of the old servers
2. **Remove references** to deleted MCP servers (calculator, weather, text-utils, converter, sse-mcp)
3. **Update tool names** to use the new namespacing format (server_name:tool_name)
4. **Test your integration** with the new FastMCP server

The FastMCP server provides all the functionality of the legacy servers in a single, unified implementation with better performance and maintenance.