#!/bin/bash

# Tool Registry Helm Deployment Script
# Usage: ./scripts/deploy.sh [environment] [namespace] [release-name]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT=${1:-dev}
NAMESPACE=${2:-tool-registry-${ENVIRONMENT}}
RELEASE_NAME=${3:-tool-registry-${ENVIRONMENT}}

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    # Check if kubectl is available
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl is not installed or not in PATH"
        exit 1
    fi

    # Check if helm is available
    if ! command -v helm &> /dev/null; then
        print_error "helm is not installed or not in PATH"
        exit 1
    fi

    # Check if Kubernetes cluster is accessible
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi

    print_status "Prerequisites check passed"
}

# Function to setup namespace
setup_namespace() {
    print_status "Setting up namespace: ${NAMESPACE}"

    if ! kubectl get namespace ${NAMESPACE} &> /dev/null; then
        kubectl create namespace ${NAMESPACE}
        print_status "Namespace ${NAMESPACE} created"
    else
        print_status "Namespace ${NAMESPACE} already exists"
    fi
}

# Function to build dependencies
build_dependencies() {
    print_status "Building Helm dependencies..."
    helm dependency build
    print_status "Dependencies built successfully"
}

# Function to deploy or upgrade
deploy_or_upgrade() {
    local values_file="values-${ENVIRONMENT}.yaml"

    if [[ ! -f "${values_file}" ]]; then
        print_error "Values file ${values_file} not found"
        exit 1
    fi

    print_status "Deploying Tool Registry to ${ENVIRONMENT} environment..."
    print_status "Namespace: ${NAMESPACE}"
    print_status "Release: ${RELEASE_NAME}"
    print_status "Values file: ${values_file}"

    # Check if release exists
    if helm release list -n ${NAMESPACE} | grep -q ${RELEASE_NAME}; then
        print_status "Release exists, performing upgrade..."
        helm upgrade ${RELEASE_NAME} . \
            --namespace ${NAMESPACE} \
            --values ${values_file} \
            --wait \
            --timeout 10m
    else
        print_status "Performing fresh installation..."
        helm install ${RELEASE_NAME} . \
            --namespace ${NAMESPACE} \
            --values ${values_file} \
            --wait \
            --timeout 10m
    fi
}

# Function to verify deployment
verify_deployment() {
    print_status "Verifying deployment..."

    # Wait for pods to be ready
    print_status "Waiting for pods to be ready..."
    kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=tool-registry -n ${NAMESPACE} --timeout=300s

    # Check deployment status
    local ready_replicas=$(kubectl get deployment ${RELEASE_NAME} -n ${NAMESPACE} -o jsonpath='{.status.readyReplicas}')
    local desired_replicas=$(kubectl get deployment ${RELEASE_NAME} -n ${NAMESPACE} -o jsonpath='{.spec.replicas}')

    if [[ ${ready_replicas} -eq ${desired_replicas} ]]; then
        print_status "Deployment verification successful: ${ready_replicas}/${desired_replicas} replicas ready"
    else
        print_error "Deployment verification failed: ${ready_replicas}/${desired_replicas} replicas ready"
        exit 1
    fi

    # Check service status
    if kubectl get svc ${RELEASE_NAME}-service -n ${NAMESPACE} &> /dev/null; then
        print_status "Service ${RELEASE_NAME}-service is ready"
    else
        print_error "Service ${RELEASE_NAME}-service not found"
        exit 1
    fi
}

# Function to show access information
show_access_info() {
    print_status "Deployment completed successfully!"
    echo ""
    echo "Access Information:"
    echo "=================="
    echo "Namespace: ${NAMESPACE}"
    echo "Release: ${RELEASE_NAME}"
    echo ""

    # Show service information
    local service_type=$(kubectl get svc ${RELEASE_NAME}-service -n ${NAMESPACE} -o jsonpath='{.spec.type}')
    local service_port=$(kubectl get svc ${RELEASE_NAME}-service -n ${NAMESPACE} -o jsonpath='{.spec.ports[0].port}')

    if [[ "${service_type}" == "LoadBalancer" ]]; then
        local external_ip=$(kubectl get svc ${RELEASE_NAME}-service -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
        if [[ -n "${external_ip}" ]]; then
            echo "External URL: http://${external_ip}:${service_port}"
        else
            echo "External IP: Pending (use 'kubectl get svc ${RELEASE_NAME}-service -n ${NAMESPACE} -w' to monitor)"
        fi
    else
        echo "Service Type: ${service_type}"
        echo "Internal Port: ${service_port}"
        echo ""
        echo "To access locally, use port forwarding:"
        echo "kubectl port-forward svc/${RELEASE_NAME}-service 8000:${service_port} -n ${NAMESPACE}"
        echo "Then access: http://localhost:8000"
    fi

    echo ""
    echo "Health Check:"
    echo "kubectl port-forward svc/${RELEASE_NAME}-service 8000:${service_port} -n ${NAMESPACE}"
    echo "curl http://localhost:8000/health"
    echo ""
    echo "API Documentation:"
    echo "curl http://localhost:8000/docs"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [environment] [namespace] [release-name]"
    echo ""
    echo "Arguments:"
    echo "  environment   Environment to deploy to (dev, prod) [default: dev]"
    echo "  namespace     Kubernetes namespace to deploy to [default: tool-registry-<environment>]"
    echo "  release-name  Helm release name [default: tool-registry-<environment>]"
    echo ""
    echo "Examples:"
    echo "  $0 dev                    # Deploy to dev environment"
    echo "  $0 prod                   # Deploy to prod environment"
    echo "  $0 dev my-namespace       # Deploy to custom namespace"
    echo "  $0 prod tool-registry     # Deploy with custom release name"
}

# Main function
main() {
    case "${1:-}" in
        --help|-h)
            show_usage
            exit 0
            ;;
    esac

    print_status "Starting Tool Registry deployment..."

    check_prerequisites
    setup_namespace
    build_dependencies
    deploy_or_upgrade
    verify_deployment
    show_access_info

    print_status "Deployment process completed!"
}

# Run main function with all arguments
main "$@"