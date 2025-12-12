# Tool Registry Helm Chart

A Helm chart for deploying the Tool Registry MCP Server to Kubernetes.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.0+
- PostgreSQL (included as dependency)

## Installation

### Add the repository

```bash
helm repo add tool-registry https://charts.yourdomain.com
helm repo update
```

### Install the chart

```bash
# Development installation
helm install my-tool-registry tool-registry/tool-registry \
  --namespace tool-registry-dev \
  --create-namespace \
  --values values-dev.yaml

# Production installation
helm install my-tool-registry tool-registry/tool-registry \
  --namespace tool-registry-prod \
  --create-namespace \
  --values values-prod.yaml
```

### Upgrade the chart

```bash
helm upgrade my-tool-registry tool-registry/tool-registry \
  --namespace tool-registry \
  --values values-prod.yaml
```

### Uninstall the chart

```bash
helm uninstall my-tool-registry --namespace tool-registry
```

## Configuration

The following table lists the configurable parameters of the Tool Registry chart and their default values.

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of replicas | `3` |
| `image.registry` | Image registry | `docker.io` |
| `image.repository` | Image repository | `tool-registry` |
| `image.tag` | Image tag | `latest` |
| `image.pullPolicy` | Image pull policy | `IfNotPresent` |
| `service.type` | Service type | `ClusterIP` |
| `service.port` | Service port | `80` |
| `ingress.enabled` | Enable ingress | `true` |
| `ingress.className` | Ingress class name | `nginx` |
| `ingress.hosts[0].host` | Ingress hostname | `tool-registry.yourdomain.com` |
| `resources.requests.memory` | Memory request | `512Mi` |
| `resources.requests.cpu` | CPU request | `250m` |
| `resources.limits.memory` | Memory limit | `1Gi` |
| `resources.limits.cpu` | CPU limit | `500m` |
| `autoscaling.enabled` | Enable HPA | `true` |
| `autoscaling.minReplicas` | Minimum replicas | `2` |
| `autoscaling.maxReplicas` | Maximum replicas | `20` |
| `postgresql.enabled` | Enable PostgreSQL | `true` |
| `postgresql.auth.postgresPassword` | PostgreSQL admin password | `""` |
| `postgresql.auth.username` | PostgreSQL username | `tool-registry` |
| `postgresql.auth.password` | PostgreSQL password | `""` |
| `postgresql.auth.database` | PostgreSQL database | `tool-registry` |
| `monitoring.enabled` | Enable monitoring | `true` |
| `networkPolicy.enabled` | Enable network policies | `true` |

### Environment-Specific Values

#### Development (`values-dev.yaml`)
- Single replica
- Reduced resource requirements
- Debug logging enabled
- Rate limiting disabled
- No monitoring or network policies

#### Production (`values-prod.yaml`)
- 5 replicas with autoscaling
- Increased resource requirements
- Production logging level
- Rate limiting enabled
- Full monitoring and security

## Secrets

The chart supports several methods for managing secrets:

1. **Auto-generation**: Set `secrets.generate: true` to automatically generate random secrets
2. **Values file**: Set secrets in the `secrets` section of your values file
3. **External secret management**: Use your preferred secret management system and reference existing secrets

### Required Secrets

- `databaseUrl`: PostgreSQL connection string
- `secretKey`: Application secret key
- `embeddingApiKey`: Embedding service API key
- `apiKey`: Admin API key

## Monitoring

The chart includes optional monitoring with Prometheus:

- ServiceMonitor for Prometheus scraping
- PrometheusRules for alerting
- Pre-configured alerting rules for common scenarios

To enable monitoring:

```yaml
monitoring:
  enabled: true
  serviceMonitor:
    enabled: true
    namespace: monitoring
  prometheusRule:
    enabled: true
    namespace: monitoring
```

## Production Deployment

For production deployment, use the provided `values-prod.yaml` as a starting point and customize:

```bash
helm install my-tool-registry tool-registry/tool-registry \
  --namespace tool-registry-prod \
  --create-namespace \
  --values values-prod.yaml \
  --set secrets.databaseUrl="postgresql+asyncpg://user:pass@host:5432/db" \
  --set secrets.embeddingApiKey="your-embedding-api-key" \
  --set secrets.secretKey="your-secret-key"
```

## Migration from Kubernetes Manifests

If you're migrating from the existing Kubernetes manifests:

1. Export current configuration
2. Create a `values.yaml` based on your current setup
3. Install the Helm chart with your custom values
4. Verify the deployment matches your expectations

## Troubleshooting

### Common Issues

1. **Pods not starting**: Check resource limits and node availability
2. **Database connection issues**: Verify PostgreSQL password and connection string
3. **Embedding service errors**: Confirm embedding service URL and API key
4. **Ingress issues**: Check ingress controller configuration and DNS

### Debug Commands

```bash
# Check pod status
kubectl get pods -n tool-registry

# Check pod logs
kubectl logs -f deployment/my-tool-registry -n tool-registry

# Check events
kubectl get events -n tool-registry --sort-by='.lastTimestamp'

# Describe pod
kubectl describe pod -l app.kubernetes.io/name=tool-registry -n tool-registry

# Port forward for local testing
kubectl port-forward svc/my-tool-registry-service 8000:80 -n tool-registry
```

## Development

For local development:

```bash
# Install with development values
helm install my-tool-registry . \
  --namespace tool-registry-dev \
  --create-namespace \
  --values values-dev.yaml

# Port forward for local testing
kubectl port-forward svc/my-tool-registry-service 8000:80 -n tool-registry-dev

# Test the API
curl http://localhost:8000/health
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `helm template`
5. Submit a pull request

## License

This chart is licensed under the MIT License.