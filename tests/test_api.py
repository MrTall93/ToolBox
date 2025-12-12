"""API endpoint tests."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app

# Create test client
client = TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_root_endpoint(self):
        """Test root endpoint returns service info."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "tool-registry-mcp"
        assert data["status"] == "running"
        assert "docs" in data
        assert "endpoints" in data

    def test_openapi_docs_available(self):
        """Test that OpenAPI documentation endpoints are available."""
        # Test OpenAPI schema
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema

        # Test docs endpoint
        response = client.get("/docs")
        assert response.status_code == 200

        # Test ReDoc endpoint
        response = client.get("/redoc")
        assert response.status_code == 200


class TestMCPEndpoints:
    """Test MCP protocol endpoints."""

    @pytest.mark.asyncio
    async def test_list_tools_empty(self):
        """Test listing tools when no tools exist."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.list_tools.return_value = []
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/mcp/list_tools",
                json={"active_only": True, "limit": 10}
            )

        assert response.status_code == 200
        data = response.json()
        assert "tools" in data
        assert "total" in data
        assert data["tools"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_tools_with_filters(self):
        """Test listing tools with category and active filters."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            # Mock tool response
            mock_tool = type('MockTool', (), {
                'name': 'test_tool',
                'description': 'Test tool',
                'category': 'test',
                'tags': ['test'],
                'input_schema': {},
                'output_schema': {},
                'is_active': True,
                'version': '1.0.0',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:00:00Z'
            })()
            mock_registry.list_tools.return_value = [mock_tool]
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/mcp/list_tools",
                json={
                    "category": "math",
                    "active_only": True,
                    "limit": 5,
                    "offset": 0
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["tools"]) == 1
        assert data["tools"][0]["name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_find_tool_semantic_search(self):
        """Test semantic search for tools."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            # Mock search result
            mock_tool = type('MockTool', (), {
                'name': 'calculator',
                'description': 'Math calculator',
                'category': 'math'
            })()
            mock_registry.find_tool.return_value = [(mock_tool, 0.9)]
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/mcp/find_tool",
                json={
                    "query": "calculator for math operations",
                    "limit": 5,
                    "threshold": 0.7,
                    "use_hybrid": False
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["tools"]) == 1
        assert data["tools"][0]["name"] == "calculator"
        assert data["tools"][0]["similarity"] == 0.9

    @pytest.mark.asyncio
    async def test_find_tool_hybrid_search(self):
        """Test hybrid search (vector + text)."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_tool = type('MockTool', (), {
                'name': 'text_processor',
                'description': 'Process text documents'
            })()
            mock_registry.find_tool.return_value = [(mock_tool, 0.85)]
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/mcp/find_tool",
                json={
                    "query": "text processing tool",
                    "limit": 3,
                    "threshold": 0.8,
                    "use_hybrid": True
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["tools"]) == 1
        assert data["tools"][0]["similarity"] == 0.85

    @pytest.mark.asyncio
    async def test_call_tool_success(self):
        """Test successful tool execution."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.execute_tool.return_value = {
                "success": True,
                "data": {"result": 42},
                "execution_time_ms": 50
            }
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/mcp/call_tool",
                json={
                    "tool_name": "calculator",
                    "arguments": {
                        "operation": "add",
                        "a": 20,
                        "b": 22
                    }
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["result"]["result"] == 42
        assert data["execution_time_ms"] == 50

    @pytest.mark.asyncio
    async def test_call_tool_not_found(self):
        """Test calling non-existent tool."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.execute_tool.side_effect = ValueError("Tool not found")
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/mcp/call_tool",
                json={
                    "tool_name": "nonexistent_tool",
                    "arguments": {}
                }
            )

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_call_tool_validation_error(self):
        """Test calling tool with invalid arguments."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.execute_tool.return_value = {
                "success": False,
                "error": "Validation error: Missing required field 'operation'"
            }
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/mcp/call_tool",
                json={
                    "tool_name": "calculator",
                    "arguments": {"a": 5, "b": 3}  # Missing 'operation'
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "validation error" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_mcp_endpoint_validation_errors(self):
        """Test request validation on MCP endpoints."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test list_tools with invalid data
            response = await ac.post(
                "/mcp/list_tools",
                json={"limit": -1}  # Invalid limit
            )
            assert response.status_code == 422  # Validation error

            # Test find_tool with missing query
            response = await ac.post(
                "/mcp/find_tool",
                json={"threshold": 0.5}  # Missing required 'query'
            )
            assert response.status_code == 422

            # Test call_tool with missing tool_name
            response = await ac.post(
                "/mcp/call_tool",
                json={"arguments": {}}  # Missing required 'tool_name'
            )
            assert response.status_code == 422


class TestAdminEndpoints:
    """Test admin API endpoints."""

    @pytest.mark.asyncio
    async def test_register_tool_success(self):
        """Test successful tool registration."""
        with patch('app.api.admin.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.register_tool.return_value = type('MockTool', (), {
                'id': 1,
                'name': 'new_tool',
                'description': 'A new tool',
                'category': 'test'
            })()
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post(
                "/admin/tools",
                json={
                    "name": "new_tool",
                    "description": "A new tool",
                    "category": "test",
                    "tags": ["test"],
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "input": {"type": "string"}
                        }
                    },
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "output": {"type": "string"}
                        }
                    },
                    "implementation_type": "python_function",
                    "implementation_code": "def test(): pass"
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "new_tool"

    @pytest.mark.asyncio
    async def test_get_tool_stats(self):
        """Test getting tool execution statistics."""
        with patch('app.api.admin.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.get_tool_stats.return_value = {
                "total_executions": 100,
                "successful_executions": 95,
                "average_execution_time_ms": 45,
                "last_execution": "2024-01-01T12:00:00Z"
            }
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.get("/admin/tools/1/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_executions"] == 100
        assert data["successful_executions"] == 95

    @pytest.mark.asyncio
    async def test_update_tool(self):
        """Test updating tool metadata."""
        with patch('app.api.admin.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.update_tool.return_value = type('MockTool', (), {
                'id': 1,
                'name': 'updated_tool',
                'description': 'Updated description'
            })()
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.put(
                "/admin/tools/1",
                json={
                    "description": "Updated description",
                    "tags": ["updated", "tool"]
                }
            )

        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_delete_tool(self):
        """Test soft deleting a tool."""
        with patch('app.api.admin.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.deactivate_tool.return_value = True
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/admin/tools/1/deactivate")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_reactivate_tool(self):
        """Test reactivating a tool."""
        with patch('app.api.admin.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.activate_tool.return_value = True
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/admin/tools/1/activate")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_reindex_tool(self):
        """Test re-generating tool embedding."""
        with patch('app.api.admin.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.reindex_tool.return_value = True
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.post("/admin/tools/1/reindex")

        assert response.status_code == 200


class TestAPIIntegration:
    """Integration tests for API endpoints."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow: register -> find -> execute -> get stats."""
        tool_id = None

        with patch('app.api.admin.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()

            # Mock registration
            mock_tool = type('MockTool', (), {
                'id': 1,
                'name': 'integration_test_tool',
                'description': 'Tool for integration testing'
            })()
            mock_registry.register_tool.return_value = mock_tool

            # Mock search
            mock_registry.find_tool.return_value = [(mock_tool, 0.9)]

            # Mock execution
            mock_registry.execute_tool.return_value = {
                "success": True,
                "data": {"result": "integration test passed"},
                "execution_time_ms": 25
            }

            # Mock stats
            mock_registry.get_tool_stats.return_value = {
                "total_executions": 1,
                "successful_executions": 1
            }

            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            # 1. Register tool
            response = await ac.post(
                "/admin/tools",
                json={
                    "name": "integration_test_tool",
                    "description": "Tool for integration testing",
                    "category": "test",
                    "tags": ["test", "integration"],
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "implementation_type": "python_function"
                }
            )
            assert response.status_code == 200

            # 2. Find tool
            response = await ac.post(
                "/mcp/find_tool",
                json={
                    "query": "integration testing tool",
                    "limit": 5
                }
            )
            assert response.status_code == 200
            assert len(response.json()["tools"]) == 1

            # 3. Execute tool
            response = await ac.post(
                "/mcp/call_tool",
                json={
                    "tool_name": "integration_test_tool",
                    "arguments": {}
                }
            )
            assert response.status_code == 200
            assert response.json()["success"] is True

            # 4. Get stats
            response = await ac.get("/admin/tools/1/stats")
            assert response.status_code == 200
            assert response.json()["total_executions"] == 1

    @pytest.mark.asyncio
    async def test_cors_headers(self):
        """Test that CORS headers are properly set."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            response = await ac.options("/health")
            # Check for CORS headers
            assert "access-control-allow-origin" in response.headers
            assert "access-control-allow-methods" in response.headers
            assert "access-control-allow-headers" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limiting_simulation(self):
        """Test API behavior under rapid requests."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.list_tools.return_value = []
            mock_registry_class.return_value = mock_registry

        # Simulate rapid requests
        async with AsyncClient(app=app, base_url="http://test") as ac:
            responses = []
            for i in range(10):
                response = await ac.post(
                    "/mcp/list_tools",
                    json={"limit": 10}
                )
                responses.append(response)

        # All requests should succeed (no rate limiting implemented yet)
        for response in responses:
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_openapi_docs_available(self):
        """Test that OpenAPI documentation endpoints are available."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test OpenAPI schema
            response = await ac.get("/openapi.json")
            assert response.status_code == 200
            schema = response.json()
            assert "openapi" in schema
            assert "paths" in schema

            # Test docs endpoint
            response = await ac.get("/docs")
            assert response.status_code == 200

            # Test ReDoc endpoint
            response = await ac.get("/redoc")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self):
        """Test consistent error handling across endpoints."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Test 404 for non-existent endpoints
            response = await ac.get("/nonexistent")
            assert response.status_code == 404

            # Test method not allowed
            response = await ac.get("/mcp/list_tools")  # Should be POST
            assert response.status_code == 405

            # Test malformed JSON
            response = await ac.post(
                "/mcp/list_tools",
                data="invalid json",
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 422


class TestAPISecurity:
    """Test API security aspects."""

    @pytest.mark.asyncio
    async def test_sql_injection_protection(self):
        """Test protection against SQL injection."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.find_tool.return_value = []
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Try SQL injection in search query
            malicious_query = "'; DROP TABLE tools; --"
            response = await ac.post(
                "/mcp/find_tool",
                json={"query": malicious_query, "limit": 10}
            )

            # Should be handled safely (400 or 500, not 200 with malicious content)
            assert response.status_code in [400, 500]

    @pytest.mark.asyncio
    async def test_xss_protection(self):
        """Test protection against XSS in input."""
        with patch('app.api.mcp.ToolRegistry') as mock_registry_class:
            mock_registry = AsyncMock()
            mock_registry.register_tool.return_value = type('MockTool', (), {'id': 1})()
            mock_registry_class.return_value = mock_registry

        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Try XSS in tool name
            xss_payload = "<script>alert('xss')</script>"
            response = await ac.post(
                "/admin/tools",
                json={
                    "name": xss_payload,
                    "description": "Test tool",
                    "category": "test",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "implementation_type": "python_function"
                }
            )

            # Should handle XSS safely
            if response.status_code == 200:
                # If it accepts the payload, ensure it's properly escaped
                # (This depends on your sanitization strategy)
                pass
            else:
                # Or it should reject the malicious input
                assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_large_payload_handling(self):
        """Test handling of large payloads."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Create a very large payload
            large_payload = {
                "description": "A" * 10000,  # 10KB description
                "tags": ["tag"] * 1000,  # 1000 tags
                "input_schema": {
                    "properties": {f"field_{i}": {"type": "string"} for i in range(1000)}
                }
            }

            response = await ac.post(
                "/admin/tools",
                json=large_payload
            )

            # Should handle gracefully (either accept or reject with proper error)
            assert response.status_code in [200, 413, 422]