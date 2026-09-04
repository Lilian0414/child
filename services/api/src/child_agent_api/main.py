"""FastAPI application and the small public deterministic-demo boundary."""

import os
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field

from child_agent_api.domain.errors import (
    DomainError,
    NotFoundError,
    VersionConflictError,
)
from child_agent_api.domain.models import AccessibilityProfile, ObservationDecision
from child_agent_api.fixture_flow import FlowView, build_view, observation_batch, observation_id
from child_agent_api.persistence.database import create_database_engine
from child_agent_api.providers.tts_elevenlabs import TTSError, synthesize_speech
from child_agent_api.revisions import (
    DrawingRevision,
    RevisionResolution,
    RevisionResult,
    RevisionSubmission,
)
from child_agent_api.service import WorldStateService

DEFAULT_CORS_ORIGINS = "http://localhost:5173"


def cors_origins_from_env() -> list[str]:
    configured_origins = os.getenv("CHILD_API_CORS_ORIGINS", DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    status: Literal["ok"]
    service: Literal["child-agent-api"]
    version: str


class CreateSessionRequest(ApiModel):
    profile: AccessibilityProfile = Field(default_factory=AccessibilityProfile)


class MutationRequest(ApiModel):
    expected_state_version: Annotated[int, Field(ge=0)]
    idempotency_key: Annotated[str, Field(min_length=8, max_length=100)]


class GroundingRequest(MutationRequest):
    action: Literal["confirm", "reject", "correct"]


class ChoiceRequest(MutationRequest):
    choice_id: Literal["choice_ask", "choice_tease", "choice_invite", "choice_give_space"]


class ErrorResponse(ApiModel):
    code: str
    message: str
    current_state_version: int | None = None


class TTSRequest(ApiModel):
    text: Annotated[str, Field(min_length=1, max_length=2000)]


engine = create_database_engine()
application_service = WorldStateService(engine)


def get_service() -> WorldStateService:
    return application_service


Service = Annotated[WorldStateService, Depends(get_service)]

app = FastAPI(title="Child-Grounded Story Agent API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_from_env(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(DomainError)
def domain_error(_request: Request, error: DomainError) -> JSONResponse:
    if isinstance(error, VersionConflictError):
        return JSONResponse(
            status_code=409,
            content=ErrorResponse(
                code="state_conflict",
                message="故事已在別處更新，請重新載入後再試。",
                current_state_version=error.current,
            ).model_dump(),
        )
    if isinstance(error, NotFoundError):
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                code="session_not_found", message="找不到這段故事。"
            ).model_dump(),
        )
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code="invalid_step", message="這個步驟現在不能使用，請重新載入。"
        ).model_dump(),
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="child-agent-api", version=app.version)


@app.post("/v1/tts")
def text_to_speech(body: TTSRequest) -> Response:
    try:
        audio_bytes = synthesize_speech(body.text)
    except TTSError as error:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(code="tts_failed", message=str(error)).model_dump(),
        )
    return Response(content=audio_bytes, media_type="audio/mpeg")


def current_view(session_id: str, service: WorldStateService) -> FlowView:
    world = service.get_world(session_id)
    status = service.observation_status(session_id, observation_id(session_id))
    return build_view(
        session_id,
        world,
        has_observation=status is not None,
        observation_decided=status is not None and status != "proposed",
        choices=service.event_payloads(session_id, "CHILD_CHOICE_ACCEPTED"),
    )


@app.post("/v1/sessions", response_model=FlowView, status_code=201)
def create_session(body: CreateSessionRequest, service: Service) -> FlowView:
    session_id = f"ses_{uuid4().hex}"
    service.create_session(session_id, body.profile)
    return current_view(session_id, service)


@app.get("/v1/sessions/{session_id}", response_model=FlowView)
def restore_session(session_id: str, service: Service) -> FlowView:
    service.get_session(session_id)
    return current_view(session_id, service)


@app.post(
    "/v1/sessions/{session_id}/drawing-revisions",
    response_model=DrawingRevision,
    status_code=201,
)
def submit_drawing_revision(
    session_id: str, body: RevisionSubmission, service: Service
) -> DrawingRevision:
    return service.submit_revision(session_id, body)


@app.get(
    "/v1/sessions/{session_id}/drawing-revisions/{revision_id}",
    response_model=DrawingRevision,
)
def retrieve_drawing_revision(
    session_id: str, revision_id: str, service: Service
) -> DrawingRevision:
    return service.get_revision(session_id, revision_id)


@app.post(
    "/v1/sessions/{session_id}/drawing-revisions/{revision_id}/decisions",
    response_model=RevisionResult,
)
def resolve_drawing_revision(
    session_id: str, revision_id: str, body: RevisionResolution, service: Service
) -> RevisionResult:
    return service.resolve_revision(session_id, revision_id, body)


@app.post("/v1/sessions/{session_id}/fixture", response_model=FlowView)
def load_fixture(session_id: str, body: MutationRequest, service: Service) -> FlowView:
    service.record_observations(
        session_id,
        observation_batch(session_id),
        body.expected_state_version,
        body.idempotency_key,
    )
    return current_view(session_id, service)


@app.post("/v1/sessions/{session_id}/grounding", response_model=FlowView)
def ground_fixture(session_id: str, body: GroundingRequest, service: Service) -> FlowView:
    decision = (
        ObservationDecision(action="correct", supplied_value={"label": "balloon", "count": 4})
        if body.action == "correct"
        else ObservationDecision(action=body.action)
    )
    service.decide_observation(
        session_id,
        observation_id(session_id),
        f"ans_{uuid4().hex}",
        decision,
        body.expected_state_version,
        body.idempotency_key,
    )
    return current_view(session_id, service)


@app.post("/v1/sessions/{session_id}/choices", response_model=FlowView)
def choose(session_id: str, body: ChoiceRequest, service: Service) -> FlowView:
    service.apply_story_choice(
        session_id, body.choice_id, body.expected_state_version, body.idempotency_key
    )
    return current_view(session_id, service)
