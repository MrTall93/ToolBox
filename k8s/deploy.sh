#!/bin/bash

# Deploy Toolbox and LiteLLM on Kubernetes

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Building Docker image for Toolbox..."
cd $PROJECT_DIR
docker build -f Dockerfile.ubi8 -t toolbox:latest .
cd $SCRIPT_DIR

echo "Applying Kubernetes manifests..."

# Create namespace
kubectl apply -f namespace/namespace.yaml

# Deploy PostgreSQL
echo "Deploying PostgreSQL..."
kubectl apply -f postgres/configmap.yaml
kubectl apply -f postgres/pvc.yaml
kubectl apply -f postgres/deployment.yaml
kubectl apply -f postgres/service.yaml

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres -n toolbox --timeout=300s

# Deploy Toolbox
echo "Deploying Toolbox..."
kubectl apply -f toolbox/configmap.yaml
kubectl apply -f toolbox/deployment.yaml
kubectl apply -f toolbox/service.yaml

# Wait for Toolbox to be ready
echo "Waiting for Toolbox to be ready..."
kubectl wait --for=condition=ready pod -l app=toolbox -n toolbox --timeout=300s

# Deploy LiteLLM
echo "Deploying LiteLLM..."
kubectl apply -f litellm/configmap.yaml
kubectl apply -f litellm/deployment.yaml
kubectl apply -f litellm/service.yaml

# Wait for LiteLLM to be ready
echo "Waiting for LiteLLM to be ready..."
kubectl wait --for=condition=ready pod -l app=litellm -n toolbox --timeout=300s

echo "Deployment complete!"
echo ""
echo "Services:"
echo "  Toolbox API: http://localhost:30800"
echo "  LiteLLM API: http://localhost:30400"
echo ""
echo "To check pod status: kubectl get pods -n toolbox"
echo "To check logs: kubectl logs -n toolbox deployment/toolbox"