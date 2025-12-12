# Production Deployment Guide

## Overview

This guide covers production deployment of the Tool Registry MCP Server using the UBI8 Docker image, which is recommended for enterprise environments.

## Prerequisites

### System Requirements
- **CPU**: 2 cores minimum, 4 cores recommended
- **Memory**: 4GB minimum, 8GB recommended
- **Storage**: 20GB minimum, 50GB recommended
- **Network**: Internet access for embedding service

### Dependencies
- Docker 20.10+ or Kubernetes 1.24+
- PostgreSQL 13+ with pgvector extension
- Load balancer (for Kubernetes)
- Monitoring solution (Prometheus, Grafana)

## Quick Start

### 1. Build and Test Container
```bash
# Build UBI8 production image
docker build -f Dockerfile.ubi8 -t tool-registry:ubi8 .

# Test container locally
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname \
  -e SECRET_KEY=production-secret-key \
  tool-registry:ubi8

# Verify health check
curl http://localhost:8000/health
```

### 2. Docker Compose Deployment
```yaml
version: '3.8'

services:
  # Application
  api:
    image: tool-registry:ubi8
    restart: unless-stopped
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/toolregistry
      - SECRET_KEY=${SECRET_KEY}
      - EMBEDDING_BASE_URL=${EMBEDDING_BASE_URL}
      - EMBEDDING_API_KEY=${EMBEDDING_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M

  # Database with pgvector
  db:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      - POSTGRES_DB=toolregistry
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./infrastructure/sql/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d toolregistry"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Migrations
  migrations:
    image: tool-registry:ubi8
    restart: "no"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/toolregistry
    command: ["python3.9", "-m", "alembic", "upgrade", "head"]
    depends_on:
      db:
        condition: service_healthy

volumes:
  postgres_data:
```

## Kubernetes Deployment

### 1. Namespace and Configuration
```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: tool-registry
  labels:
    name: tool-registry
```

### 2. Secrets
```yaml
# secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: tool-registry-secrets
  namespace: tool-registry
type: Opaque
data:
  DATABASE_URL: <base64-encoded-database-url>
  SECRET_KEY: <base64-encoded-secret-key>
  EMBEDDING_API_KEY: <base64-encoded-embedding-api-key>
```

### 3. ConfigMap
```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tool-registry-config
  namespace: tool-registry
data:
  EMBEDDING_BASE_URL: "https://your-embedding-service.com/v1/embeddings"
  LOG_LEVEL: "INFO"
  WORKERS: "4"
```

### 4. Deployment with Security
```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tool-registry
  namespace: tool-registry
  labels:
    app: tool-registry
spec:
  replicas: 3
  selector:
    matchLabels:
      app: tool-registry
  template:
    metadata:
      labels:
        app: tool-registry
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
        fsGroup: 1000
        readOnlyRootFilesystem: true
        allowPrivilegeEscalation: false
        capabilities:
          drop:
            - ALL
      initContainers:
      - name: migrations
        image: tool-registry:ubi8
        imagePullPolicy: Always
        securityContext:
          runAsNonRoot: true
          runAsUser: 1000
          runAsGroup: 1000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: tool-registry-secrets
              key: DATABASE_URL
        command: ["python3.9", "-m", "alembic", "upgrade", "head"]
        volumeMounts:
        - name: tmp
          mountPath: /app/tmp
        - name: logs
          mountPath: /app/logs
      containers:
      - name: tool-registry
        image: tool-registry:ubi8
        imagePullPolicy: Always
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
              - ALL
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: tool-registry-secrets
              key: DATABASE_URL
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: tool-registry-secrets
              key: SECRET_KEY
        - name: EMBEDDING_BASE_URL
          valueFrom:
            configMapKeyRef:
              name: tool-registry-config
              key: EMBEDDING_BASE_URL
        - name: EMBEDDING_API_KEY
          valueFrom:
            secretKeyRef:
              name: tool-registry-secrets
              key: EMBEDDING_API_KEY
        ports:
        - containerPort: 8000
          name: http
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /live
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        volumeMounts:
        - name: tmp
          mountPath: /app/tmp
        - name: logs
          mountPath: /app/logs
      volumes:
      - name: tmp
        emptyDir: {}
      - name: logs
        emptyDir: {}
```

### 5. Service
```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: tool-registry-service
  namespace: tool-registry
  labels:
    app: tool-registry
spec:
  type: ClusterIP
  ports:
  - port: 80
    targetPort: 8000
    protocol: TCP
    name: http
  selector:
    app: tool-registry
```

### 6. Horizontal Pod Autoscaler
```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: tool-registry-hpa
  namespace: tool-registry
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: tool-registry
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 10
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
```

## Environment Variables

### Required
```bash
DATABASE_URL="postgresql+asyncpg://user:password@host:5432/dbname"
SECRET_KEY="your-secure-secret-key"
```

### Optional
```bash
EMBEDDING_BASE_URL="https://your-embedding-service.com/v1/embeddings"
EMBEDDING_API_KEY="your-api-key"
LOG_LEVEL="INFO"  # DEBUG, INFO, WARNING, ERROR
WORKERS="4"       # Number of uvicorn workers
```

## Monitoring and Observability

### 1. Health Endpoints
- **Health Check**: `GET /health` - Complete service health
- **Liveness**: `GET /live` - Container liveness (Kubernetes)
- **Readiness**: `GET /ready` - Service readiness (Kubernetes)

### 2. Metrics Collection
```yaml
# service-monitor.yaml (for Prometheus)
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: tool-registry-monitor
  namespace: tool-registry
spec:
  selector:
    matchLabels:
      app: tool-registry
  endpoints:
  - port: http
    path: /metrics
    interval: 30s
```

### 3. Logging
- Logs are JSON formatted for easy parsing
- Log levels controlled by `LOG_LEVEL` environment variable
- Structured logging includes request IDs and correlation

## Security Configuration

### 1. Container Security
- Non-root execution (UID 1000)
- Read-only root filesystem
- No privileged capabilities
- Resource limits enforced

### 2. Network Security
```yaml
# network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tool-registry-netpol
  namespace: tool-registry
spec:
  podSelector:
    matchLabels:
      app: tool-registry
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-nginx
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 5432  # PostgreSQL
    - protocol: TCP
      port: 443   # HTTPS for embedding service
    - protocol: TCP
      port: 53    # DNS
```

## Deployment Steps

### 1. Prepare Environment
```bash
# Create namespace
kubectl create namespace tool-registry

# Apply secrets
kubectl apply -f secrets.yaml

# Apply configmap
kubectl apply -f configmap.yaml
```

### 2. Deploy Application
```bash
# Deploy database (if not managed externally)
kubectl apply -f postgres-statefulset.yaml

# Run migrations (handled by init container)
kubectl apply -f deployment.yaml

# Expose service
kubectl apply -f service.yaml

# Configure autoscaling
kubectl apply -f hpa.yaml

# Setup monitoring
kubectl apply -f service-monitor.yaml
```

### 3. Verify Deployment
```bash
# Check pod status
kubectl get pods -n tool-registry

# Check logs
kubectl logs -f deployment/tool-registry -n tool-registry

# Check service endpoint
kubectl port-forward svc/tool-registry-service 8080:80 -n tool-registry
curl http://localhost:8080/health
```

## Performance Tuning

### 1. Database Optimization
```sql
-- PostgreSQL configuration for pgvector
-- postgresql.conf
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB

-- pgvector index optimization
SET ivfflat.probes = 10;  -- Adjust for accuracy vs speed
```

### 2. Application Performance
```yaml
# Increase replicas for load
kubectl scale deployment tool-registry --replicas=5 -n tool-registry

# Adjust resource limits
kubectl patch deployment tool-registry -p '{"spec":{"template":{"spec":{"containers":[{"name":"tool-registry","resources":{"limits":{"cpu":"2000m","memory":"2Gi"}}}]}}}}' -n tool-registry
```

## Backup and Recovery

### 1. Database Backup
```bash
# Create backup
kubectl exec -it postgres-0 -n tool-registry -- \
  pg_dump -U postgres toolregistry > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
kubectl exec -i postgres-0 -n tool-registry -- \
  psql -U postgres toolregistry < backup_file.sql
```

### 2. Application State
- Tool registry data stored in PostgreSQL
- No persistent application state required
- Configuration via environment variables

## Troubleshooting

### Common Issues

1. **Container won't start**
   ```bash
   # Check logs
   kubectl logs deployment/tool-registry -n tool-registry

   # Check environment variables
   kubectl describe deployment tool-registry -n tool-registry
   ```

2. **Database connection issues**
   ```bash
   # Test database connectivity
   kubectl exec -it deployment/tool-registry -n tool-registry -- \
     python3.9 -c "import asyncpg; asyncio.run(asyncpg.connect('postgresql+asyncpg://...'))"
   ```

3. **High memory usage**
   ```bash
   # Check resource usage
   kubectl top pods -n tool-registry

   # Check for memory leaks
   kubectl logs deployment/tool-registry -n tool-registry | grep "memory"
   ```

### Health Check Failures
1. **Database health**: Check PostgreSQL connection
2. **Embedding service**: Verify external service availability
3. **Resource limits**: Check memory/CPU constraints

## Rollback Procedures

### 1. Quick Rollback
```bash
# Rollback to previous deployment
kubectl rollout undo deployment/tool-registry -n tool-registry

# Check rollback status
kubectl rollout status deployment/tool-registry -n tool-registry
```

### 2. Emergency Rollback
```bash
# Scale to zero to stop all traffic
kubectl scale deployment tool-registry --replicas=0 -n tool-registry

# Deploy previous version
kubectl apply -f previous-deployment.yaml

# Restore service
kubectl scale deployment tool-registry --replicas=3 -n tool-registry
```

## Maintenance

### Regular Tasks
1. **Monitor resource usage**
2. **Check health endpoints**
3. **Review security logs**
4. **Update base images**
5. **Test disaster recovery**

### Updates
1. **Update application**: Rolling deployment strategy
2. **Update dependencies**: Test in staging first
3. **Update base image**: Rebuild and test container
4. **Database updates**: Run migrations during maintenance window

## Support

For deployment issues:
- Check logs: `kubectl logs -f deployment/tool-registry -n tool-registry`
- Verify configuration: `kubectl describe deployment tool-registry -n tool-registry`
- Test locally: `docker run -p 8000:8000 tool-registry:ubi8`

---

**Last Updated**: 2025-12-11
**Version**: 1.0.0