"""FastAPI application entry point."""

import os
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

DEFAULT_CORS_ORIGINS = "http://localhost:5173"


def cors_origins_from_env() -> list[str]:
    """Return the explicitly allowed browser origins."""
    configured_origins = os.getenv("CHILD_API_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]


class HealthResponse(BaseModel):
    """Stable response contract for service health checks."""

    status: Literal["ok"]
    service: Literal["child-agent-api"]
    version: str


app = FastAPI(
    title="Child-Grounded Story Agent API",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_from_env(),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report that the API process is ready to accept requests."""
    return HealthResponse(status="ok", service="child-agent-api", version=app.version)
