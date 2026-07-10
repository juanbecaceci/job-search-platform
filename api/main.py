"""FastAPI application factory.

Stage 2 wires the read API only. The async JobRunner (Stage 3) and agent
adapter (Stage 4) attach to the lifespan later; the hook is kept here so those
stages have an obvious place to start.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.agent.claude_adapter import ClaudeAdapter
from api.jobs import EventBus, JobRunner
from api.jobs.handlers import register_handlers
from api.routers import all_routers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the in-process JobRunner + EventBus + agent adapter; tear down on exit."""
    bus = EventBus()
    runner = JobRunner(bus, max_workers=2)
    register_handlers(runner)
    app.state.event_bus = bus
    app.state.job_runner = runner
    # v1 ships only ClaudeAdapter (DECISIONS #5). Tests override app.state.agent_adapter.
    app.state.agent_adapter = ClaudeAdapter()
    try:
        yield
    finally:
        runner.shutdown(wait=False)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Job Search Platform API",
        version="0.3.0",  # Stage 3: write ops + async jobs
        lifespan=lifespan,
    )

    # Self-hosted single-user tool: the SPA is served from localhost during dev.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    for router in all_routers:
        app.include_router(router)

    return app


app = create_app()
