# Production Docker Image Options

## Summary
Three production-ready Docker images are available for the Tool Registry MCP Server:

### 1. **Alpine Linux (Recommended for Security)**
- **File**: `Dockerfile.alpine`
- **Tag**: `tool-registry:alpine`
- **Size**: ~250MB
- **CVEs**: 0 vulnerabilities ✅
- **User**: Non-root (UID: 1000)
- **Base**: Python 3.14 Alpine

### 2. **Red Hat UBI8 (Enterprise Production)**
- **File**: `Dockerfile.ubi8`
- **Tag**: `tool-registry:ubi8`
- **Size**: ~368MB
- **CVEs**: 27 vulnerabilities (mostly system packages)
- **User**: Non-root (UID: 1000)
- **Base**: Red Hat Universal Base Image 8 with Python 3.9
- **Support**: Long-term enterprise support

### 3. **Debian Slim (Development)**
- **File**: `Dockerfile`
- **Tag**: `tool-registry:latest`
- **Size**: ~450MB
- **CVEs**: 29 vulnerabilities
- **User**: Non-root (UID: 1000)
- **Base**: Python 3.14 Debian Slim

## Production Recommendations

### For Maximum Security
```bash
docker build -f Dockerfile.alpine -t tool-registry:production .
```

### For Enterprise Environments
```bash
docker build -f Dockerfile.ubi8 -t tool-registry:production .
```

## Security Features Common to All Images
- ✅ Non-root user execution (UID: 1000)
- ✅ Minimal attack surface
- ✅ Multi-stage builds
- ✅ No build tools in runtime image
- ✅ Proper file permissions
- ✅ Health checks enabled

## Runtime Verification
All images have been tested and verified to:
- Start successfully with non-root user
- Run the application correctly
- Pass health checks
- Handle permissions properly

## Deployment Notes

### Environment Variables Required
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
SECRET_KEY=your-secret-key
```

### Ports
- Application: `8000`
- Health check: HTTP `/health`

### Volumes (Optional)
- `/app/logs` - Application logs
- `/app/tmp` - Temporary files

## Docker Scout Results
- **Alpine**: 0 CVEs (Cleanest)
- **UBI8**: 27 CVEs (System packages, acceptable for enterprise)
- **Debian**: 29 CVEs (Development only)

## Build Commands
```bash
# Alpine (Recommended)
docker build -f Dockerfile.alpine -t tool-registry:alpine .

# UBI8 (Enterprise)
docker build -f Dockerfile.ubi8 -t tool-registry:ubi8 .

# Debian (Development)
docker build -f Dockerfile -t tool-registry:latest .
```

## Docker Compose Example
```yaml
version: '3.8'
services:
  tool-registry:
    image: tool-registry:ubi8  # or :alpine for max security
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/toolregistry
      - SECRET_KEY=production-secret-key
    ports:
      - "8000:8000"
    depends_on:
      - db
    restart: unless-stopped

  db:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_DB=toolregistry
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

volumes:
  postgres_data:
```