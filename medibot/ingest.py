"""MediBot — Component 1: Document Ingestion with Docling & HybridChunker.

Patterns reused from the CodeBasics course notebooks:
  - Docling parsing + ResultPostprocessor            -> S4_02_rag_with_docling_chunks.ipynb
  - HybridChunker (tokenizer-aligned, merge_peers)    -> S5_01_advanced_rag.ipynb
  - Qdrant collection creation / PointStruct payloads -> S3_01 / S3_02

Run this once as a standalone script, not from inside an API request — the
assignment's own tip is that Docling's layout models download on first run
and structured parsing is slow, so ingestion should happen ahead of time.

    python ingest.py
"""

import logging
from pathlib import Path

from docling.document_converter import DocumentConverter
from docling.chunking import HybridChunker
from fastembed import SparseTextEmbedding
from hierarchical.postprocessor import ResultPostprocessor
from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Modifier,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from config import (
    COLLECTION_ACCESS_ROLES,
    COLLECTION_NAME,
    DATA_DIR,
    DENSE_VECTOR_NAME,
    EMBED_MODEL,
    MAX_TOKENS_PER_CHUNK,
    QDRANT_PATH,
    SPARSE_EMBED_MODEL,
    SPARSE_VECTOR_NAME,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("medibot.ingest")

SUPPORTED_SUFFIXES = {".pdf", ".md"}


def discover_documents(data_dir: Path) -> list[tuple[Path, str]]:
    """Walk each role-mapped collection folder; skip db/ (that's SQL RAG data, not vector-store content)."""
    discovered = []
    for collection_dir in sorted(data_dir.iterdir()):
        if not collection_dir.is_dir() or collection_dir.name not in COLLECTION_ACCESS_ROLES:
            continue
        for file_path in sorted(collection_dir.iterdir()):
            if file_path.suffix.lower() in SUPPORTED_SUFFIXES:
                discovered.append((file_path, collection_dir.name))
    return discovered


def parse_document(file_path: Path):
    """Parse a PDF/Markdown file into a structure-aware DoclingDocument (headings/tables/code preserved).

    ResultPostprocessor infers heading hierarchy from PDF provenance (item.prov -> page/bbox), which
    Markdown-sourced items don't carry -- so it's only run for PDFs; Markdown already has explicit
    heading structure (#, ##) that HybridChunker can use directly.
    """
    converter = DocumentConverter()
    result = converter.convert(str(file_path))
    if file_path.suffix.lower() == ".pdf":
        ResultPostprocessor(result).process()
    return result.document


def classify_chunk_type(doc_chunk) -> str:
    """Map a chunk's source item labels to the assignment's chunk_type vocabulary: text/table/heading/code."""
    labels = [str(getattr(item, "label", "")).lower() for item in doc_chunk.meta.doc_items]
    if any("table" in label for label in labels):
        return "table"
    if any("code" in label for label in labels):
        return "code"
    if any("header" in label or "title" in label for label in labels):
        return "heading"
    return "text"


def chunk_document(dl_doc, chunker: HybridChunker) -> list[dict]:
    """Two-pass chunking: HybridChunker first splits along section/subsection/paragraph structure,
    then enforces the tokenizer-aware max_tokens budget — exactly the strategy the assignment requires.
    """
    chunks = []
    for doc_chunk in chunker.chunk(dl_doc=dl_doc):
        headings = doc_chunk.meta.headings or []
        chunks.append(
            {
                # serialize() prepends the heading breadcrumb to the chunk body, so the
                # *embedded* text always carries its parent-section context (S5_01 pattern).
                "chunk_text": chunker.serialize(chunk=doc_chunk),
                "section_title": headings[-1] if headings else "Untitled Section",
                "chunk_type": classify_chunk_type(doc_chunk),
            }
        )
    return chunks


def build_points(
    chunks_with_meta: list[dict],
    embedder: SentenceTransformer,
    sparse_embedder: SparseTextEmbedding,
    start_id: int,
) -> list[PointStruct]:
    """Embed each chunk with both the dense model and BM25, as two named vectors on one point.

    Storing both on the same point (rather than in separate collections/queries) is what lets
    Component 2 fuse dense + sparse server-side in a single Qdrant query.
    """
    texts = [c["chunk_text"] for c in chunks_with_meta]
    dense_vectors = embedder.encode(texts, show_progress_bar=False)
    sparse_vectors = list(sparse_embedder.embed(texts))
    return [
        PointStruct(
            id=start_id + i,
            vector={
                DENSE_VECTOR_NAME: dense_vector.tolist(),
                SPARSE_VECTOR_NAME: SparseVector(
                    indices=sparse_vector.indices.tolist(), values=sparse_vector.values.tolist()
                ),
            },
            payload=chunk,
        )
        for i, (chunk, dense_vector, sparse_vector) in enumerate(zip(chunks_with_meta, dense_vectors, sparse_vectors))
    ]


def ensure_hybrid_collection(client: QdrantClient, embedder: SentenceTransformer) -> None:
    """Create the collection with named dense + sparse vector configs.

    A collection's vector config is immutable after creation, so a collection built by the
    original dense-only Component 1 run can't be upgraded in place — it's dropped and rebuilt
    from source documents instead (ingestion is idempotent, so this is safe to re-run).
    """
    if client.collection_exists(collection_name=COLLECTION_NAME):
        info = client.get_collection(collection_name=COLLECTION_NAME)
        has_hybrid_schema = isinstance(info.config.params.vectors, dict) and DENSE_VECTOR_NAME in (
            info.config.params.vectors or {}
        )
        if has_hybrid_schema:
            return
        logger.warning(
            "Collection '%s' exists with an old (dense-only) schema; recreating for hybrid search.",
            COLLECTION_NAME,
        )
        client.delete_collection(collection_name=COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            DENSE_VECTOR_NAME: VectorParams(
                size=embedder.get_sentence_embedding_dimension(), distance=Distance.COSINE
            ),
        },
        sparse_vectors_config={
            # IDF modifier: FastEmbed's BM25 stores raw term-frequency weights at index time;
            # Qdrant applies the IDF term (from corpus-wide stats) at query time using this flag.
            SPARSE_VECTOR_NAME: SparseVectorParams(modifier=Modifier.IDF),
        },
    )
    logger.info("Created Qdrant collection '%s' with dense+sparse vectors", COLLECTION_NAME)


def main() -> None:
    documents = discover_documents(DATA_DIR)
    logger.info("Discovered %d source documents across %d collections", len(documents), len(COLLECTION_ACCESS_ROLES))

    embedder = SentenceTransformer(EMBED_MODEL)
    sparse_embedder = SparseTextEmbedding(model_name=SPARSE_EMBED_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL)
    chunker = HybridChunker(tokenizer=tokenizer, max_tokens=MAX_TOKENS_PER_CHUNK, merge_peers=True)

    client = QdrantClient(path=QDRANT_PATH)
    ensure_hybrid_collection(client, embedder)

    next_id = 0
    total_chunks = 0
    for file_path, collection in documents:
        logger.info("Parsing %s (collection=%s)", file_path.name, collection)
        dl_doc = parse_document(file_path)
        raw_chunks = chunk_document(dl_doc, chunker)

        access_roles = COLLECTION_ACCESS_ROLES[collection]
        for chunk in raw_chunks:
            chunk["source_document"] = file_path.name
            chunk["collection"] = collection
            chunk["access_roles"] = access_roles

        points = build_points(raw_chunks, embedder, sparse_embedder, start_id=next_id)
        client.upsert(collection_name=COLLECTION_NAME, points=points, wait=True)

        next_id += len(points)
        total_chunks += len(points)
        logger.info("  -> %d chunks indexed", len(points))

    logger.info(
        "Ingestion complete: %d chunks from %d documents indexed into '%s' at %s",
        total_chunks,
        len(documents),
        COLLECTION_NAME,
        QDRANT_PATH,
    )


if __name__ == "__main__":
    main()
