"""Transparent BM25 + cosine search, reciprocal rank fusion, then reranking."""

import math
import re

from rank_bm25 import BM25Okapi

from axelyn.application.indexing import validate_vectors
from axelyn.domain.models import Hit
from axelyn.domain.ports import DocumentRepository, Embedder, Reranker


def tokens(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold())


def cosine(a: tuple[float, ...], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Embedding dimension mismatch; rebuild the index")
    denominator = math.sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / denominator if denominator else 0.0


def fuse(rankings: list[list[Hit]], k: int = 60) -> list[Hit]:
    scores: dict[str, float] = {}
    chunks = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking, 1):
            key = hit.chunk.id
            chunks[key] = hit.chunk
            scores[key] = scores.get(key, 0.0) + 1 / (k + rank)
    return sorted(
        [Hit(chunks[key], score) for key, score in scores.items()],
        key=lambda h: (-h.score, h.chunk.id),
    )


class Retrieve:
    def __init__(
        self, repository: DocumentRepository, embedder: Embedder, reranker: Reranker
    ) -> None:
        self.repository, self.embedder, self.reranker = repository, embedder, reranker

    def execute(
        self,
        tenant_id: str,
        question: str,
        document_ids: tuple[str, ...] = (),
        tags: tuple[str, ...] = (),
    ) -> list[Hit]:
        documents = [
            d
            for d in self.repository.list(tenant_id)
            if (not document_ids or d.id in document_ids)
            and (not tags or set(tags).issubset(d.tags))
        ]
        if any(d.embedding_identity != self.embedder.identity for d in documents):
            raise ValueError("Embedding configuration changed; re-index documents before searching")
        chunks = [c for d in documents for c in d.chunks]
        vectors = [v for d in documents for v in d.vectors]
        if not chunks:
            return []
        query = self.embedder.embed([question])
        validate_vectors(query, 1)
        keyword_scores = BM25Okapi([tokens(c.text) for c in chunks]).get_scores(tokens(question))
        keyword = sorted(
            [Hit(c, float(s)) for c, s in zip(chunks, keyword_scores, strict=True) if s > 0],
            key=lambda h: -h.score,
        )[:50]
        semantic = sorted(
            [Hit(c, cosine(v, query[0])) for c, v in zip(chunks, vectors, strict=True)],
            key=lambda h: -h.score,
        )
        semantic = [h for h in semantic if h.score > 0][:50]
        ranked = self.reranker.rank(question, fuse([keyword, semantic])[:50])
        selected: list[Hit] = []
        page_counts: dict[tuple[str, int], int] = {}
        for hit in ranked:
            # Plain text has no page; do not invent one or apply a page cap to it.
            if hit.chunk.page is not None:
                key = (hit.chunk.document_id, hit.chunk.page)
                if page_counts.get(key, 0) >= 3:
                    continue
                page_counts[key] = page_counts.get(key, 0) + 1
            selected.append(hit)
            if len(selected) == 10:
                break
        return selected
