# Testing Toolbox FastMCP Server Locally

Since MCP servers use stdio transport, the easiest way to test with the MCP Inspector is to run the FastMCP server locally.

## Step 1: Port Forward the Database

```bash
kubectl port-forward -n toolbox svc/postgres 5432:5432 &
```

## Step 2: Run the MCP Server Locally

```bash
# Set environment variables
export DATABASE_URL="postgresql+asyncpg://toolregistry:devpassword@localhost:5432/toolregistry"
export EMBEDDING_ENDPOINT_URL="http://localhost:1234/v1/embeddings"
export EMBEDDING_API_KEY="dummy-key"
export EMBEDDING_DIMENSION="768"
export LOG_LEVEL="INFO"
export PYTHONPATH="/Users/guneetsingh/Documents/GitHub/tmp/ToolBox"

# Run the FastMCP server
python3.9 -m app.mcp_fastmcp_server
```

## Step 3: Test with MCP Inspector

In another terminal:

```bash
# Install MCP Inspector if you haven't already
npm install -g @modelcontextprotocol/inspector

# Run the inspector
mcp-inspector python3.9 -m app.mcp_fastmcp_server
```

## Alternative: Using Docker with Volume Mount

```bash
# Run Toolbox FastMCP server with mounted source
docker run --rm -it \
  -v /Users/guneetsingh/Documents/GitHub/tmp/ToolBox:/app \
  -e DATABASE_URL="postgresql+asyncpg://toolregistry:devpassword@host.docker.internal:5432/toolregistry" \
  -e EMBEDDING_ENDPOINT_URL="http://host.docker.internal:1234/v1/embeddings" \
  -e EMBEDDING_API_KEY="dummy-key" \
  -e EMBEDDING_DIMENSION="768" \
  -e LOG_LEVEL="INFO" \
  -e PYTHONPATH="/app" \
  toolbox:mcp \
  python3.9 -m app.mcp_fastmcp_server
```

## What to Expect

The MCP Inspector will show:
- Server information (Tool Registry FastMCP v1.0.0)
- Tools available from the registry and any connected external MCP servers
- Tools will be namespaced by their source (e.g., "external_server:tool_name")
- You can use semantic search to find tools by describing what you need

You can then test tool execution directly in the MCP Inspector interface!