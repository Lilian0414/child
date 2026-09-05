"""FastAPI application and the small public deterministic-demo boundary."""

import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import Annotated, Literal
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from child_agent_api.domain.errors import (
    DomainError,
    NotFoundError,
    VersionConflictError,
)
from child_agent_api.domain.models import (
    AccessibilityProfile,
    CandidateDecision,
    FullStory,
    ObservationBatch,
    ObservationDecision,
    RevisionState,
    Session,
    StoryGrounding,
    StoryState,
)
from child_agent_api.fixture_flow import FlowView, build_view, observation_batch, observation_id
from child_agent_api.observer import (
    ImageInput,
    ObservationPipeline,
    ObserverFailure,
    ObserverItem,
    ObserverPayload,
    ObserverProvider,
)
from child_agent_api.persistence.database import create_database_engine
from child_agent_api.providers.minimax import (
    MiniMaxConfigError,
    MiniMaxStoryProvider,
    minimax_observer,
)
from child_agent_api.providers.tts_elevenlabs import TTSError, synthesize_speech
from child_agent_api.service import WorldStateService
from child_agent_api.story import StoryProvider

REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPO_ROOT / ".env")

DEFAULT_CORS_ORIGINS = ""

# MiniMax (GMI Cloud) is the only live ObserverProvider/StoryProvider backend.
ProviderConfigError = (MiniMaxConfigError,)


def current_observer_provider() -> ObserverProvider:
    return minimax_observer()


def current_story_provider(child_idea: str | None = None) -> StoryProvider:
    return MiniMaxStoryProvider(child_idea=child_idea)


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


class SubmitRevisionRequest(MutationRequest):
    revision_id: Annotated[str, Field(pattern=r"^rev_[A-Za-z0-9_-]+$")]
    observations: "RevisionObservationBatch"


class RevisionObservationBatch(ApiModel):
    schema_version: Literal["observation.v1"]
    batch_id: Annotated[str, Field(pattern=r"^obsb_[A-Za-z0-9_-]+$")]
    media_id: Annotated[str, Field(pattern=r"^med_[A-Za-z0-9_-]+$")]
    items: list[ObserverItem] = Field(min_length=1, max_length=30)

    def to_domain(self) -> ObservationBatch:
        return ObservationBatch.model_validate(
            {
                **self.model_dump(),
                "items": ObserverPayload(items=self.items).to_domain_items(),
            },
            strict=False,
        )


class ResolveRevisionRequest(MutationRequest):
    command_id: Annotated[str, Field(pattern=r"^ans_[A-Za-z0-9_-]+$")]
    decisions: list[CandidateDecision] = Field(min_length=1, max_length=5)


class StoryProposalRequest(ApiModel):
    expected_state_version: Annotated[int, Field(ge=0)]
    child_idea: Annotated[str | None, Field(min_length=1, max_length=300)] = None


class RegenerateStoryRequest(ApiModel):
    expected_state_version: Annotated[int, Field(ge=0)]
    child_idea: Annotated[str | None, Field(min_length=1, max_length=300)] = None


class GroundStoryRequest(MutationRequest):
    action: Literal["accept", "correct", "redirect"]
    supplied_text: Annotated[str | None, Field(min_length=1, max_length=500)] = None


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
    print(f"[domain_error] {type(error).__name__}: {error}")  # noqa: T201 - dev-time diagnostics
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


@app.get("/v1/sessions/{session_id}/state", response_model=Session)
def restore_session_state(session_id: str, service: Service) -> Session:
    """Return canonical persisted session lifecycle state independently of fixture UI."""
    return service.get_session(session_id)


@app.get("/v1/sessions/{session_id}/story", response_model=StoryState)
def restore_story(session_id: str, service: Service) -> StoryState:
    return service.get_story(session_id)


@app.post("/v1/sessions/{session_id}/story/proposals")
def propose_story(session_id: str, body: StoryProposalRequest, service: Service) -> Response:
    try:
        provider = current_story_provider(body.child_idea)
    except ProviderConfigError as error:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(code="story_provider_failed", message=str(error)).model_dump(),
        )
    try:
        state = service.request_story_proposal(
            session_id, body.expected_state_version, provider=provider
        )
    except DomainError:
        raise
    except Exception as error:  # noqa: BLE001 - live model call, keep the API boundary stable
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(code="story_provider_failed", message=str(error)).model_dump(),
        )
    return Response(content=state.model_dump_json(), media_type="application/json")


@app.post("/v1/sessions/{session_id}/story/proposals/{proposal_id}/regenerate")
def regenerate_story(
    session_id: str, proposal_id: str, body: RegenerateStoryRequest, service: Service
) -> Response:
    """Child said the current draft isn't what they meant — write a fresh draft
    for the *same* still-pending proposal from their new idea. Nothing becomes
    canonical here; this never touches world/session state, only the draft."""
    try:
        provider = current_story_provider(body.child_idea)
    except ProviderConfigError as error:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(code="story_provider_failed", message=str(error)).model_dump(),
        )
    try:
        state = service.regenerate_story_proposal(
            session_id, proposal_id, body.expected_state_version, provider
        )
    except DomainError:
        raise
    except Exception as error:  # noqa: BLE001 - live model call, keep the API boundary stable
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(code="story_provider_failed", message=str(error)).model_dump(),
        )
    return Response(content=state.model_dump_json(), media_type="application/json")


@app.post(
    "/v1/sessions/{session_id}/story/proposals/{proposal_id}/ground", response_model=StoryState
)
def ground_story(
    session_id: str, proposal_id: str, body: GroundStoryRequest, service: Service
) -> StoryState:
    grounding = StoryGrounding(action=body.action, supplied_text=body.supplied_text)
    return service.ground_story_proposal(
        session_id, proposal_id, grounding, body.expected_state_version, body.idempotency_key
    )


@app.get("/v1/sessions/{session_id}/story/full", response_model=FullStory)
def full_story(session_id: str, service: Service) -> FullStory:
    return service.full_story(session_id)


@app.post("/v1/sessions/{session_id}/story/complete", response_model=FullStory)
def complete_story(session_id: str, body: MutationRequest, service: Service) -> FullStory:
    return service.complete_story(
        session_id, body.expected_state_version, body.idempotency_key
    )


@app.post(
    "/v1/sessions/{session_id}/drawing-revisions",
    response_model=RevisionState,
    status_code=201,
)
def submit_revision(
    session_id: str, body: SubmitRevisionRequest, service: Service
) -> RevisionState:
    return service.submit_revision(
        session_id,
        body.revision_id,
        body.observations.to_domain(),
        body.expected_state_version,
        body.idempotency_key,
    )


@app.post(
    "/v1/sessions/{session_id}/drawing-revisions/photo",
    status_code=201,
)
async def submit_revision_photo(
    session_id: str,
    service: Service,
    image: UploadFile,
    expected_state_version: Annotated[int, Form()],
    idempotency_key: Annotated[str, Form(min_length=8, max_length=100)],
) -> Response:
    """Live (non-fixture) drawing-revision entry point: a photo goes through a
    real MiniMax vision model, and the resulting observation batch is submitted
    through the same Core `submit_revision` boundary the fixture path uses —
    the photo never becomes canonical truth by itself."""
    image_bytes = await image.read()
    revision_id = f"rev_{uuid4().hex}"
    batch_id = f"obsb_{uuid4().hex}"
    media_id = f"med_{uuid4().hex}"
    image_input = ImageInput(
        media_id=media_id, content=image_bytes, mime_type=image.content_type or "image/jpeg"
    )
    try:
        pipeline = ObservationPipeline(current_observer_provider())
        result = pipeline.run(image_input, batch_id=batch_id, timeout_seconds=45)
    except (*ProviderConfigError, ObserverFailure) as error:
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(code="observer_failed", message=str(error)).model_dump(),
        )
    # The model reuses short ids like "obs_1" on every call, but `observation_id`
    # is a globally unique column — scope each id to this batch before it's stored.
    batch = result.batch.model_copy(
        update={
            "items": [
                item.model_copy(update={"observation_id": f"{batch_id}_{item.observation_id}"})
                for item in result.batch.items
            ]
        }
    )
    state = service.submit_revision(
        session_id, revision_id, batch, expected_state_version, idempotency_key
    )
    return Response(
        content=state.model_dump_json(), media_type="application/json", status_code=201
    )


@app.get(
    "/v1/sessions/{session_id}/drawing-revisions/{revision_id}",
    response_model=RevisionState,
)
def get_revision(session_id: str, revision_id: str, service: Service) -> RevisionState:
    return service.get_revision(session_id, revision_id)


@app.post(
    "/v1/sessions/{session_id}/drawing-revisions/{revision_id}/decisions",
    response_model=RevisionState,
)
def resolve_revision(
    session_id: str,
    revision_id: str,
    body: ResolveRevisionRequest,
    service: Service,
) -> RevisionState:
    return service.resolve_revision(
        session_id,
        revision_id,
        body.decisions,
        body.command_id,
        body.expected_state_version,
        body.idempotency_key,
    )


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


web_dir = REPO_ROOT / "apps" / "web"
if web_dir.is_dir():

    class NoCacheStaticFiles(StaticFiles):
        """Dev/demo app iterates on the frontend constantly — never let the
        browser silently serve a stale cached copy of index.html/app.js/style.css.
        Large static binaries (fonts) that never change mid-demo are the
        exception — no-store would re-download several MB on every reload."""

        _CACHEABLE_SUFFIXES = (".ttf", ".woff", ".woff2", ".otf")

        async def get_response(
            self, path: str, scope: MutableMapping[str, object]
        ) -> Response:
            response = await super().get_response(path, scope)
            if path.endswith(self._CACHEABLE_SUFFIXES):
                response.headers["Cache-Control"] = "public, max-age=604800, immutable"
            else:
                response.headers["Cache-Control"] = "no-store"
            return response

    app.mount("/", NoCacheStaticFiles(directory=web_dir, html=True), name="web")
