#!/bin/bash
# Script to connect to Toolbox FastMCP server running in Kubernetes

set -e

echo "Connecting to Toolbox FastMCP server in Kubernetes..."

# Find the pod name
POD_NAME=$(kubectl get pods -n toolbox -l app=toolbox -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
    echo "Error: No Toolbox pod found"
    exit 1
fi

echo "Found Toolbox pod: $POD_NAME"

# Run kubectl exec to connect to the FastMCP server
echo "Starting FastMCP server connection..."
echo "Press Ctrl+C to stop"
echo ""

kubectl exec -it -n toolbox "$POD_NAME" -- python3.9 -m app.mcp_fastmcp_server