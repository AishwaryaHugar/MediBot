"""
Cross-encoder reranking: scores each candidate against the query jointly.
Narrows the initial retrieval set (top-10) to a smaller set (top-3)
before the chunks are included in the LLM prompt.
"""
import logging
from typing import Any

from sentence_transformers import CrossEncoder

from config import RERANKER_MODEL, TOP_K_RERANKED

logger = logging.getLogger("reranker")
_reranker: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder(RERANKER_MODEL)
    return _reranker


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    top_k: int = TOP_K_RERANKED,
) -> list[dict[str, Any]]:
    """
    Scores (query, chunk) pairs jointly with a cross-encoder.
    Returns the top_k highest-scoring chunks.
    Reranker scores are logged for development visibility (US-07).
    """
    if not candidates:
        return []

    reranker = get_reranker()
    pairs = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)

    for chunk, score in zip(candidates, scores):
        chunk["reranker_score"] = float(score)
        logger.debug("reranker | score=%.4f | doc=%s | section=%s",
                     score, chunk["source_document"], chunk["section_title"])

    ranked = sorted(candidates, key=lambda c: c["reranker_score"], reverse=True)
    top = ranked[:top_k]

    logger.info("reranked %d → %d | top_score=%.4f",
                len(candidates), len(top), top[0]["reranker_score"] if top else 0)
    return top
