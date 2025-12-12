# Tool Registry MCP Server - Kubernetes Deployment

## Overview

This directory contains production-ready Kubernetes manifests for deploying the Tool Registry MCP Server.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Ingress (nginx)                          │
├─────────────────────────────────────────────────────────────┤
│                  Tool Registry Service                         │
│  ┌─────────────────┬─────────────────┬─────────────────────┐  │
│  │   Pod 1 (API)   │   Pod 2 (API)   │   Pod N (API)      │  │
│  │   UBI8 Container│   UBI8 Container│   UBI8 Container   │  │
│  └─────────────────┴─────────────────┴─────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                    PostgreSQL (pgvector)                          │
├─────────────────────────────────────────────────────────────┤
│                   Monitoring & Logging                           │
└─────────────────────────────────────────────────────────────┘
```

## Files Structure

### Core Resources
- `namespace.yaml` - Kubernetes namespace
- `configmap.yaml` - Application configuration
- `secrets.yaml` - Sensitive data (database credentials, API keys)
- `deployment.yaml` - Main application deployment
- `service.yaml` - Internal and external services
- `postgres.yaml` - PostgreSQL database with pgvector

### Production Features
- `ingress.yaml` - External access with TLS termination
- `hpa.yaml` - Horizontal Pod Autoscaler
- `network-policy.yaml` - Network security policies
- `monitoring.yaml` - Prometheus monitoring and Grafana dashboards
- `rbac.yaml` - Role-based access control

### Kustomize
- `kustomization.yaml` - Base configuration
- `prod.yaml` - Production-specific overrides

## Prerequisites

### Required
- Kubernetes 1.24+
- PostgreSQL with pgvector extension (or use the provided manifests)
- Ingress controller (nginx, traefik, etc.)
- Cert-manager for TLS certificates (optional but recommended)

### Optional
- Prometheus Operator for monitoring
- Grafana for visualization
- Loki for log aggregation
- Cert-manager for automatic TLS

## Quick Start

### 1. Create Namespace
```bash
kubectl apply -f namespace.yaml
```

### 2. Configure Secrets
Edit `secrets.yaml` with your actual values:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Application secret key
- `EMBEDDING_API_KEY` - Your embedding service API key

```bash
# Generate base64 encoded values
echo -n "your-secret-key" | base64
echo -n "your-db-connection-string" | base64

# Apply secrets
kubectl apply -f secrets.yaml
```

### 3. Deploy Database
```bash
kubectl apply -f postgres.yaml
```

### 4. Deploy Application
```bash
kubectl apply -f configmap.yaml deployment.yaml service.yaml
```

### 5. Configure Ingress (Optional)
Edit `ingress.yaml` with your domain and TLS configuration:

```yaml
spec:
  tls:
  - hosts:
    - api.tool-registry.yourdomain.com
    secretName: tool-registry-tls
  rules:
  - host: api.tool-registry.yourdomain.com
    http:
      paths:
      - path: /
        backend:
          service:
            name: tool-registry-service
            port:
              number: 80
```

```bash
kubectl apply -f ingress.yaml
```

### 6. Enable Autoscaling
```bash
kubectl apply -f hpa.yaml
```

### 7. Enable Monitoring
```bash
kubectl apply -f monitoring.yaml rbac.yaml
```

## Configuration

### Environment Variables

#### Required
- `DATABASE_URL` - PostgreSQL connection string with pgvector
- `SECRET_KEY` - Flask application secret key
- `EMBEDDING_ENDPOINT_URL` - Your embedding service endpoint

#### Optional
- `LOG_LEVEL` - Application log level (default: INFO)
- `WORKERS` - Number of uvicorn workers (default: 4)
- `ENABLE_CACHE` - Enable application caching (default: true)
- `CORS_ORIGINS` - Allowed CORS origins

### Database Configuration

#### PostgreSQL with pgvector
```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Create tools table with vector support
CREATE TABLE tools (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    tags JSONB DEFAULT '[]',
    input_schema JSONB NOT NULL,
    embedding vector(768),  -- Adjust dimension based on your model
    is_active BOOLEAN DEFAULT true,
    version VARCHAR(50) DEFAULT '1.0.0',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create vector index for similarity search
CREATE INDEX ON tools USING ivfflat (embedding vector_cosine_ops);
```

## Scaling

### Horizontal Scaling
- Minimum: 2 replicas (recommended)
- Maximum: 50 replicas (configurable)
- Target CPU: 70%
- Target Memory: 80%

### Vertical Scaling
- Minimum pod: 1GB RAM, 0.5 CPU
- Maximum pod: 2GB RAM, 2 CPU

### Database Scaling
- Consider connection pooling with PgBouncer
- Enable connection pooling in PostgreSQL
- Use read replicas for high read workloads

## Security

### Network Policies
- Restrict inbound traffic to required sources only
- Allow only necessary egress traffic
- Use mTLS for inter-service communication

### Pod Security
- Non-root user execution
- Read-only root filesystem
- Drop all capabilities
- Resource limits enforced

### Secrets Management
- Use Kubernetes secrets for sensitive data
- Rotate secrets regularly
- Consider external secret management (HashiCorp Vault, AWS Secrets Manager)

## Monitoring

### Prometheus Metrics
- HTTP request metrics (rate, duration, errors)
- Resource usage (CPU, memory)
- Application-specific metrics (tool count, embedding cache hits)

### Alerting
- Service downtime
- High error rates (>10%)
- High latency (>2s 95th percentile)
- Resource exhaustion

### Logging
- Structured JSON logs
- Centralized log aggregation
- Log levels: DEBUG, INFO, WARNING, ERROR

## Deployment Strategies

### Rolling Update
```bash
kubectl set image deployment/tool-registry tool-registry=your-registry/tool-registry:v1.1.0
```

### Blue-Green Deployment
```bash
kubectl apply -f deployment-blue-green.yaml
```

### Canary Deployment
```bash
kubectl apply -f deployment-canary.yaml
```

## Troubleshooting

### Common Issues

#### 1. Pod CrashLoopBackOff
```bash
kubectl logs deployment/tool-registry
kubectl describe pod <pod-name>
```

#### 2. Database Connection Errors
```bash
kubectl exec -it deployment/tool-registry -- python -c "
import asyncpg
asyncio.run(asyncpg.connect('postgresql+asyncpg://user:pass@postgres-service:5432/db'))
"
```

#### 3. Embedding Service Issues
```bash
kubectl exec -it deployment/tool-registry -- curl -X POST http://your-embedding-service/embed -H "Content-Type: application/json" -d '{"input": "test"}'
```

### Health Checks

#### Application Health
```bash
kubectl port-forward service/tool-registry-service 8000:8000
curl http://localhost:8000/health
```

#### Database Health
```bash
kubectl exec -it postgres-0 -- pg_isready -U tool-registry
```

## Maintenance

### Backup
```bash
# Database backup
kubectl exec postgres-0 -- pg_dump -U tool-registry tool-registry > backup.sql

# Kubernetes manifests backup
kubectl get all -n tool-registry -o yaml > cluster-backup.yaml
```

### Updates
```bash
# Update to new version
kubectl apply -k .

# Rollback to previous version
kubectl rollout undo deployment/tool-registry
```

### Cleanup
```bash
# Remove all resources
kubectl delete -f .

# Remove namespace
kubectl delete namespace tool-registry
```

## Production Checklist

- [ ] Secrets configured with strong values
- [ ] TLS certificates configured
- [ ] Resource limits set appropriately
- [ ] Health checks configured
- [ ] Monitoring and alerting enabled
- [ ] Backup strategy implemented
- [ ] Disaster recovery plan in place
- [ ] Security policies applied
- [ ] Load testing performed
- [ ] Documentation updated

## Support

For issues and questions:

1. Check application logs: `kubectl logs deployment/tool-registry`
2. Check pod status: `kubectl get pods -n tool-registry`
3. Check events: `kubectl get events -n tool-registry`
4. Review documentation: [Project README](../README.md)

---

**Last Updated**: 2025-12-11
**Version**: 1.0.0
**Maintainer**: Your Team