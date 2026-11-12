from pydantic import BaseModel, Field

from axelyn.domain.models import Answer, IndexResult


class DocumentInput(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=500_000)
    tags: tuple[str, ...] = Field(default=(), max_length=30)


class QuestionInput(BaseModel):
    question: str = Field(min_length=1, max_length=2000, pattern=r"\S")
    document_ids: tuple[str, ...] = Field(default=(), max_length=100)
    tags: tuple[str, ...] = Field(default=(), max_length=30)


class IndexResponse(BaseModel):
    result: IndexResult


class AnswerResponse(BaseModel):
    result: Answer
    mode: str = "extractive-baseline"
