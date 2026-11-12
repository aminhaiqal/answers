"""Incremental ingestion; no API, database or serving-library dependencies."""

import hashlib
import json
import math
import re

from axelyn.domain.models import Chunk, Document, IndexResult
from axelyn.domain.ports import DocumentRepository, Embedder


class ConcurrentUpdate(Exception):
    """A document changed while it was being indexed; retry with the latest version."""


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def validate_vectors(vectors: list[list[float]], count: int) -> None:
    if len(vectors) != count or any(not v for v in vectors):
        raise ValueError("Embedding provider returned an invalid number of vectors")
    if vectors and len({len(v) for v in vectors}) != 1:
        raise ValueError("Embedding dimensions are inconsistent")
    if any(not math.isfinite(x) for v in vectors for x in v):
        raise ValueError("Embedding values must be finite")


class IndexDocument:
    def __init__(self, repository: DocumentRepository, embedder: Embedder) -> None:
        self.repository = repository
        self.embedder = embedder

    def execute(
        self, tenant_id: str, document_id: str, title: str, text: str, tags: tuple[str, ...] = ()
    ) -> IndexResult:
        # Include metadata so title/tag changes are persisted even when text is unchanged.
        digest = fingerprint(json.dumps([title, text, tags], ensure_ascii=False))
        previous = self.repository.get(tenant_id, document_id)
        same_model = previous is not None and previous.embedding_identity == self.embedder.identity
        if previous and same_model and previous.fingerprint == digest:
            return IndexResult(
                document_id, previous.version, len(previous.chunks), 0, len(previous.chunks), True
            )

        # Paragraph boundaries remain stable after edits elsewhere in the document.
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            raise ValueError("Document contains no text")
        if any(len(p) > 8000 for p in paragraphs):
            raise ValueError("Paragraph exceeds 8000 characters; split it before ingestion")
        cached = (
            {fingerprint(c.text): v for c, v in zip(previous.chunks, previous.vectors, strict=True)}
            if previous and same_model
            else {}
        )
        missing = {fingerprint(p): p for p in paragraphs if fingerprint(p) not in cached}
        new_vectors = self.embedder.embed(list(missing.values())) if missing else []
        validate_vectors(new_vectors, len(missing))
        cache = cached | dict(zip(missing, map(tuple, new_vectors), strict=True))
        chunks = tuple(
            Chunk(f"{document_id}:{i}:{fingerprint(p)[:12]}", document_id, title, p, i)
            for i, p in enumerate(paragraphs)
        )
        vectors = tuple(cache[fingerprint(p)] for p in paragraphs)
        validate_vectors([list(v) for v in vectors], len(chunks))
        version = previous.version + 1 if previous else 1
        document = Document(
            document_id,
            tenant_id,
            title,
            digest,
            self.embedder.identity,
            chunks,
            vectors,
            version,
            tags,
        )
        self.repository.save(document, previous.version if previous else None)
        reused = sum(fingerprint(p) in cached for p in paragraphs)
        return IndexResult(document_id, version, len(chunks), len(missing), reused)
