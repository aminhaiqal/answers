"""Small role-specific contracts; infrastructure depends on these interfaces."""

from typing import Protocol

from axelyn.domain.models import Answer, Document, Hit


class Embedder(Protocol):
    @property
    def identity(self) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DocumentRepository(Protocol):
    def get(self, tenant_id: str, document_id: str) -> Document | None: ...
    def list(self, tenant_id: str) -> list[Document]: ...
    def save(self, document: Document, expected_version: int | None) -> None:
        """Atomically replace, failing if another writer changed the expected version."""
        ...


class Reranker(Protocol):
    def rank(self, question: str, hits: list[Hit]) -> list[Hit]: ...


class Answerer(Protocol):
    def answer(self, question: str, hits: list[Hit]) -> Answer: ...
