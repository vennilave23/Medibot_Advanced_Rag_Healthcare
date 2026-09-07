"""Shared configuration for the MediBot pipeline.

Values here are referenced by every component (ingestion first, retrieval /
API components later) so the role→collection matrix and model names stay
defined in exactly one place.
"""

from pathlib import Path

from dotenv import load_dotenv

# Walks up from this file's directory looking for a .env — finds the shared
# CodeBasics/.env (GROQ_API_KEY, GROQ_MODEL) without needing a copy per assignment.
load_dotenv()

# mediassist_data/ sits alongside this project folder, inside the assignment's
# resource bundle: 2_RAG/Medibot_Assignment_Resources/mediassist_data/
_RAG_ASSIGNMENT_DIR = Path(__file__).resolve().parents[1]
print(f"RAG assignment dir: {_RAG_ASSIGNMENT_DIR}")
DATA_DIR = _RAG_ASSIGNMENT_DIR / "Medibot_Assignment_Resources" / "mediassist_data"
print(f"Data dir: {DATA_DIR}")
# Local, embedded (no server) Qdrant store — same `path=` pattern used in
# S3_01 / S3_02 / S4_02. A real folder (not /tmp) so the index survives
# across ingestion runs instead of being wiped on reboot.
QDRANT_PATH = str(Path(__file__).resolve().parent / "qdrant_storage")
COLLECTION_NAME = "medibot_docs"

# Must match the tokenizer HybridChunker aligns chunk sizes to, per the
# S5_01 pattern (tokenizer = AutoTokenizer.from_pretrained(EMBED_MODEL)).
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MAX_TOKENS_PER_CHUNK = 256

# Component 2: Hybrid RAG (dense + BM25 sparse), stored as two named vectors
# on the same point so Qdrant can fuse them server-side in one query.
DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"
SPARSE_EMBED_MODEL = "Qdrant/bm25"

# Initial hybrid retrieval casts a wide net (Component 3's reranker narrows it).
HYBRID_PREFETCH_LIMIT = 10  # candidates fetched per branch (dense, sparse) before fusion
HYBRID_TOP_K = 10           # fused results returned to the caller

# Cloud-hosted LLM inference (Groq). GROQ_API_KEY / GROQ_MODEL come from .env.
GROQ_MODEL_DEFAULT = "openai/gpt-oss-20b"

# Component 3: Reranking. A cross-encoder scores (query, chunk) jointly -- unlike
# the dense/BM25 legs, which score the query and each chunk independently -- so
# it narrows the broad hybrid candidate set (HYBRID_TOP_K) down to what the LLM
# actually sees.
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RERANK_TOP_K = 3

# Component 4: SQL RAG over the pre-populated operations database (claims,
# maintenance_tickets) -- separate from the document vector store entirely.
MEDIASSIST_DB_PATH = DATA_DIR / "db" / "mediassist.db"

# Gated to analytical roles per the assignment's Component 4 requirement.
SQL_RAG_ALLOWED_ROLES = ["billing_executive", "admin"]

# Role -> Collection access matrix, taken from the assignment's
# "User Roles & Access Matrix" / "Data Sources" tables.
COLLECTION_ACCESS_ROLES = {
    "general": ["doctor", "nurse", "billing_executive", "technician", "admin"],
    "clinical": ["doctor", "admin"],
    "nursing": ["nurse", "doctor", "admin"],
    "billing": ["billing_executive", "admin"],
    "equipment": ["technician", "admin"],
}
