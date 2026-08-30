"""
Chat orchestration (FR-20 → FR-22):
  - Classify question as analytical or knowledge-based
  - Route to SQL RAG (billing_executive / admin) or Hybrid RAG + Reranking
  - Return {answer, sources, retrieval_type, role, question}
"""
import logging

import anthropic

from config import ANTHROPIC_API_KEY, LLM_MODEL
from models import ChatResponse, Source
from rbac import format_rbac_denial, is_sql_permitted
from reranker import rerank
from retrieval import hybrid_retrieve
from sql_rag import sql_rag_chain

logger = logging.getLogger("chat")
_client: anthropic.Anthropic | None = None

ANALYTICAL_KEYWORDS = (
    "how many", "count", "total", "average", "avg", "sum",
    "maximum", "minimum", "max", "min", "list all", "show all",
    "what is the total", "how much", "percentage", "trend",
    "last month", "this year", "breakdown", "statistics",
    "how often", "which department", "top 5", "top 3",
)


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def is_analytical(question: str) -> bool:
    q = question.lower()
    return any(kw in q for kw in ANALYTICAL_KEYWORDS)


def answer_with_context(question: str, chunks: list[dict]) -> str:
    context = "\n\n".join(
        f"[{c['collection'].upper()} | {c['section_title']}]\n{c['text']}"
        for c in chunks
    )
    prompt = (
        "You are MediBot, the internal knowledge assistant for MediAssist Health Network. "
        "Answer the question using ONLY the provided context. Be concise and accurate. "
        "If the context is insufficient, state that clearly — do not fabricate information.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )
    resp = get_client().messages.create(
        model=LLM_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


def orchestrate(question: str, role: str) -> ChatResponse:
    # Analytical path — SQL RAG (FR-19)
    if is_analytical(question) and is_sql_permitted(role):
        try:
            answer = sql_rag_chain(question)
            return ChatResponse(
                answer=answer,
                sources=[],
                retrieval_type="sql_rag",
                role=role,
                question=question,
            )
        except Exception as exc:
            logger.error("sql_rag failed, falling back to hybrid_rag: %s", exc)

    # Knowledge-base path — Hybrid RAG + Reranking (FR-10 → FR-15)
    candidates = hybrid_retrieve(question, role)

    if not candidates:
        return ChatResponse(
            answer=format_rbac_denial(role),
            sources=[],
            retrieval_type="hybrid_rag",
            role=role,
            question=question,
        )

    top_chunks = rerank(question, candidates)
    answer = answer_with_context(question, top_chunks)

    sources = [
        Source(
            source_document=c["source_document"],
            section_title=c["section_title"],
            collection=c["collection"],
            score=c.get("reranker_score"),
        )
        for c in top_chunks
    ]

    return ChatResponse(
        answer=answer,
        sources=sources,
        retrieval_type="hybrid_rag",
        role=role,
        question=question,
    )
