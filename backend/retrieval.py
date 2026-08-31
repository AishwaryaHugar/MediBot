"""
Hybrid retrieval: dense (semantic) + sparse (BM25-approximated) vectors
with RBAC enforced as a Qdrant metadata filter — access control at the data layer.
"""
from collections import Counter
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Prefetch,
    FusionQuery,
    Fusion,
    SparseVector,
)
from sentence_transformers import SentenceTransformer

from config import (
    COLLECTION_NAME,
    DENSE_MODEL,
    EMBEDDING_DIM,
    QDRANT_API_KEY,
    QDRANT_PATH,
    QDRANT_URL,
    SPARSE_DIM,
    TOP_K_RETRIEVAL,
)
from rbac import build_qdrant_filter

_dense_model: SentenceTransformer | None = None
_qdrant_client: QdrantClient | None = None


def get_dense_model() -> SentenceTransformer:
    global _dense_model
    if _dense_model is None:
        _dense_model = SentenceTransformer(DENSE_MODEL)
    return _dense_model


def get_qdrant_client() -> QdrantClient:
    global _qdrant_client
    if _qdrant_client is None:
        # Use local disk storage when QDRANT_PATH is set (no Docker required).
        # Set QDRANT_URL to point at a real Qdrant server for production.
        try:
            remote = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=2)
            remote.get_collections()          # probe — throws if unreachable
            _qdrant_client = remote
        except Exception:
            _qdrant_client = QdrantClient(path=QDRANT_PATH)
    return _qdrant_client


def encode_dense(text: str) -> list[float]:
    return get_dense_model().encode(text, normalize_embeddings=True).tolist()


def encode_sparse(text: str) -> SparseVector:
    """
    BM25-approximated sparse encoding.
    Each unique token is hashed to a stable index in [0, SPARSE_DIM).
    Hash collisions are aggregated (summed) to ensure unique indices,
    which Qdrant requires for valid SparseVector payloads.
    """
    tokens = text.lower().split()
    tf = Counter(tokens)
    total = len(tokens) or 1
    index_vals: dict[int, float] = {}
    for token, count in tf.items():
        idx = abs(hash(token)) % SPARSE_DIM
        index_vals[idx] = index_vals.get(idx, 0.0) + count / total
    return SparseVector(indices=list(index_vals.keys()), values=list(index_vals.values()))


def hybrid_retrieve(query: str, role: str, top_k: int = TOP_K_RETRIEVAL) -> list[dict[str, Any]]:
    """
    Combines dense + sparse search with Reciprocal Rank Fusion (RRF).
    RBAC filter is applied at the Qdrant query level — restricted chunks
    never reach the application or the LLM.
    """
    client = get_qdrant_client()
    rbac_filter = build_qdrant_filter(role)

    dense_vec = encode_dense(query)
    sparse_vec = encode_sparse(query)

    # RBAC filter pushed into each Prefetch so restricted chunks are
    # excluded before RRF fusion — not as a post-hoc pass on results (NFR-01).
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            Prefetch(query=dense_vec,  using="dense",  filter=rbac_filter, limit=top_k),
            Prefetch(query=sparse_vec, using="sparse", filter=rbac_filter, limit=top_k),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )

    candidates = []
    for point in results.points:
        p = point.payload or {}
        candidates.append(
            {
                "text":            p.get("text", ""),
                "source_document": p.get("source_document", ""),
                "section_title":   p.get("section_title", ""),
                "collection":      p.get("collection", ""),
                "chunk_type":      p.get("chunk_type", "text"),
                "score":           point.score,
            }
        )
    return candidates
