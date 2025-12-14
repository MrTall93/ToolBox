#!/bin/bash

echo "🚀 Starting local FastMCP server for MCP Inspector..."
echo ""

# Kill any existing processes
pkill -f "port-forward.*808" 2>/dev/null || true
pkill -f "mcp.*proxy" 2>/dev/null || true
sleep 2

# Get database credentials from k8s
DB_URL=$(kubectl get secret postgres-secret -n toolbox -o jsonpath='{.data.DATABASE_URL}' | base64 -d)
EMBEDDING_URL=$(kubectl get configmap toolbox-config -n toolbox -o jsonpath='{.data.EMBEDDING_ENDPOINT_URL}')

# Set environment variables
export DATABASE_URL="$DB_URL"
export EMBEDDING_ENDPOINT_URL="$EMBEDDING_URL"
export EMBEDDING_API_KEY="dummy-key"
export EMBEDDING_DIMENSION="768"
export SECRET_KEY="test-secret-key-for-development-only"
export LOG_LEVEL="INFO"
export PYTHONPATH="/app"

echo "✅ Environment configured"
echo ""

# Run the FastMCP server directly
echo "Starting FastMCP server on port 8080..."
cd /Users/guneetsingh/Documents/GitHub/tmp/ToolBox

# Use kubectl exec to run the server in the pod
echo "Using kubectl exec to run MCP server in existing pod..."
kubectl exec -it deployment/toolbox -n toolbox -- python3 -m app.mcp_fastmcp_server &
MCP_PID=$!

echo ""
echo "✅ FastMCP server is running!"
echo ""
echo "📋 For MCP Inspector, use the following configuration:"
echo ""
echo "Method 1 - Direct Connection (if MCP Inspector supports stdio):"
echo '```json'
echo '{'
echo '  "command": "kubectl",'
echo '  "args": ['
echo '    "exec", "-it", "-n", "toolbox",'
echo '    "deployment/toolbox", "--"'
echo '  ],'
echo '  "env": {'
echo '    "DATABASE_URL": "'"$DB_URL"'",'
echo '    "EMBEDDING_ENDPOINT_URL": "'"$EMBEDDING_URL"'",'
echo '    "EMBEDDING_API_KEY": "dummy-key",'
echo '    "EMBEDDING_DIMENSION": "768",'
echo '    "SECRET_KEY": "test-secret-key-for-development-only"'
echo '  }'
echo '}'
echo '```'
echo ""
echo "Method 2 - Manual Testing with curl:"
echo 'curl -X POST http://localhost:8080/mcp \'
echo '  -H "Content-Type: application/json" \'
echo '  -H "Accept: application/json, text/event-stream" \'
echo '  -d '"'"'{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}'"'"