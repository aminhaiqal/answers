from dataclasses import replace

import pytest

from axelyn.application.indexing import ConcurrentUpdate, IndexDocument
from axelyn.application.retrieval import Retrieve, fuse
from axelyn.domain.models import Chunk, Hit
from axelyn.infrastructure.models import DemoEmbedder, ExtractiveAnswerer, LexicalReranker


def test_incremental_updates_and_metadata(repository):
    index = IndexDocument(repository, DemoEmbedder())
    first = index.execute(
        "a", "policy", "Leave", "Annual leave is 20 days.\n\nSick leave is 14 days."
    )
    assert first.embedded == 2
    same = index.execute(
        "a", "policy", "Leave", "Annual leave is 20 days.\n\nSick leave is 14 days."
    )
    assert same.skipped and same.embedded == 0
    update = index.execute(
        "a", "policy", "Leave", "Annual leave is 21 days.\n\nSick leave is 14 days."
    )
    assert (update.embedded, update.reused, update.version) == (1, 1, 2)
    metadata = index.execute(
        "a", "policy", "New title", "Annual leave is 21 days.\n\nSick leave is 14 days."
    )
    assert metadata.embedded == 0
    assert repository.get("a", "policy").chunks[0].title == "New title"


def test_tenant_isolation_and_replaced_text(repository):
    embedder = DemoEmbedder()
    index = IndexDocument(repository, embedder)
    index.execute("a", "policy", "A", "Confidential alpha policy.")
    index.execute("b", "policy", "B", "Secret beta policy.")
    index.execute("a", "policy", "A", "Replacement gamma policy.")
    retrieve = Retrieve(repository, embedder, LexicalReranker())
    hits = retrieve.execute("a", "policy")
    assert hits and all(h.chunk.title == "A" for h in hits)
    assert all("alpha" not in h.chunk.text and "beta" not in h.chunk.text for h in hits)
    assert retrieve.execute("unknown", "policy") == []
    assert retrieve.execute("a", "policy", document_ids=("other",)) == []


def test_stale_writer_does_not_destroy_current_version(repository):
    IndexDocument(repository, DemoEmbedder()).execute("a", "doc", "Title", "Original")
    original = repository.get("a", "doc")
    repository.save(replace(original, version=2, title="Winner"), expected_version=1)
    with pytest.raises(ConcurrentUpdate):
        repository.save(replace(original, version=2, title="Loser"), expected_version=1)
    assert repository.get("a", "doc").title == "Winner"
    with pytest.raises(ConcurrentUpdate):
        repository.save(original, expected_version=None)


def test_model_change_requires_reindex(repository):
    embedder = DemoEmbedder()
    IndexDocument(repository, embedder).execute("a", "doc", "T", "Some policy")
    embedder.identity = "new-model"
    with pytest.raises(ValueError, match="re-index"):
        Retrieve(repository, embedder, LexicalReranker()).execute("a", "policy")
    assert IndexDocument(repository, embedder).execute("a", "doc", "T", "Some policy").embedded == 1


def test_fusion_rewards_agreement_and_refusal():
    a = Hit(Chunk("a", "doc", "T", "Evidence", 0), 100)
    b = Hit(Chunk("b", "doc", "T", "Other", 1), 0.1)
    ranked = fuse([[a, b], [b]])
    assert ranked[0].chunk.id == "b"
    answerer = ExtractiveAnswerer()
    assert answerer.answer("anything", []).refused
    answer = answerer.answer("evidence", [Hit(a.chunk, 1)])
    assert answer.sources == (a.chunk,) and answer.text == "[1] Evidence"


def test_embedding_failure_preserves_previous_document(repository):
    IndexDocument(repository, DemoEmbedder()).execute("a", "doc", "T", "Original")

    class BrokenEmbedder(DemoEmbedder):
        def embed(self, texts):
            return []

    with pytest.raises(ValueError):
        IndexDocument(repository, BrokenEmbedder()).execute("a", "doc", "T", "Changed")
    assert repository.get("a", "doc").chunks[0].text == "Original"
