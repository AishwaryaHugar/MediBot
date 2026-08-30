from pydantic import BaseModel
from typing import Optional


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: str
    username: str
    accessible_collections: list[str]


class ChatRequest(BaseModel):
    question: str
    token: str


class Source(BaseModel):
    source_document: str
    section_title: str
    collection: str
    score: Optional[float] = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    retrieval_type: str       # "hybrid_rag" | "sql_rag"
    role: str
    question: str


class CollectionsResponse(BaseModel):
    role: str
    collections: list[str]


class HealthResponse(BaseModel):
    status: str
    services: dict
