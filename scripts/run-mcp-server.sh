#!/bin/bash
# Script to run Toolbox as a FastMCP server

set -e

echo "Starting Toolbox FastMCP Server..."
echo "Mode: FastMCP Server (stdio transport)"

# Run the FastMCP server using stdio transport
python3.9 -m app.mcp_fastmcp_server