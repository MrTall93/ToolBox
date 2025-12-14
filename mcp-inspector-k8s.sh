#!/bin/bash
# Script to run MCP Inspector with Toolbox FastMCP server in Kubernetes

set -e

echo "Setting up MCP Inspector connection to Toolbox FastMCP server in Kubernetes..."

# Find the pod name
POD_NAME=$(kubectl get pods -n toolbox -l app=toolbox -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
    echo "Error: No Toolbox pod found"
    exit 1
fi

echo "Found Toolbox pod: $POD_NAME"

# Create a wrapper script that kubectl execs the FastMCP server
cat > /tmp/toolbox-fastmcp-wrapper.sh << 'EOF'
#!/bin/bash
exec kubectl exec -i -n toolbox "$1" -- python3.9 -m app.mcp_fastmcp_server
EOF

chmod +x /tmp/toolbox-fastmcp-wrapper.sh

echo "Starting MCP Inspector..."
echo "The wrapper command to use in MCP Inspector is:"
echo "/tmp/toolbox-fastmcp-wrapper.sh $POD_NAME"
echo ""

# Check if mcp-inspector is installed
if ! command -v mcp-inspector &> /dev/null; then
    echo "Installing MCP Inspector..."
    npm install -g @modelcontextprotocol/inspector
fi

# Run MCP Inspector with the wrapper
echo "Starting MCP Inspector..."
mcp-inspector --command "/tmp/toolbox-fastmcp-wrapper.sh $POD_NAME"