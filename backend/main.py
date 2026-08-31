"""
MediBot FastAPI backend.

Endpoints:
  GET  /health                  — service liveness check
  POST /login                   — authenticate and receive role-tagged JWT
  GET  /collections/{role}      — list accessible collections for a role
  POST /chat                    — submit a question; returns answer + sources
"""
import logging

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from auth import authenticate, create_token, decode_token, get_accessible_collections
from chat import orchestrate
from config import ROLE_COLLECTIONS
from models import (
    ChatRequest,
    ChatResponse,
    CollectionsResponse,
    HealthResponse,
    LoginRequest,
    LoginResponse,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("medibot")

app = FastAPI(title="MediBot API", version="1.0.0", description="Role-Based RAG Assistant for MediAssist Health Network")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health() -> HealthResponse:
    return HealthResponse(status="healthy", services={"api": "up", "qdrant": "up", "llm": "up"})


@app.post("/login", response_model=LoginResponse, tags=["Auth"])
async def login(req: LoginRequest) -> LoginResponse:
    user = authenticate(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(req.username, user["role"])
    return LoginResponse(
        token=token,
        role=user["role"],
        username=req.username,
        accessible_collections=get_accessible_collections(user["role"]),
    )


@app.get("/collections/{role}", response_model=CollectionsResponse, tags=["Auth"])
async def get_collections(role: str) -> CollectionsResponse:
    if role not in ROLE_COLLECTIONS:
        raise HTTPException(status_code=404, detail=f"Unknown role: {role}")
    return CollectionsResponse(role=role, collections=ROLE_COLLECTIONS[role])


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        payload = decode_token(req.token)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    role = payload["role"]
    logger.info("chat | role=%s | question=%.80s", role, req.question)

    try:
        return orchestrate(req.question, role)
    except Exception as exc:
        logger.exception("chat error")
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
