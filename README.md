# Axelyn Answers

A maintainable backend foundation for private document Q&A, based on the [project overview](docs/Axelyn%20Answers%20Project%20Overview.pdf).

**Scorecard: not yet measured.** The overview's 80% answer accuracy, 90% citation support, 90% correct refusal and 85% retrieval hit-rate figures are targets, not results. Automated tests verify software behavior, not RAG quality.

This starter implements the first build phase: plain-text ingestion, persistent document versions, incremental embeddings, tenant-scoped hybrid retrieval, and evidence returned with exact source text. It runs without model downloads. The default hashing embedder and lexical reranker are explicitly development baselines. Answers quote retrieved paragraphs; they do not synthesize an answer or prove that a paragraph answers the question.

## Quick start

Requirements: Docker Compose, or Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
cp .env.example .env
# Edit .env and set AXELYN_API_KEY to a random secret of at least 32 characters.
docker compose up --build
```

API documentation: http://localhost:8000/docs. Authenticate there with the configured API key using **Authorize**. PUT the sample body in [examples/policy.json](examples/policy.json) to `/v1/documents/leave-policy`, then POST `{"question":"How many days of annual leave?"}` to `/v1/questions`.

The database is private to Compose, and the API binds to localhost. The example database credentials are for local development. No model server is needed in demo mode.

For native development, set `AXELYN_DATABASE_URL=sqlite:///./axelyn.db` in `.env`:

```sh
make setup
uv run python -m axelyn.infrastructure.init_db
uv run uvicorn axelyn.api.app:create_app --factory --reload
```

`make setup` creates `.venv` and installs all locked dependencies, including development
tools. It downloads Python 3.12 if needed. To activate the environment in your shell,
run `source .venv/bin/activate`. Run `make help` for setup options.

Postgres works with the same repository; Compose uses a pgvector-capable Postgres image. This baseline stores vectors in JSON and computes cosine similarity in Python. It does **not** yet enable a pgvector extension or use an indexed vector query. This is intentionally limited to small collections.

## Code organization

```text
src/axelyn/
  domain/          Immutable entities and small provider/repository protocols
  application/     Incremental indexing, BM25/cosine retrieval and RRF
  infrastructure/  SQLAlchemy persistence, embedding and answer adapters
  api/             Request validation, authentication, routes, composition root
  config.py        Validated environment settings
```

Domain code imports no framework. Application services depend on protocols, not database or model implementations. The API composition root selects adapters and owns their lifecycle. This keeps responsibilities separate and allows providers to change without modifying the indexing/retrieval logic. See [architecture and extension guidance](docs/architecture/decisions.md).

## API

All `/v1` routes require `Authorization: Bearer <AXELYN_API_KEY>`.

| Route | Behavior |
| --- | --- |
| `PUT /v1/documents/{id}` | Create or replace a plain-text document; return version, new embedding count and reused chunk count |
| `POST /v1/questions` | Retrieve and quote sources; accepts optional `document_ids` and `tags` filters |
| `GET /health/live` | Process liveness |
| `GET /health/ready` | Database connectivity and initial schema readiness |

The API key maps to one server-configured tenant. Caller-supplied tenant fields or headers cannot select another tenant. This is a local single-principal bootstrap, **not** user login, JWT authentication, or organization membership management. Repository operations always require a tenant ID, with isolation tests. Add verified identity-to-tenant resolution before serving multiple users.

Plain-text sources have `page: null` and `section: null`; the API does not invent PDF page references. Paragraphs are capped at 8,000 characters; documents at 500,000 characters. Ingestion is synchronous for now. A failed model call or concurrent write leaves the previous version intact; concurrent replacements return HTTP 409 for retry.

## Configuration and model changes

Settings use the `AXELYN_` prefix; see [.env.example](.env.example). Unknown embedding providers fail validation.

To use a locally served Ollama embedding model, set `AXELYN_EMBEDDING_PROVIDER=ollama`, `AXELYN_EMBEDDING_MODEL` to a pinned model identifier and `AXELYN_OLLAMA_URL` to the local server. Native default: `http://localhost:11434`. Inside Compose set the URL to `http://host.docker.internal:11434`. Download and check the chosen model's license separately. Ollama integration requires a running compatible `/api/embed` endpoint and has not been exercised by the offline test suite.

Every stored document records its embedding identity. A configuration change rejects searches against incompatible documents; ingest them again to rebuild. Blue/green background index migration is future work. A model replacement must also run the eventual quality evaluation dataset; CI currently runs correctness checks only.

## Checks

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -q
```

Tests cover incremental edits, metadata updates, tenant isolation, stale writer conflicts, embedding changes, rollback on embedding failure, fusion, refusal behavior, and authenticated API flow. SQLite is used in tests; Postgres/Compose require separate integration validation.

## Next implementation stages

1. Add Alembic migrations and normalized chunk/vector tables with pgvector indexes; preserve atomic version activation and tenant filtering.
2. Add Docling parsing through a parser port, with page/section provenance and extraction fixtures. Compare against Unstructured before choosing.
3. Add a multilingual cross-encoder reranker and a local generative answer adapter with a separate claim-to-citation verifier. Keep document text delimited as untrusted data.
4. Build a real-document evaluation dataset (50 questions initially), including Bahasa Malaysia, unanswerable and injected questions; publish measured quality by content type and configuration.
5. Add JWT identity, membership checks, background ingestion with Redis/RQ, conversation rewriting, date filters, neighboring chunks and structured tracing.
6. Add the answer/source web interface, then tables, OCR, charts and equations following the overview's phases.

No frontend, worker, PDF upload/parser, generated-answer verifier, or production identity service is represented as complete in this boilerplate.
