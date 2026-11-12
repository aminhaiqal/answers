"""Framework-independent values shared by indexing and answering."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    title: str
    text: str
    position: int
    page: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class Document:
    id: str
    tenant_id: str
    title: str
    fingerprint: str
    embedding_identity: str
    chunks: tuple[Chunk, ...]
    vectors: tuple[tuple[float, ...], ...]
    version: int = 1
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class IndexResult:
    document_id: str
    version: int
    chunks: int
    embedded: int
    reused: int
    skipped: bool = False


@dataclass(frozen=True)
class Answer:
    text: str
    sources: tuple[Chunk, ...]
    refused: bool
