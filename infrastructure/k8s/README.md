# Kubernetes Deployment

This directory contains Kubernetes manifests for deploying the Tool Registry MCP Server.

## Architecture

The deployment includes:

- **Init Container**: Runs database migrations via Alembic before the main application starts
- **Main Container**: FastAPI application serving the MCP endpoints
- **ConfigMap**: Application configuration (non-sensitive)
- **Secret**: Sensitive configuration (database credentials, API keys)
- **Service**: ClusterIP service for internal communication
- **Deployment**: Main application with 3 replicas for high availability

## Database Migrations as Init Container

Database migrations are automatically run before each deployment using an init container. This ensures:

- Schema is always up-to-date before the application starts
- Zero-downtime deployments (migrations run before new pods receive traffic)
- Automatic retry on connection failures
- Proper error handling and logging

### How It Works

1. When a pod starts, the `migrations` init container runs first
2. It waits for PostgreSQL to be ready (max 30 retries)
3. Runs `alembic upgrade head` to apply all pending migrations
4. If successful, the main application container starts
5. If it fails, the pod will not start and K8s will retry

The migration script is stored in a ConfigMap and mounted as a volume.

## Deployment Steps

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured
- PostgreSQL database with pgvector extension
- Container registry with the tool-registry-mcp image

### 1. Update Secrets

Edit [secret.yaml](base/secret.yaml) with your actual credentials:

```bash
# Replace CHANGE_ME with your actual database password
DATABASE_URL: "postgresql+asyncpg://toolregistry:YOUR_PASSWORD@postgres-service:5432/toolregistry"

# Optional: Add embedding API key if needed
EMBEDDING_API_KEY: "your-api-key-here"
```

**IMPORTANT**: For production, use a proper secrets management solution:
- Kubernetes Secrets (encrypted at rest)
- External Secrets Operator
- HashiCorp Vault
- AWS Secrets Manager / GCP Secret Manager / Azure Key Vault

### 2. Update ConfigMap

Edit [configmap.yaml](base/configmap.yaml) to configure your environment:

```yaml
# Update the embedding service endpoint
embedding-endpoint-url: "http://your-embedding-service:8001/embed"

# Adjust search parameters as needed
default-similarity-threshold: "0.7"
default-search-limit: "5"
```

### 3. Deploy to Kubernetes

```bash
# Apply all manifests
kubectl apply -f infrastructure/k8s/base/

# Or apply them in order
kubectl apply -f infrastructure/k8s/base/configmap.yaml
kubectl apply -f infrastructure/k8s/base/secret.yaml
kubectl apply -f infrastructure/k8s/base/service.yaml
kubectl apply -f infrastructure/k8s/base/deployment.yaml
```

### 4. Verify Deployment

```bash
# Check if pods are running
kubectl get pods -l app=tool-registry

# Check init container logs (migrations)
kubectl logs <pod-name> -c migrations

# Check main container logs
kubectl logs <pod-name> -c api

# Check deployment status
kubectl describe deployment tool-registry-api
```

### 5. Access the API

```bash
# Port-forward to access locally
kubectl port-forward service/tool-registry-api 8000:8000

# Test the health endpoint
curl http://localhost:8000/health

# Access API docs
open http://localhost:8000/docs
```

## Production Considerations

### Database Migrations

The init container approach works well for most scenarios, but consider these for large-scale deployments:

1. **Pre-deployment migrations**: Run migrations in a separate Job before deployment
2. **Blue-green deployments**: Ensure migrations are backward-compatible
3. **Migration locks**: Alembic uses PostgreSQL advisory locks to prevent concurrent migrations

### Scaling

```bash
# Scale replicas
kubectl scale deployment tool-registry-api --replicas=5

# Or use HPA (Horizontal Pod Autoscaler)
kubectl autoscale deployment tool-registry-api \
  --cpu-percent=70 \
  --min=3 \
  --max=10
```

### Resource Limits

Adjust resource requests/limits in [deployment.yaml](base/deployment.yaml) based on your workload:

```yaml
resources:
  requests:
    cpu: 250m      # Minimum guaranteed
    memory: 256Mi
  limits:
    cpu: 1000m     # Maximum allowed
    memory: 512Mi
```

### Security

The deployment follows security best practices:

- ✅ Non-root user (UID 1000)
- ✅ Read-only root filesystem
- ✅ Dropped all capabilities
- ✅ No privilege escalation
- ✅ Secrets stored securely
- ✅ Network policies (add as needed)

### Monitoring

Add monitoring with:

```yaml
# Prometheus annotations
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

### Ingress (Optional)

To expose the API externally, create an Ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tool-registry-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
    - hosts:
        - api.yourdomain.com
      secretName: tool-registry-tls
  rules:
    - host: api.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: tool-registry-api
                port:
                  number: 8000
```

## Troubleshooting

### Init Container Fails

```bash
# Check migration logs
kubectl logs <pod-name> -c migrations

# Common issues:
# 1. Database not accessible - check DATABASE_URL
# 2. pgvector extension missing - ensure PostgreSQL has pgvector
# 3. Network policy blocking - check network policies
```

### Application Won't Start

```bash
# Check events
kubectl describe pod <pod-name>

# Check application logs
kubectl logs <pod-name> -c api

# Verify configuration
kubectl get configmap tool-registry-config -o yaml
kubectl get secret tool-registry-secrets -o yaml
```

### Connection Issues

```bash
# Test database connectivity from within cluster
kubectl run -it --rm debug --image=postgres:15 --restart=Never -- \
  psql "postgresql://toolregistry:password@postgres-service:5432/toolregistry"

# Check service endpoints
kubectl get endpoints tool-registry-api
```

## Clean Up

```bash
# Delete all resources
kubectl delete -f infrastructure/k8s/base/

# Or delete by label
kubectl delete all -l app=tool-registry
```

## Next Steps

- Set up Helm charts for templated deployments (see `infrastructure/helm/`)
- Configure monitoring with Prometheus + Grafana
- Set up alerting for migration failures
- Implement GitOps with ArgoCD or Flux
- Add network policies for pod-to-pod communication
