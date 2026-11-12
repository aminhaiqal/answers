"""SQL persistence with atomic replacement and optimistic concurrency control."""

from dataclasses import asdict
from typing import Any

from sqlalchemy import JSON, Integer, String, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from axelyn.application.indexing import ConcurrentUpdate
from axelyn.domain.models import Chunk, Document


class Base(DeclarativeBase):
    pass


class DocumentRow(Base):
    __tablename__ = "documents"
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class SqlDocumentRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self.sessions = sessions

    @staticmethod
    def decode(row: DocumentRow) -> Document:
        payload = dict(row.payload)
        payload["chunks"] = tuple(Chunk(**c) for c in payload["chunks"])
        payload["vectors"] = tuple(tuple(v) for v in payload["vectors"])
        payload["tags"] = tuple(payload["tags"])
        return Document(**payload)

    def get(self, tenant_id: str, document_id: str) -> Document | None:
        with self.sessions() as session:
            row = session.get(DocumentRow, (tenant_id, document_id))
            return self.decode(row) if row else None

    def list(self, tenant_id: str) -> list[Document]:
        with self.sessions() as session:
            rows = session.scalars(
                select(DocumentRow)
                .where(DocumentRow.tenant_id == tenant_id)
                .order_by(DocumentRow.id)
            )
            return [self.decode(row) for row in rows]

    def save(self, document: Document, expected_version: int | None) -> None:
        try:
            with self.sessions.begin() as session:
                if expected_version is not None:
                    deleted = session.execute(
                        delete(DocumentRow).where(
                            DocumentRow.tenant_id == document.tenant_id,
                            DocumentRow.id == document.id,
                            DocumentRow.version == expected_version,
                        )
                    )
                    if deleted.rowcount != 1:  # type: ignore[attr-defined]
                        raise ConcurrentUpdate("Document changed; retry ingestion")
                session.add(
                    DocumentRow(
                        tenant_id=document.tenant_id,
                        id=document.id,
                        version=document.version,
                        payload=asdict(document),
                    )
                )
        except IntegrityError as exc:
            raise ConcurrentUpdate("Document changed; retry ingestion") from exc
