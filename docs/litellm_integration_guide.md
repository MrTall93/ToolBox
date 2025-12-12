# LiteLLM Integration Guide

This guide shows how to connect your Tool Registry MCP Server to an existing LiteLLM deployment.

## Quick Setup

### 1. Configure LiteLLM MCP Connection

Since LiteLLM is already deployed, you just need to configure it to connect to your Tool Registry MCP Server.

#### **Option A: Update LiteLLM Configuration**

Add this to your LiteLLM configuration file:

```yaml
# litellm_config.yaml
model_list:
  # Your existing model configurations
  - model_name: "gpt-4"
    litellm_params:
      model: "openai/gpt-4"
      api_key: "${OPENAI_API_KEY}"

# Tool Registry MCP Server integration
mcp_servers:
  - name: "tool-registry"
    description: "Tool Registry for semantic tool discovery"
    connection:
      host: "localhost"          # Update to your Tool Registry host
      port: 8000                # Update to your Tool Registry port
      protocol: "http"
      base_path: "/mcp"
      auth:
        type: "api_key"
        api_key: "${TOOL_REGISTRY_API_KEY}"

    # Tool registry settings
    tool_registry:
      discovery:
        semantic_search: true
        similarity_threshold: 0.7
        max_results: 10
      execution:
        enabled: true
        timeout: 60
      cache:
        enabled: true
        ttl: 300
```

#### **Option B: Environment Variables**

Set these environment variables in your LiteLLM deployment:

```bash
# Tool Registry MCP Server connection
TOOL_REGISTRY_HOST=localhost
TOOL_REGISTRY_PORT=8000
TOOL_REGISTRY_API_KEY=your-tool-registry-api-key

# MCP Configuration
MCP_SERVERS_0_NAME=tool-registry
MCP_SERVERS_0_HOST=${TOOL_REGISTRY_HOST}
MCP_SERVERS_0_PORT=${TOOL_REGISTRY_PORT}
MCP_SERVERS_0_API_KEY=${TOOL_REGISTRY_API_KEY}
```

### 2. Update Tool Registry Configuration

Make sure your Tool Registry is configured to work with LiteLLM:

#### **app/config.py** additions:

```python
# Add to your Settings class
class Settings(BaseSettings):
    # ... existing settings ...

    # LiteLLM Integration
    LITELM_MCP_ENABLED: bool = True
    LITELM_MCP_TIMEOUT: int = 30
    LITELM_MCP_MAX_RETRIES: int = 3

    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v) -> List[str]:
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(origin).rstrip("/") for origin in v if origin]
        return []
```

#### **Environment variables for Tool Registry:**

```bash
# Add to your Tool Registry .env file
LITELM_MCP_ENABLED=true
LITELM_MCP_TIMEOUT=30
LITELM_MCP_MAX_RETRIES=3

# Make sure to include LiteLLM's origin in CORS
CORS_ORIGINS=http://localhost:4000,http://localhost:3000,http://localhost:8000
```

### 3. Test the Integration

Use this Python script to test the connection:

```python
import asyncio
import httpx
import os

async def test_litellm_mcp_connection():
    """Test connection between LiteLLM and Tool Registry MCP Server."""

    # Tool Registry MCP endpoint
    tool_registry_url = "http://localhost:8000/mcp"
    api_key = os.getenv("TOOL_REGISTRY_API_KEY", "your-api-key")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    async with httpx.AsyncClient() as client:
        try:
            # Test health check
            health_response = await client.get("http://localhost:8000/health")
            print(f"Tool Registry Health: {health_response.status_code}")

            # Test tool listing
            tools_response = await client.post(
                f"{tool_registry_url}/list_tools",
                json={"limit": 5},
                headers=headers
            )

            if tools_response.status_code == 200:
                tools = tools_response.json()
                print(f"✅ Found {len(tools.get('tools', []))} tools")

                # Test tool search
                search_response = await client.post(
                    f"{tool_registry_url}/find_tool",
                    json={"query": "calculator", "limit": 3},
                    headers=headers
                )

                if search_response.status_code == 200:
                    results = search_response.json()
                    print(f"✅ Found {len(results.get('results', []))} calculator tools")

                    return True
                else:
                    print(f"❌ Search failed: {search_response.status_code}")
                    return False
            else:
                print(f"❌ Tool listing failed: {tools_response.status_code}")
                print(f"Response: {tools_response.text}")
                return False

        except Exception as e:
            print(f"❌ Connection error: {str(e)}")
            return False

# Run the test
if __name__ == "__main__":
    result = asyncio.run(test_litellm_mcp_connection())
    if result:
        print("🎉 LiteLLM + Tool Registry integration is working!")
    else:
        print("⚠️ Integration needs attention")
```

### 4. Use with LiteLLM

Once connected, you can use tools through LiteLLM:

```python
import litellm

# Example with tool usage
response = litellm.completion(
    model="gpt-4",
    messages=[{
        "role": "user",
        "content": "Calculate 15 + 27 and then format the result as a currency"
    }],
    tools="auto"  # LiteLLM will automatically discover tools from your MCP server
)

print(response.choices[0].message.content)
```

## Configuration Options

### Tool Registry Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `LITELM_MCP_ENABLED` | `true` | Enable LiteLLM MCP integration |
| `LITELM_MCP_TIMEOUT` | `30` | Request timeout in seconds |
| `LITELM_MCP_MAX_RETRIES` | `3` | Maximum retry attempts |

### LiteLLM Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `semantic_search` | `true` | Enable semantic tool discovery |
| `similarity_threshold` | `0.7` | Minimum similarity for search results |
| `max_results` | `10` | Maximum tools to return from search |
| `cache.enabled` | `true` | Enable tool discovery caching |
| `cache.ttl` | `300` | Cache TTL in seconds |

## Troubleshooting

### Common Issues

#### **1. CORS Errors**
```
Access blocked by CORS policy
```

**Solution:** Add LiteLLM's origin to your Tool Registry CORS settings:
```bash
CORS_ORIGINS=http://your-litellm-host:4000,http://localhost:3000
```

#### **2. Authentication Errors**
```
401 Unauthorized
```

**Solution:** Ensure API keys are configured correctly:
```bash
# In Tool Registry .env
API_KEY=your-tool-registry-api-key

# In LiteLLM config
TOOL_REGISTRY_API_KEY=your-tool-registry-api-key
```

#### **3. Connection Timeouts**
```
Request timeout
```

**Solution:** Increase timeout settings:
```bash
# In Tool Registry .env
LITELM_MCP_TIMEOUT=60

# In LiteLLM config
timeout: 60
```

#### **4. Tool Not Found**
```
Tool 'xyz' not found
```

**Solution:** Check if tools are registered and active:
```bash
curl -X POST http://localhost:8000/mcp/list_tools \
  -H "Authorization: Bearer your-api-key" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
# Tool Registry
LOG_LEVEL=DEBUG

# LiteLLM
LITELM_LOG=DEBUG
LITELM_DEBUG=True
```

## Monitoring

### Health Checks

Monitor the integration with these endpoints:

- **Tool Registry Health:** `GET /health`
- **LiteLLM Health:** `GET /health` (on your LiteLLM instance)

### Metrics

Enable Prometheus metrics for monitoring:

```yaml
# In Tool Registry config
monitoring:
  metrics:
    enabled: true
    port: 9090
```

Key metrics to monitor:
- Tool registry request rate
- Tool execution latency
- Error rates
- Cache hit rates

## Production Tips

### 1. Security
- Use HTTPS for all communications
- Rotate API keys regularly
- Enable rate limiting
- Monitor access logs

### 2. Performance
- Enable Redis caching in LiteLLM
- Use connection pooling
- Monitor memory usage
- Set appropriate timeouts

### 3. Reliability
- Configure health checks
- Set up alerting
- Use circuit breakers
- Implement retry logic

### 4. Scaling
- Use horizontal scaling for Tool Registry
- Configure auto-scaling based on load
- Load balance between multiple instances
- Monitor resource utilization

## Examples

### Basic Tool Usage

```python
import litellm

# Simple tool execution
response = litellm.completion(
    model="gpt-4",
    messages=[{
        "role": "user",
        "content": "Find tools for data analysis"
    }],
    tools="auto"
)
```

### Advanced Tool Discovery

```python
# Search for specific tools
response = litellm.completion(
    model="gpt-4",
    messages=[{
        "role": "user",
        "content": "I need to process a CSV file and calculate statistics"
    }],
    tools="auto",
    tool_choice="auto"  # Force tool usage
)
```

### Error Handling

```python
import litellm

try:
    response = litellm.completion(
        model="gpt-4",
        messages=[{"role": "user", "content": "Execute tool xyz"}],
        tools="auto"
    )
except Exception as e:
    print(f"Tool execution failed: {e}")
    # Implement retry logic or fallback
```

This integration allows your existing LiteLLM deployment to discover and use tools from your Tool Registry MCP Server seamlessly!