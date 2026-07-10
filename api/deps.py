"""Shared FastAPI dependencies for accessing app-scoped singletons."""

from __future__ import annotations

from fastapi import Request

from api.agent import AgentAdapter
from api.jobs import EventBus, JobRunner


def get_runner(request: Request) -> JobRunner:
    return request.app.state.job_runner


def get_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_adapter(request: Request) -> AgentAdapter:
    return request.app.state.agent_adapter
