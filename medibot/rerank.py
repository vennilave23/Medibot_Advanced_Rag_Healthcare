"""MediBot — Component 3: Reranking with a cross-encoder.

Hybrid retrieval (Component 2) fuses two *independent* scoring functions --
dense cosine similarity and BM25 term overlap -- neither of which ever looks
at the query and a candidate chunk together. A cross-encoder does: it takes
the (query, chunk_text) pair as joint input and outputs one relevance score,
which is a strictly stronger signal. This is what narrows the broad hybrid
candidate set down to what the LLM actually sees.
"""

import logging

from sentence_transformers import CrossEncoder

from config import RERANK_MODEL, RERANK_TOP_K

logger = logging.getLogger("medibot.rerank")

_cross_encoder: CrossEncoder | None = None


def get_cross_encoder() -> CrossEncoder:
    """Lazily load and cache the cross-encoder (it's only needed once a query comes in)."""
    global _cross_encoder
    if _cross_encoder is None:
        _cross_encoder = CrossEncoder(RERANK_MODEL)
    return _cross_encoder


def rerank(query: str, chunks: list[dict], top_k: int = RERANK_TOP_K) -> list[dict]:
    """Score each candidate chunk against the query jointly, then keep only the top_k.

    Per the assignment: only these top_k chunks may reach the LLM prompt -- the
    full initial hybrid candidate set (e.g. top-10) must not be passed through.
    Every candidate's score is logged (not just the survivors), since seeing
    a low-ranked hybrid result jump to #1 is the point of reranking.
    """
    if not chunks:
        return []

    cross_encoder = get_cross_encoder()
    pairs = [(query, chunk["chunk_text"]) for chunk in chunks]
    scores = cross_encoder.predict(pairs)

    ranked = sorted(zip(chunks, scores), key=lambda pair: pair[1], reverse=True)
    for rank, (chunk, score) in enumerate(ranked, start=1):
        logger.info(
            "rerank #%d score=%.4f  [%s] %s > %s",
            rank,
            score,
            chunk["collection"],
            chunk["source_document"],
            chunk["section_title"],
        )

    return [dict(chunk, rerank_score=float(score)) for chunk, score in ranked[:top_k]]
