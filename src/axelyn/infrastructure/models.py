"""Runnable local baseline and a real Ollama embedding adapter."""

import hashlib

import httpx

from axelyn.application.retrieval import tokens
from axelyn.domain.models import Answer, Hit


class DemoEmbedder:
    """Feature hashing for smoke tests; not a semantic or multilingual model."""

    identity = "demo-hash-v1:128"

    def embed(self, texts: list[str]) -> list[list[float]]:
        result = []
        for text in texts:
            vector = [0.0] * 128
            for token in tokens(text):
                index = int(hashlib.sha256(token.encode()).hexdigest(), 16) % 128
                vector[index] += 1.0
            result.append(vector)
        return result


class OllamaEmbedder:
    def __init__(self, client: httpx.Client, model: str) -> None:
        self.client, self.model = client, model

    @property
    def identity(self) -> str:
        # Use a pinned model digest/version in config, not a mutable tag.
        return f"ollama:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.client.post("/api/embed", json={"model": self.model, "input": texts})
        response.raise_for_status()
        return [[float(value) for value in vector] for vector in response.json()["embeddings"]]


class LexicalReranker:
    """Conservative baseline. Replace with a multilingual cross-encoder for real evaluation."""

    def rank(self, question: str, hits: list[Hit]) -> list[Hit]:
        query = set(tokens(question))
        scored = [
            Hit(h.chunk, len(query & set(tokens(h.chunk.text))) / max(len(query), 1)) for h in hits
        ]
        return sorted(scored, key=lambda h: (-h.score, h.chunk.id))


class ExtractiveAnswerer:
    """Quotes evidence verbatim; makes no model-generated factual claims."""

    def __init__(self, minimum_score: float = 0.25) -> None:
        self.minimum_score = minimum_score

    def answer(self, question: str, hits: list[Hit]) -> Answer:
        supported = [h.chunk for h in hits if h.score >= self.minimum_score][:3]
        if not supported:
            return Answer("I couldn't find this in the documents.", (), True)
        text = "\n\n".join(f"[{i}] {chunk.text}" for i, chunk in enumerate(supported, 1))
        return Answer(text, tuple(supported), False)
