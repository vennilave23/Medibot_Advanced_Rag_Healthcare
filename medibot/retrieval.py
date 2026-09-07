"""MediBot — Component 2: Hybrid RAG (dense + BM25 sparse) with RBAC filtering.

The RBAC filter is built once and passed to *every* branch of the query
(both prefetch stages and the outer fused query) so a restricted collection
can never surface a candidate, regardless of which retrieval leg found it —
per the assignment's "RBAC enforced at the retrieval layer, not the LLM"
requirement.
"""

import logging
import os

from fastembed import SparseTextEmbedding
from groq import Groq
from qdrant_client import QdrantClient
from qdrant_client.http.models import QueryResponse
from qdrant_client.models import (
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    Prefetch,
    SparseVector,
)
from sentence_transformers import SentenceTransformer

from config import (
    DENSE_VECTOR_NAME,
    GROQ_MODEL_DEFAULT,
    HYBRID_PREFETCH_LIMIT,
    HYBRID_TOP_K,
    SPARSE_VECTOR_NAME,
)

logger = logging.getLogger("medibot.retrieval")


def build_rbac_filter(role: str) -> Filter:
    """Restrict results to chunks whose access_roles list contains this role.

    access_roles is stored as a list per chunk (e.g. ["doctor", "admin"]); MatchAny
    matches if the payload's list contains any of the given values, i.e. this role.
    """
    return Filter(must=[FieldCondition(key="access_roles", match=MatchAny(any=[role]))])


def hybrid_search(
    client: QdrantClient,
    collection_name: str,
    dense_embedder: SentenceTransformer,
    sparse_embedder: SparseTextEmbedding,
    query: str,
    role: str,
    limit: int = HYBRID_TOP_K,
    prefetch_limit: int = HYBRID_PREFETCH_LIMIT,
) -> QueryResponse:
    """Dense + BM25 sparse search fused server-side by Qdrant in a single query_points call.

    Both branches run as `Prefetch` stages of one request (not two separate `.search()`
    calls merged in Python), and their ranked lists are fused with Reciprocal Rank Fusion
    (RRF) before the caller ever sees a result — satisfying the assignment's "queried
    together" and "fused before being passed downstream" requirements in one step.
    """
    rbac_filter = build_rbac_filter(role)

    dense_vector = dense_embedder.encode(query).tolist()
    sparse_embedding = next(sparse_embedder.query_embed(query))
    sparse_vector = SparseVector(
        indices=sparse_embedding.indices.tolist(), values=sparse_embedding.values.tolist()
    )

    return client.query_points(
        collection_name=collection_name,
        prefetch=[
            Prefetch(
                query=dense_vector,
                using=DENSE_VECTOR_NAME,
                filter=rbac_filter,
                limit=prefetch_limit,
            ),
            Prefetch(
                query=sparse_vector,
                using=SPARSE_VECTOR_NAME,
                filter=rbac_filter,
                limit=prefetch_limit,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        query_filter=rbac_filter,
        limit=limit,
        with_payload=True,
    )


def generate_answer(query: str, chunks: list[dict], groq_client: Groq | None = None) -> str:
    """Send the retrieved chunks + question to a cloud-hosted LLM (Groq) for the final answer."""
    groq_client = groq_client or Groq(api_key=os.environ["GROQ_API_KEY"])
    model = os.environ.get("GROQ_MODEL", GROQ_MODEL_DEFAULT)

    context = "\n\n---\n\n".join(
        f"[Source: {c['source_document']} > {c['section_title']}]\n{c['chunk_text']}" for c in chunks
    )
    system_prompt = (
        "You are MediBot, an internal assistant for MediAssist Health Network staff. "
        "Answer the question using ONLY the provided context chunks. If the context does not "
        "contain the answer, say so plainly instead of guessing. Cite the source document and "
        "section title inline when you use a fact from it."
    )
    response = groq_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content
