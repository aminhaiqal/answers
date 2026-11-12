"""Composition root: only this layer knows which concrete adapters are selected."""

import logging
import secrets
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Path, Request
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from axelyn.api.schemas import AnswerResponse, DocumentInput, IndexResponse, QuestionInput
from axelyn.application.indexing import ConcurrentUpdate, IndexDocument
from axelyn.application.retrieval import Retrieve
from axelyn.config import Settings
from axelyn.infrastructure.database import SqlDocumentRepository
from axelyn.infrastructure.models import (
    DemoEmbedder,
    ExtractiveAnswerer,
    LexicalReranker,
    OllamaEmbedder,
)

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    engine = create_engine(config.database_url, pool_pre_ping=True)
    repository = SqlDocumentRepository(sessionmaker(engine))
    client = httpx.Client(base_url=config.ollama_url, timeout=120, trust_env=False)
    embedder = (
        OllamaEmbedder(client, config.embedding_model)
        if config.embedding_provider == "ollama"
        else DemoEmbedder()
    )
    index = IndexDocument(repository, embedder)
    retrieve = Retrieve(repository, embedder, LexicalReranker())
    answerer = ExtractiveAnswerer(config.minimum_score)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            client.close()
            engine.dispose()

    app = FastAPI(title="Axelyn Answers", version="0.1.0", lifespan=lifespan)

    def tenant(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
        if credentials is None or not secrets.compare_digest(
            credentials.credentials.encode(), config.api_key.encode()
        ):
            raise HTTPException(401, "Invalid bearer token", headers={"WWW-Authenticate": "Bearer"})
        # Tenant comes from server-side configuration, never a caller-supplied header/body.
        return config.tenant_id

    @app.middleware("http")
    async def trace(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = str(uuid4())
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_id=%s method=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            response.status_code,
            (time.perf_counter() - start) * 1000,
        )
        return response

    @app.exception_handler(ConcurrentUpdate)
    async def conflict(request: Request, exc: ConcurrentUpdate) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(httpx.HTTPError)
    async def provider_error(request: Request, exc: httpx.HTTPError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Embedding provider unavailable"})

    @app.get("/health/live")
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready() -> dict[str, str]:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM documents LIMIT 1"))
        return {"status": "ready"}

    @app.put("/v1/documents/{document_id}", response_model=IndexResponse)
    def ingest(
        payload: DocumentInput,
        tenant_id: Annotated[str, Depends(tenant)],
        document_id: Annotated[str, Path(pattern=r"^[a-zA-Z0-9_-]{1,128}$")],
    ) -> IndexResponse:
        return IndexResponse(
            result=index.execute(tenant_id, document_id, payload.title, payload.text, payload.tags)
        )

    @app.post("/v1/questions", response_model=AnswerResponse)
    def ask(payload: QuestionInput, tenant_id: Annotated[str, Depends(tenant)]) -> AnswerResponse:
        hits = retrieve.execute(tenant_id, payload.question, payload.document_ids, payload.tags)
        return AnswerResponse(result=answerer.answer(payload.question, hits))

    return app
