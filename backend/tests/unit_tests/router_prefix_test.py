import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(("prefix", "serve_frontend"), [("/api", True), ("", False)])
def test_deployment_router_prefix(tmp_path: Path, prefix: str, serve_frontend: bool) -> None:
    (tmp_path / "static").mkdir()
    frontend = tmp_path / "frontend-dist"
    frontend.mkdir()
    (frontend / "index.html").write_text("prefix-smoke-test")
    backend = Path(__file__).resolve().parents[2]
    script = """
import os
from fastapi.testclient import TestClient
from bracket.app import app, routers
from bracket.config import config

prefix = os.environ["API_PREFIX"]
assert config.api_prefix == prefix
assert config.serve_frontend == (os.environ["SERVE_FRONTEND"] == "true")
assert len(routers) == 17
assert all(router.prefix == prefix for router in routers.values())

client = TestClient(app)
response = client.get("/openapi.json")
assert response.status_code == 200
paths = response.json()["paths"]
expected = {
    "Competitions": "/tournaments/{tournament_id}/competitions",
    "Match Events": "/tournaments/{tournament_id}/matches/{match_id}/events",
    "Tournament Sponsors": "/tournaments/{tournament_id}/sponsors",
}
for tag, path in expected.items():
    assert prefix + path in paths, (tag, path)
    tagged_paths = [
        route for route, methods in paths.items()
        if any(tag in operation.get("tags", []) for operation in methods.values())
    ]
    assert tagged_paths, tag
    assert all(route.startswith(prefix + "/tournaments/") for route in tagged_paths)
    if prefix:
        assert path not in paths
assert not any(path.startswith("/api/api") for path in paths)
for tag, router in routers.items():
    for route in router.routes:
        if hasattr(route, "methods"):
            registered = paths[route.path]
            assert all(method.lower() in registered for method in route.methods)
if config.serve_frontend:
    response = client.get("/tournaments/example/dashboard")
    assert response.status_code == 200
    assert response.text == "prefix-smoke-test"
print("App import, 17 router prefixes, OpenAPI HTTP smoke and frontend serving passed")
"""
    env = {
        **os.environ,
        "ENVIRONMENT": "CI",
        "API_PREFIX": prefix,
        "SERVE_FRONTEND": str(serve_frontend).lower(),
        "AUTO_RUN_MIGRATIONS": "false",
        "PG_DSN": "postgresql://prefix_test:unused@127.0.0.1:1/prefix_test",
        "JWT_SECRET": "prefix-test-secret-not-used-for-real-authentication",
        "PYTHONPATH": str(backend),
    }
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
