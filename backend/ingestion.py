"""
Ingestion pipeline (FR-06 → FR-09):
  - Parse PDFs / Markdown with Docling (structure-aware)
  - Chunk hierarchically: section → subsection → paragraph/table
  - Each chunk embeds its parent section heading for context
  - Store dense + sparse (BM25) vectors in Qdrant with full metadata
  - RBAC metadata (access_roles) written at index time

Run once before demo:
    cd backend && python ingestion.py
"""
import logging
import uuid
from collections import Counter
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    OptimizersConfigDiff,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)
from sentence_transformers import SentenceTransformer

from config import (
    COLLECTION_ACCESS_ROLES,
    COLLECTION_NAME,
    DENSE_MODEL,
    DOCUMENTS,
    EMBEDDING_DIM,
    QDRANT_API_KEY,
    QDRANT_PATH,
    QDRANT_URL,
    SPARSE_DIM,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ingestion")


def init_collection(client: QdrantClient) -> None:
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME in existing:
        logger.info("Collection '%s' already exists — skipping creation.", COLLECTION_NAME)
        return
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={"dense": VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)},
        sparse_vectors_config={"sparse": SparseVectorParams()},
        optimizers_config=OptimizersConfigDiff(indexing_threshold=0),
    )
    logger.info("Created Qdrant collection '%s'.", COLLECTION_NAME)


def encode_dense(text: str, model: SentenceTransformer) -> list[float]:
    return model.encode(text, normalize_embeddings=True).tolist()


def encode_sparse(text: str) -> SparseVector:
    tokens = text.lower().split()
    tf = Counter(tokens)
    total = len(tokens) or 1
    # Aggregate across hash collisions — Qdrant requires unique indices.
    index_vals: dict[int, float] = {}
    for token, count in tf.items():
        idx = abs(hash(token)) % SPARSE_DIM
        index_vals[idx] = index_vals.get(idx, 0.0) + count / total
    return SparseVector(indices=list(index_vals.keys()), values=list(index_vals.values()))


def ingest_document(doc_meta: dict, model: SentenceTransformer, client: QdrantClient) -> None:
    path = Path(doc_meta["path"])
    collection = doc_meta["collection"]

    if not path.exists():
        logger.warning("File not found: %s — skipping.", path)
        return

    logger.info("Parsing: %s (collection=%s)", path.name, collection)
    converter = DocumentConverter()
    result = converter.convert(str(path))

    chunker = HybridChunker()
    chunks = list(chunker.chunk(result.document))
    logger.info("  %d chunks extracted.", len(chunks))

    points: list[PointStruct] = []
    for chunk in chunks:
        raw_text = chunk.text.strip()
        if not raw_text:
            continue

        # Prepend the nearest parent heading so the embedding carries section context (FR-08)
        section_title = ""
        meta = getattr(chunk, "meta", None)
        if meta:
            headings = getattr(meta, "headings", []) or []
            if headings:
                section_title = headings[-1]

        embedded_text = f"{section_title}\n\n{raw_text}" if section_title else raw_text

        # Detect chunk type (FR-09)
        chunk_type = "text"
        if meta:
            if getattr(meta, "is_table", False):
                chunk_type = "table"
            elif getattr(meta, "is_code", False):
                chunk_type = "code"

        points.append(
            PointStruct(
                id=str(uuid.uuid4()),
                vector={
                    "dense":  encode_dense(embedded_text, model),
                    "sparse": encode_sparse(embedded_text),
                },
                payload={
                    "text":            embedded_text,
                    "source_document": path.name,
                    "collection":      collection,
                    "access_roles":    COLLECTION_ACCESS_ROLES.get(collection, []),
                    "section_title":   section_title or "Main Content",
                    "chunk_type":      chunk_type,
                },
            )
        )

    if points:
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        logger.info("  Upserted %d points from %s.", len(points), path.name)


def make_client() -> QdrantClient:
    """Connect to a live Qdrant server if reachable, otherwise use local disk storage."""
    try:
        remote = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY, timeout=2)
        remote.get_collections()
        logger.info("Connected to Qdrant at %s", QDRANT_URL)
        return remote
    except Exception:
        logger.info("Qdrant not reachable — using local disk storage at %s", QDRANT_PATH)
        return QdrantClient(path=QDRANT_PATH)


def run_ingestion() -> None:
    logger.info("Loading embedding model: %s", DENSE_MODEL)
    model = SentenceTransformer(DENSE_MODEL)

    client = make_client()
    init_collection(client)

    for doc_meta in DOCUMENTS:
        ingest_document(doc_meta, model, client)

    logger.info("Ingestion complete.")


if __name__ == "__main__":
    run_ingestion()
