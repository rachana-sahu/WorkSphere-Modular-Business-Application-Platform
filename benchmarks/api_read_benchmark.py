"""Repeatable local read-API benchmark using SQLite and synthetic records."""

import argparse
import json
import logging
import math
import statistics
import sys
import time
from collections.abc import Iterator
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def percentile95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[math.ceil(0.95 * len(ordered)) - 1]


def make_engine() -> Engine:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    return engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=positive_int, default=50)
    parser.add_argument("--tasks", type=positive_int, default=100)
    args = parser.parse_args()

    engine = make_engine()
    app_logger = logging.getLogger("worksphere")
    log_streams = []
    for handler in app_logger.handlers:
        if isinstance(handler, logging.StreamHandler):
            log_streams.append((handler, handler.stream))
            handler.setStream(sys.stderr)

    def override_get_db() -> Iterator[Session]:
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            registration = client.post(
                "/api/auth/register",
                json={
                    "email": "benchmark@example.com",
                    "display_name": "Benchmark User",
                    "password": "benchmark-only-secure-password",
                    "workspace_name": "Synthetic Benchmark",
                },
            )
            registration.raise_for_status()
            token = registration.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            workspace_response = client.get(
                "/api/workspaces/current",
                headers=headers,
            )
            workspace_response.raise_for_status()
            workspace_id = UUID(workspace_response.json()["id"])

            project_response = client.post(
                f"/api/workspaces/{workspace_id}/projects",
                json={
                    "name": "Synthetic benchmark project",
                    "description": "Generated solely for local read-route timing.",
                },
                headers=headers,
            )
            project_response.raise_for_status()
            project_id = project_response.json()["id"]
            for index in range(args.tasks):
                response = client.post(
                    f"/api/workspaces/{workspace_id}/projects/"
                    f"{project_id}/tasks",
                    json={"title": f"Synthetic task {index:05d}"},
                    headers=headers,
                )
                response.raise_for_status()

            routes = {
                "project_list": f"/api/workspaces/{workspace_id}/projects?page=1&page_size=20",
                "task_list": (
                    f"/api/workspaces/{workspace_id}/projects/"
                    f"{project_id}/tasks?page=1&page_size=20&task_status=todo"
                ),
            }
            results: dict[str, dict[str, float | int]] = {}
            for route_name, path in routes.items():
                for _ in range(5):
                    response = client.get(path, headers=headers)
                    response.raise_for_status()
                samples_ms = []
                for _ in range(args.iterations):
                    started = time.perf_counter()
                    response = client.get(path, headers=headers)
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    response.raise_for_status()
                    samples_ms.append(elapsed_ms)
                results[route_name] = {
                    "iterations": args.iterations,
                    "median_ms": round(statistics.median(samples_ms), 3),
                    "p95_ms": round(percentile95(samples_ms), 3),
                }

            print(
                json.dumps(
                    {
                        "database": "in-memory SQLite",
                        "synthetic_tasks": args.tasks,
                        "warmup_requests_per_route": 5,
                        "results": results,
                        "note": (
                            "Local repeatability aid only; timings are not a "
                            "production or PostgreSQL performance claim."
                        ),
                    },
                    indent=2,
                )
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
        for handler, stream in log_streams:
            handler.setStream(stream)


if __name__ == "__main__":
    main()
