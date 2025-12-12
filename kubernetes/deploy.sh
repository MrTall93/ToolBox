#!/bin/bash

# Tool Registry MCP Server - Kubernetes Deployment Script
# This script automates the deployment of the Tool Registry MCP Server to Kubernetes

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NAMESPACE="tool-registry"
KUBECONFIG=${KUBECONFIG:-$HOME/.kube/config}
CONTEXT=${KUBECONTEXT:-}

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed. Please install kubectl first."
        exit 1
    fi

    # Check kubernetes connection
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster. Please check your kubeconfig."
        exit 1
    fi

    # Check if namespace exists, create if not
    if ! kubectl get namespace $NAMESPACE &> /dev/null; then
        print_warning "Namespace '$NAMESPACE' does not exist. Creating..."
        kubectl create namespace $NAMESPACE
    fi

    print_success "Prerequisites check completed."
}

# Configure secrets
configure_secrets() {
    print_status "Configuring secrets..."

    # Prompt for database URL if not configured
    if ! kubectl get secret tool-registry-secrets -n $NAMESPACE &> /dev/null; then
        print_warning "Secrets not configured. Please provide the following values:"

        read -p "PostgreSQL connection URL (postgresql+asyncpg://user:pass@host:5432/dbname): " DB_URL
        read -p "Application secret key (generate with: openssl rand -hex 32): " SECRET_KEY
        read -p "Embedding API key: " EMBEDDING_API_KEY

        # Generate base64 encoded values
        DB_URL_B64=$(echo -n "$DB_URL" | base64)
        SECRET_KEY_B64=$(echo -n "$SECRET_KEY" | base64)
        EMBEDDING_API_KEY_B64=$(echo -n "$EMBEDDING_API_KEY" | base64)

        # Create secrets file
        cat > /tmp/secrets.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: tool-registry-secrets
  namespace: $NAMESPACE
type: Opaque
data:
  DATABASE_URL: $DB_URL_B64
  SECRET_KEY: $SECRET_KEY_B64
  EMBEDDING_API_KEY: $EMBEDDING_API_KEY_B64
  API_KEY: $(echo -n "production-api-token" | base64)
EOF

        kubectl apply -f /tmp/secrets.yaml
        rm /tmp/secrets.yaml
        print_success "Secrets configured."
    else
        print_success "Secrets already exist."
    fi
}

# Deploy infrastructure
deploy_infrastructure() {
    print_status "Deploying infrastructure..."

    # Deploy ConfigMaps
    kubectl apply -f configmap.yaml

    # Deploy PostgreSQL
    kubectl apply -f postgres.yaml

    # Wait for PostgreSQL to be ready
    print_status "Waiting for PostgreSQL to be ready..."
    kubectl wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s

    print_success "Infrastructure deployed successfully."
}

# Deploy application
deploy_application() {
    print_status "Deploying Tool Registry application..."

    # Deploy the application
    kubectl apply -f deployment.yaml
    kubectl apply -f service.yaml

    # Wait for deployment to be ready
    print_status "Waiting for application to be ready..."
    kubectl wait --for=condition=available deployment/tool-registry -n $NAMESPACE --timeout=300s

    print_success "Application deployed successfully."
}

# Deploy production features
deploy_production() {
    print_status "Deploying production features..."

    # Apply optional production features
    if kubectl get ingressclass nginx &> /dev/null; then
        kubectl apply -f ingress.yaml
        print_success "Ingress deployed."
    else
        print_warning "NGINX IngressController not found. Skipping ingress deployment."
        print_status "To enable ingress, install NGINX IngressController: kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller/v1.8.2/deploy/static/provider/cloud/deploy.yaml"
    fi

    # Apply HPA
    kubectl apply -f hpa.yaml

    # Apply Network Policies
    kubectl apply -f network-policy.yaml

    # Apply RBAC
    kubectl apply -f rbac.yaml

    print_success "Production features deployed."
}

# Setup monitoring
setup_monitoring() {
    print_status "Setting up monitoring..."

    # Check if Prometheus is available
    if kubectl get service prometheus-service -n monitoring &> /dev/null; then
        kubectl apply -f monitoring.yaml
        print_success "Monitoring deployed with Prometheus integration."
    else
        print_warning "Prometheus not found in 'monitoring' namespace. Skipping monitoring setup."
        print_status "To enable monitoring, install Prometheus Operator: https://github.com/prometheus-operator/prometheus-operator"
    fi
}

# Verify deployment
verify_deployment() {
    print_status "Verifying deployment..."

    # Check pods
    print_status "Checking pods..."
    kubectl get pods -n $NAMESPACE -l app=tool-registry

    # Check services
    print_status "Checking services..."
    kubectl get services -n $NAMESPACE -l app=tool-registry

    # Check deployment status
    print_status "Deployment status:"
    kubectl rollout status deployment/tool-registry -n $NAMESPACE

    # Test API health
    print_status "Testing API health..."
    sleep 10  # Wait for pods to be fully ready
    if kubectl port-forward service/tool-registry-service 8080:8000 -n $NAMESPACE &> /dev/null & then
        sleep 5
        if curl -s http://localhost:8080/health &> /dev/null; then
            print_success "API health check passed."
        else
            print_error "API health check failed."
        fi
        pkill -f "kubectl port-forward" &> /dev/null
    else
        print_warning "Could not test API health check."
    fi
}

# Display access information
show_access_info() {
    print_success "Deployment completed successfully!"

    echo
    echo -e "${BLUE}=== Access Information ===${NC}"
    echo "Namespace: $NAMESPACE"
    echo "Service: tool-registry-service"
    echo "Port: 8000"

    if kubectl get ingress tool-registry-ingress -n $NAMESPACE &> /dev/null; then
        echo "Ingress: Configured (check external IP/DNS)"
    fi

    echo
    echo -e "${BLUE}=== Useful Commands ===${NC}"
    echo "Check logs: kubectl logs -f deployment/tool-registry -n $NAMESPACE"
    echo "Access API: kubectl port-forward service/tool-registry-service 8000:8000 -n $NAMESPACE"
    echo "Check pods: kubectl get pods -n $NAMESPACE"
    echo "Scale deployment: kubectl scale deployment tool-registry --replicas=5 -n $NAMESPACE"
    echo "Check HPA: kubectl get hpa -n $NAMESPACE"

    echo
    echo -e "${BLUE}=== API Endpoints ===${NC}"
    echo "Health Check: http://localhost:8000/health"
    echo "API Docs: http://localhost:8000/docs"
    echo "MCP List Tools: POST http://localhost:8000/mcp/list_tools"
    echo "Admin Register: POST http://localhost:8000/admin/tools"
}

# Cleanup function
cleanup() {
    print_status "Cleaning up deployment..."

    kubectl delete -f network-policy.yaml 2>/dev/null || true
    kubectl delete -f hpa.yaml 2>/dev/null || true
    kubectl delete -f monitoring.yaml 2>/dev/null || true
    kubectl delete -f rbac.yaml 2>/dev/null || true
    kubectl delete -f ingress.yaml 2>/dev/null || true
    kubectl delete -f service.yaml 2>/dev/null || true
    kubectl delete -f deployment.yaml 2>/dev/null || true
    kubectl delete -f postgres.yaml 2>/dev/null || true
    kubectl delete -f configmap.yaml 2>/dev/null || true

    # Ask before deleting secrets
    read -p "Delete secrets as well? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete secret tool-registry-secrets -n $NAMESPACE 2>/dev/null || true
        print_success "Secrets deleted."
    fi

    # Ask before deleting namespace
    read -p "Delete namespace '$NAMESPACE' as well? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete namespace $NAMESPACE 2>/dev/null || true
        print_success "Namespace deleted."
    fi

    print_success "Cleanup completed."
}

# Show help
show_help() {
    echo "Tool Registry MCP Server - Kubernetes Deployment Script"
    echo
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Options:"
    echo "  deploy      Full deployment (default)"
    echo "  infra       Deploy infrastructure only"
    echo "  app         Deploy application only"
    echo "  prod        Deploy with production features"
    echo "  monitor     Setup monitoring"
    echo "  verify      Verify deployment"
    echo "  cleanup     Clean up deployment"
    echo "  help        Show this help message"
    echo
    echo "Environment variables:"
    echo "  NAMESPACE    Kubernetes namespace (default: tool-registry)"
    echo "  KUBECONFIG   Path to kubeconfig file"
    echo "  KUBECONTEXT  Kubernetes context"
    echo
}

# Main execution
main() {
    cd "$(dirname "$0")"

    case "${1:-deploy}" in
        deploy)
            check_prerequisites
            configure_secrets
            deploy_infrastructure
            deploy_application
            deploy_production
            setup_monitoring
            verify_deployment
            show_access_info
            ;;
        infra)
            check_prerequisites
            deploy_infrastructure
            ;;
        app)
            check_prerequisites
            deploy_application
            ;;
        prod)
            check_prerequisites
            configure_secrets
            deploy_infrastructure
            deploy_application
            deploy_production
            ;;
        monitor)
            setup_monitoring
            ;;
        verify)
            verify_deployment
            show_access_info
            ;;
        cleanup)
            cleanup
            ;;
        help)
            show_help
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
}

# Trap cleanup on script exit
trap cleanup EXIT

# Run main function
main "$@"