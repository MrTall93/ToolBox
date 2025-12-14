#!/bin/bash
# Script to run Toolbox MCP HTTP server locally
# DEPRECATED: HTTP transport for MCP is no longer supported. Use stdio transport instead.

set -e

echo "This script is DEPRECATED."
echo "HTTP transport for MCP is no longer supported in the Toolbox FastMCP server."
echo ""
echo "Please use the stdio transport instead:"
echo "  - Run: python3.9 -m app.mcp_fastmcp_server"
echo "  - Or use: ./scripts/run-mcp-server.sh"
echo ""
echo "For MCP Inspector, use: mcp-inspector python3.9 -m app.mcp_fastmcp_server"
echo ""
exit 1