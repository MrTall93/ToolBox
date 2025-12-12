# Container Security Policy

## Security Overview

This document outlines the security measures implemented for the Tool Registry MCP Server containers.

## Available Docker Images

### 1. **Dockerfile.ubi8 (Enterprise Production)**
- **Base**: Red Hat Universal Base Image 8 with Python 3.9
- **Security Features**:
  - ✅ Non-root user (UID: 1000)
  - ✅ Minimal packages
  - ✅ Multi-stage build
  - ✅ Enterprise support
  - ✅ CVE scanning compatible
- **Trade-offs**: Some system package vulnerabilities (acceptable in enterprise)

### 2. **Dockerfile.alpine (Maximum Security)**
- **Base**: Python 3.14 Alpine Linux
- **Security Features**:
  - ✅ Zero CVEs in latest scan
  - ✅ Minimal attack surface
  - ✅ Musl libc (smaller than glibc)
  - ✅ Non-root user (UID: 1000)
- **Best for**: High-security environments

### 3. **Dockerfile.hardened (Hardened Runtime)**
- **Base**: Google Distroless Python
- **Security Features**:
  - ✅ Minimal runtime (no shell, package manager)
  - ✅ Reduced attack surface
  - ✅ Non-root user
  - ✅ No unnecessary tools
- **Trade-offs**: Harder to debug, limited runtime capabilities

## Security Features Implemented

### ✅ User Security
- **Non-root Execution**: All images run as non-root user
  - UBI8/Alpine: UID 1000 (appuser)
  - Hardened: UID 65534 (nobody)
- **Dedicated Group**: Separate user group for isolation
- **Limited Permissions**: Minimal file permissions

### ✅ Image Security
- **Multi-stage Builds**: No build tools in runtime
- **Minimal Base Images**: Small attack surface
- **No Vulnerable Packages**: Regular CVE scanning
- **Package Pinning**: Fixed package versions

### ✅ Runtime Security
- **Signal Handling**: Graceful shutdown on SIGTERM/SIGINT
- **Resource Limits**: Configurable memory/CPU limits
- **Health Checks**: Automated health monitoring
- **Readiness Probes**: Kubernetes-ready

### ✅ Network Security
- **Port Exposure**: Only necessary ports exposed
- **Internal Communication**: Database connections secured
- **CORS Configuration**: Controlled cross-origin requests

### ✅ File System Security
- **Read-only Root**: Optional read-only root filesystem
- **No SUID/SGID**: Dangerous binaries removed
- **Secure Directories**: Proper permissions on /app
- **No Secrets in Image**: Environment variables only

## Security Scanning Results

### Latest CVE Scan (Docker Scout)

| Image | Critical | High | Medium | Low | Total |
|-------|----------|------|--------|-----|-------|
| Alpine | 0 | 0 | 0 | 0 | ✅ 0 |
| UBI8 | 0 | 13 | 13 | 1 | ⚠️ 27 |
| Hardened | TBD | TBD | TBD | TBD | 🔄 Pending |

**Note**: UBI8 vulnerabilities are primarily in older system packages and are acceptable in enterprise environments with proper patch management.

## Kubernetes Security Configuration

### Pod Security Context
```yaml
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
```

### Network Policy
```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: tool-registry-netpol
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
          name: monitoring
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 5432  # PostgreSQL
```

## Production Deployment Checklist

### ✅ Pre-deployment
- [ ] Scan images with Docker Scout
- [ ] Verify non-root user execution
- [ ] Check health endpoints
- [ ] Validate resource limits
- [ ] Review environment variables

### ✅ Kubernetes Configuration
- [ ] Set pod security context
- [ ] Configure resource quotas
- [ ] Set up network policies
- [ ] Enable liveness/readiness probes
- [ ] Configure service accounts

### ✅ Runtime Monitoring
- [ ] Container runtime security (Falco, Trivy)
- [ ] Network traffic monitoring
- [ ] Resource usage monitoring
- [ ] Log aggregation
- [ ] Alert configuration

## Security Best Practices

### ✅ Build Time
1. **Use minimal base images**
2. **Multi-stage builds**
3. **Pin package versions**
4. **Scan for vulnerabilities**
5. **Sign images (cosign)**

### ✅ Runtime
1. **Run as non-root**
2. **Read-only filesystem**
3. **Resource limits**
4. **Network policies**
5. **Regular updates**

### ✅ Operations
1. **Secrets management**
2. **Audit logging**
3. **Monitoring & alerting**
4. **Backup procedures**
5. **Incident response**

## Container Runtime Options

### Docker Run Command
```bash
docker run \
  --read-only \
  --tmpfs /app/tmp \
  --tmpfs /app/logs \
  --pids-limit 100 \
  --memory 512m \
  --cpus 0.5 \
  --security-opt no-new-privileges \
  --cap-drop ALL \
  --user 1000:1000 \
  -p 8000:8000 \
  tool-registry:ubi8
```

### Kubernetes Security Context
```yaml
apiVersion: v1
kind: Pod
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    readOnlyRootFilesystem: true
    allowPrivilegeEscalation: false
  containers:
  - name: tool-registry
    image: tool-registry:ubi8
    securityContext:
      capabilities:
        drop:
        - ALL
    resources:
      requests:
        memory: "256Mi"
        cpu: "250m"
      limits:
        memory: "512Mi"
        cpu: "500m"
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

## Compliance

### ✅ Standards Supported
- **CIS Docker Benchmark**: Controls implemented
- **NIST Cybersecurity Framework**: Security controls in place
- **SOC 2**: Security controls available
- **PCI DSS**: Card data protection (if applicable)

### ✅ Audit Trail
- Container image digests stored
- Build logs archived
- Security scan results maintained
- Runtime access logged

## Incident Response

### 🚨 Security Events
1. **Container Escape**: Immediate pod termination
2. **Resource Abuse**: Auto-scaling and rate limiting
3. **Data Exfiltration**: Network policy enforcement
4. **Malware Detection**: Image quarantine

### 📞 Response Procedures
1. **Detection**: Monitoring and alerting
2. **Containment**: Isolate affected pods
3. **Investigation**: Log analysis and forensics
4. **Recovery**: Rebuild and redeploy
5. **Post-mortem**: Update security controls

## Future Enhancements

### 🚧 Planned Security Features
- **Image Signing**: Cosign integration
- **SBOM Generation**: Software bill of materials
- **Runtime Protection**: Falco integration
- **Secrets Management**: HashiCorp Vault integration
- **Vulnerability Management**: Automated patching

## Contact

For security questions or concerns:
- **Security Team**: security@example.com
- **DevOps Team**: devops@example.com
- **Incident Response**: incidents@example.com

---

**Last Updated**: 2025-12-11
**Next Review**: 2025-12-25
**Security Owner**: Security Team