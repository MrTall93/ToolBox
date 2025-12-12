"""Container testing suite for Docker images."""

import asyncio
import os
import subprocess
import time
from typing import Dict, List, Optional
import httpx
import pytest


class ContainerTestSuite:
    """Test suite for Docker containers."""

    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.timeout = 30
        self.containers: Dict[str, str] = {}

    async def setup_container(self, image_tag: str, container_name: str,
                            env_vars: Optional[Dict[str, str]] = None) -> str:
        """Start a container and return its ID."""
        # Stop existing container if running
        try:
            subprocess.run(["docker", "stop", container_name],
                         capture_output=True, check=False)
        except:
            pass

        # Remove existing container if exists
        try:
            subprocess.run(["docker", "rm", container_name],
                         capture_output=True, check=False)
        except:
            pass

        # Prepare environment variables
        env_args = []
        if env_vars:
            for key, value in env_vars.items():
                env_args.extend(["-e", f"{key}={value}"])

        # Start new container
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", "8000:8000",
            "--read-only",
            "--tmpfs", "/app/tmp",
            "--tmpfs", "/app/logs",
            "--pids-limit", "100",
            "--memory", "256m",
            "--cpus", "0.5",
            "--security-opt", "no-new-privileges",
            "--cap-drop", "ALL"
        ] + env_args + [
            image_tag
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        container_id = result.stdout.strip()
        self.containers[container_name] = container_id

        # Wait for container to start
        await self._wait_for_ready()
        return container_id

    async def _wait_for_ready(self, max_attempts: int = 30) -> bool:
        """Wait for container to be ready."""
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{self.base_url}/ready", timeout=5)
                    if response.status_code == 200:
                        return True
            except:
                pass
            await asyncio.sleep(1)
        return False

    async def cleanup_container(self, container_name: str):
        """Stop and remove a container."""
        if container_name in self.containers:
            subprocess.run(["docker", "stop", container_name],
                         capture_output=True, check=False)
            subprocess.run(["docker", "rm", container_name],
                         capture_output=True, check=False)
            del self.containers[container_name]

    async def test_health_endpoint(self) -> bool:
        """Test the /health endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("status") == "healthy"
                return False
        except:
            return False

    async def test_liveness_endpoint(self) -> bool:
        """Test the /live endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/live", timeout=5)
                return response.status_code == 200
        except:
            return False

    async def test_readiness_endpoint(self) -> bool:
        """Test the /ready endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/ready", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("status") == "ready"
                return False
        except:
            return False

    async def test_root_endpoint(self) -> bool:
        """Test the / root endpoint."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/", timeout=5)
                return response.status_code == 200 and "name" in response.json()
        except:
            return False

    async def test_mcp_endpoints(self) -> bool:
        """Test MCP protocol endpoints."""
        try:
            async with httpx.AsyncClient() as client:
                # Test list_tools
                response = await client.post(
                    f"{self.base_url}/mcp/list_tools",
                    json={},
                    timeout=10
                )
                if response.status_code != 200:
                    return False

                # Test find_tool
                response = await client.post(
                    f"{self.base_url}/mcp/find_tool",
                    json={"query": "test", "limit": 5},
                    timeout=10
                )
                if response.status_code != 200:
                    return False

                return True
        except:
            return False

    async def test_user_permissions(self, container_name: str) -> bool:
        """Test that container is running as non-root user."""
        try:
            result = subprocess.run(
                ["docker", "exec", container_name, "id"],
                capture_output=True,
                text=True,
                check=True
            )
            output = result.stdout.strip()
            # Check that UID is not 0 (root)
            return "uid=0(root)" not in output
        except:
            return False

    async def test_file_permissions(self, container_name: str) -> bool:
        """Test that important files have correct permissions."""
        try:
            # Check that app directory is writable
            result = subprocess.run(
                ["docker", "exec", container_name, "test", "-w", "/app"],
                capture_output=True,
                check=True
            )
            return result.returncode == 0
        except:
            return False

    async def test_signal_handling(self, container_name: str) -> bool:
        """Test graceful shutdown on SIGTERM."""
        try:
            # Send SIGTERM
            subprocess.run(["docker", "kill", "-s", "TERM", container_name], check=True)

            # Wait for graceful shutdown (should take < 10 seconds)
            start_time = time.time()
            while True:
                result = subprocess.run(
                    ["docker", "inspect", "-f", "{{.State.Status}}", container_name],
                    capture_output=True,
                    text=True
                )
                status = result.stdout.strip()
                if status == "exited":
                    shutdown_time = time.time() - start_time
                    # Should exit gracefully within 10 seconds
                    return shutdown_time < 10
                if time.time() - start_time > 15:
                    # Force kill if it takes too long
                    subprocess.run(["docker", "kill", container_name], check=False)
                    return False
                await asyncio.sleep(0.5)
        except:
            return False

    async def test_resource_limits(self, container_name: str) -> bool:
        """Test that resource limits are enforced."""
        try:
            # Check memory limit
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.HostConfig.Memory}}", container_name],
                capture_output=True,
                text=True,
                check=True
            )
            memory_limit = int(result.stdout.strip())
            # Should be limited to 256MB
            return memory_limit == 256 * 1024 * 1024
        except:
            return False

    async def run_full_test_suite(self, image_tag: str,
                                env_vars: Optional[Dict[str, str]] = None) -> Dict[str, bool]:
        """Run the complete test suite for an image."""
        container_name = f"test-{image_tag.replace(':', '-').replace('/', '-')}"

        try:
            await self.setup_container(image_tag, container_name, env_vars)

            results = {
                "container_startup": True,
                "health_check": await self.test_health_endpoint(),
                "liveness_probe": await self.test_liveness_endpoint(),
                "readiness_probe": await self.test_readiness_endpoint(),
                "root_endpoint": await self.test_root_endpoint(),
                "mcp_endpoints": await self.test_mcp_endpoints(),
                "non_root_user": await self.test_user_permissions(container_name),
                "file_permissions": await self.test_file_permissions(container_name),
                "resource_limits": await self.test_resource_limits(container_name),
                "signal_handling": await self.test_signal_handling(container_name),
            }

            return results

        finally:
            await self.cleanup_container(container_name)


@pytest.fixture
def test_suite():
    """Create a test suite instance."""
    return ContainerTestSuite()


@pytest.mark.asyncio
async def test_ubi8_container(test_suite):
    """Test the UBI8 container image."""
    # Mock environment variables for testing
    env_vars = {
        "DATABASE_URL": "sqlite+aiosqlite:///test.db",
        "SECRET_KEY": "test-key",
        "EMBEDDING_BASE_URL": "http://localhost:8001/embed",
    }

    results = await test_suite.run_full_test_suite("tool-registry:ubi8", env_vars)

    # All tests should pass
    for test_name, passed in results.items():
        assert passed, f"Test '{test_name}' failed for UBI8 container"

    print(f"✅ UBI8 Container Tests: {sum(results.values())}/{len(results)} passed")


@pytest.mark.asyncio
async def test_alpine_container(test_suite):
    """Test the Alpine container image."""
    # Build Alpine image if not exists
    try:
        subprocess.run(["docker", "build", "-f", "Dockerfile.alpine",
                       "-t", "tool-registry:alpine", "."], check=True)
    except subprocess.CalledProcessError:
        pytest.skip("Could not build Alpine image")

    env_vars = {
        "DATABASE_URL": "sqlite+aiosqlite:///test.db",
        "SECRET_KEY": "test-key",
        "EMBEDDING_BASE_URL": "http://localhost:8001/embed",
    }

    results = await test_suite.run_full_test_suite("tool-registry:alpine", env_vars)

    # All tests should pass
    for test_name, passed in results.items():
        assert passed, f"Test '{test_name}' failed for Alpine container"

    print(f"✅ Alpine Container Tests: {sum(results.values())}/{len(results)} passed")


@pytest.mark.asyncio
async def test_container_security(test_suite):
    """Test container security features."""
    env_vars = {
        "DATABASE_URL": "sqlite+aiosqlite:///test.db",
        "SECRET_KEY": "test-key",
    }

    await test_suite.setup_container("tool-registry:ubi8", "security-test", env_vars)

    try:
        # Test security features
        security_tests = {
            "non_root_execution": await test_suite.test_user_permissions("security-test"),
            "file_permissions": await test_suite.test_file_permissions("security-test"),
            "resource_limits": await test_suite.test_resource_limits("security-test"),
            "graceful_shutdown": await test_suite.test_signal_handling("security-test"),
        }

        # All security tests should pass
        for test_name, passed in security_tests.items():
            assert passed, f"Security test '{test_name}' failed"

        print(f"✅ Security Tests: {sum(security_tests.values())}/{len(security_tests)} passed")

    finally:
        await test_suite.cleanup_container("security-test")


def test_dockerfile_syntax():
    """Test that all Dockerfiles have valid syntax."""
    dockerfiles = [
        "Dockerfile",
        "Dockerfile.ubi8",
        "Dockerfile.alpine",
        "Dockerfile.hardened"
    ]

    valid_files = 0
    for dockerfile in dockerfiles:
        if os.path.exists(dockerfile):
            try:
                # Check file can be read and has basic structure
                with open(dockerfile, 'r') as f:
                    content = f.read()
                    assert "FROM" in content, f"Dockerfile {dockerfile} missing FROM instruction"
                    assert "CMD" in content or "ENTRYPOINT" in content, \
                           f"Dockerfile {dockerfile} missing CMD/ENTRYPOINT"

                    # Basic syntax checks
                    lines = content.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Check for common Dockerfile syntax issues
                            assert not line.startswith('\t'), \
                                f"Dockerfile {dockerfile} uses tabs instead of spaces"

                valid_files += 1
                print(f"  ✅ {dockerfile}")

            except Exception as e:
                print(f"  ❌ {dockerfile}: {e}")
                raise

    print(f"✅ Dockerfile syntax checks passed for {valid_files} files")


if __name__ == "__main__":
    import sys

    async def main():
        """Run container tests manually."""
        suite = ContainerTestSuite()

        # Test UBI8 container
        try:
            results = await suite.run_full_test_suite("tool-registry:ubi8", {
                "DATABASE_URL": "sqlite+aiosqlite:///test.db",
                "SECRET_KEY": "test-key",
            })

            print("\n🧪 Container Test Results:")
            for test_name, passed in results.items():
                status = "✅" if passed else "❌"
                print(f"  {status} {test_name}")

            total_passed = sum(results.values())
            total_tests = len(results)
            print(f"\n📊 Summary: {total_passed}/{total_tests} tests passed")

            if total_passed == total_tests:
                print("All container tests passed!")
                return 0
            else:
                print("Some tests failed!")
                return 1

        except Exception as e:
            print(f"Test failed with error: {e}")
            return 1

    sys.exit(asyncio.run(main()))