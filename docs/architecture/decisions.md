# Architecture decisions

## Small layered application

Use a single Python package rather than microservices. The pipeline is linear and does not need an agent framework. Domain values are frozen dataclasses; protocols expose only the operations each role needs. Composition happens in `api/app.py` so tests can construct application services directly.

Dependency direction: API → application → domain; infrastructure → domain. Infrastructure can use application validation and error definitions, but application services never import infrastructure. FastAPI and SQLAlchemy stay out of the domain and use cases. Follow the SQLAlchemy [transaction context pattern](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html) and FastAPI's [dependency conventions](https://fastapi.tiangolo.com/tutorial/dependencies/).

## Incremental and atomic replacement

A stable caller-chosen document ID is scoped by tenant. Document fingerprints include title, text and tags. Paragraph hashes reuse unchanged vectors within the same document and embedding identity, including duplicate paragraphs. Inserting a paragraph does not force subsequent paragraphs to re-embed. Chunk IDs identify a position in the current document; historical citation resolution is not yet supported.

Compute embeddings before writing. Replace a document's full snapshot in one SQL transaction using an expected-version condition. Readers see either complete version. Conflicts abort rather than overwrite a newer writer. This JSON snapshot design is easy to understand for the baseline; move to separate documents, versions, elements, chunks and embeddings tables before large-scale use. Bootstrap uses explicit `create_all`; adopt reviewed migrations before changing deployed schemas.

## Search and evidence

Filter by tenant, document and tags **before** either search. BM25 uses `rank-bm25`; keyword scoring is not mislabeled Postgres full-text search. Cosine and BM25 each return up to 50 candidates. Reciprocal Rank Fusion uses `1 / (60 + rank)`. Rerank fused candidates and return at most ten, capped at three per known page. The baseline lexical reranker scores token overlap, so its threshold is not a neural confidence probability.

The extractive answer adapter returns at most three exact paragraphs and stable per-response source numbers. This guarantees the displayed quotation exists in its source, not that the source semantically answers the question. A generative provider must return structured claims, validate cited IDs against the retrieved set, and independently check support before releasing claims. Do not use lexical overlap as a production entailment verifier.

## Privacy and identity

The starter makes no external model calls by default. Ollama URLs are operator configuration, not user input. Do not point them at hosted services if documents must remain local. HTTP logs include generated request ID, method, status and duration; they omit bodies, tokens and document contents. Full question/answer tracing needs an explicit retention/access policy and self-hosted trace adapter.

A bearer key authenticates one configured principal. Repository methods require tenant scope, but there is no database row-level security yet. Introduce a verified principal and membership lookup when adding JWTs; never trust a tenant header. Add database isolation as defense in depth. Put request-size limits at the reverse proxy before public deployment; field limits apply after request parsing.

## Extending roles

- New embedding server: implement `Embedder`, include model revision and any preprocessing version in `identity`, and wire it in the composition root. Never compare mismatched spaces.
- New reranker: implement `Reranker`; normalize/document score range before configuring refusal thresholds.
- Generated answers: implement `Answerer` and an independent citation-checking role; retain the no-evidence refusal path.
- PDF ingestion: introduce an `Element` value and `DocumentParser` protocol first; keep structured tables together, propagate real page and section metadata, then chunk.
- Queue: move the existing indexing use case behind a job runner, preserving idempotency and conflict handling. Avoid putting provider logic in workers or routes.

Prefer concrete functions and small classes until another implementation actually needs an interface. Do not add generic base services, repository CRUD frameworks, service locators or nested dependency containers.
