#!/bin/bash
# Script to run MCP Inspector with proper configuration for Toolbox FastMCP server

echo "🚀 Starting Toolbox FastMCP server for MCP Inspector..."
echo ""

# Kill any existing port-forwards
pkill -f "kubectl port-forward" 2>/dev/null || true

# Start port-forward for the main toolbox service (not the HTTP one)
echo "📡 Starting port-forward for Toolbox API..."
kubectl port-forward service/toolbox 8000:8000 -n toolbox &
FORWARD_PID=$!
sleep 3

# Check if it's working
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Toolbox API is accessible at http://localhost:8000"
    echo ""
    echo "📋 MCP Inspector Configuration:"
    echo "--------------------------------"
    echo "The MCP server uses stdio transport, not HTTP."
    echo "Please use the following configuration:"
    echo ""
    echo "For Claude Desktop (~/Library/Application Support/Claude/claude_desktop_config.json):"
    echo ""
    echo '{'
    echo '  "mcpServers": {'
    echo '    "toolbox": {'
    echo '      "command": "kubectl",'
    echo '      "args": ['
    echo '        "exec", "-i", "-n", "toolbox",'
    echo '        "deployment/toolbox",'
    echo '        "--",'
    echo '        "python3", "-m", "app.mcp_fastmcp_server"'
    echo '      ]'
    echo '    }'
    echo '  }'
    echo '}'
    echo ""
    echo "Alternatively, run it locally:"
    echo "1. Install dependencies: pip install -r requirements.txt"
    echo "2. Set DATABASE_URL and other env vars"
    echo "3. Run: python3 -m app.mcp_fastmcp_server"
    echo ""
    echo "Then use:"
    echo '{'
    echo '  "mcpServers": {'
    echo '    "toolbox": {'
    echo '      "command": "python3",'
    echo '      "args": ["-m", "app.mcp_fastmcp_server"]'
    echo '    }'
    echo '  }'
    echo '}'
else
    echo "❌ Failed to connect to Toolbox"
fi

# Cleanup
kill $FORWARD_PID 2>/dev/null || true
