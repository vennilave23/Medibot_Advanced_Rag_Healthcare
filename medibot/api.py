"""MediBot — Component 5: FastAPI backend.

Style follows S1_ch1_fastapi_intro's taught pattern: plain `FastAPI()`, typed
request/response models, `HTTPException` with real status codes, a friendly
HTML homepage, run via `fastapi dev api.py`. This module composes every
prior component rather than reimplementing anything:

  - Components 1/2 (ingest.py, retrieval.py): hybrid_search() for document RBAC + retrieval
  - Component 3 (rerank.py): rerank() to narrow candidates before the LLM sees them
  - Component 4 (sql_rag.py): is_sql_rag_permitted() + sql_rag_chain() for analytics questions
  - config.py: the role -> collection matrix, shared model/config constants

Run it:
    fastapi dev api.py

Known simplification (documented in README, not hidden): the assignment's
/chat schema is literally {question, role} -- the role travels in the request
body, not resolved server-side from the /login token. That matches the
assignment's documented contract exactly, but it means /chat trusts whatever
role the caller claims. A production version would resolve role from the
Authorization bearer token issued by /login instead.
"""

import logging
import os
import secrets
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastembed import SparseTextEmbedding
from groq import Groq
from pydantic import BaseModel
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from config import (
    COLLECTION_ACCESS_ROLES,
    COLLECTION_NAME,
    EMBED_MODEL,
    GROQ_MODEL_DEFAULT,
    HYBRID_TOP_K,
    QDRANT_PATH,
    RERANK_TOP_K,
    SPARSE_EMBED_MODEL,
)
from retrieval import generate_answer, hybrid_search
from rerank import rerank
from sql_rag import is_sql_rag_permitted, sql_rag_chain

logger = logging.getLogger("medibot.api")

app = FastAPI(title="MediBot API")

# Component 6 (Next.js, localhost:3000) calls this API directly from the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_ROLES = sorted({role for roles in COLLECTION_ACCESS_ROLES.values() for role in roles})

# --- Module-level singletons, loaded once at import time (not per-request) ---
qdrant_client = QdrantClient(path=QDRANT_PATH)
dense_embedder = SentenceTransformer(EMBED_MODEL)
sparse_embedder = SparseTextEmbedding(model_name=SPARSE_EMBED_MODEL)
groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

# --- Demo accounts (assignment's Component 6 table): username -> (password, role) ---
DEMO_ACCOUNTS = {
    "dr.mehta": ("doctor", "doctor"),
    "nurse.priya": ("nurse", "nurse"),
    "billing.ravi": ("billing_executive", "billing_executive"),
    "tech.anand": ("technician", "technician"),
    "admin.sys": ("admin", "admin"),
}

# In-memory session store: token -> role. Resets on restart -- fine for a demo,
# not a substitute for real session storage in production.
SESSIONS: dict[str, str] = {}

INTENT_SYSTEM_PROMPT = """Classify whether the user's question requires a SQL query against an
operations database (claims, maintenance tickets -- counts, sums, statuses, dates, "how many",
"total", "average") or whether it should be answered from policy/clinical/procedure documents.
Reply with exactly one word, lowercase: "sql" or "document"."""


def classify_intent(question: str) -> Literal["sql", "document"]:
    """Is this an analytical/numbers question (SQL RAG) or a document question (Hybrid RAG)?

    GROQ_MODEL_DEFAULT ("openai/gpt-oss-20b") is a reasoning model: it spends tokens on a
    hidden reasoning pass before the final answer. A tight max_tokens (originally 5, found
    during testing to leave zero budget for the actual answer -- every single call came back
    with empty content) starves that reasoning pass and the response is empty. 200 tokens
    covers the reasoning + one-word answer comfortably.
    """
    model = os.environ.get("GROQ_MODEL", GROQ_MODEL_DEFAULT)
    response = groq_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,
        max_tokens=200,
    )
    label = (response.choices[0].message.content or "").strip().lower()
    return "sql" if "sql" in label else "document"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    role: str


class ChatRequest(BaseModel):
    question: str
    role: str


class SourceOut(BaseModel):
    source_document: str
    section_title: str
    collection: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    retrieval_type: Literal["hybrid_rag", "sql_rag"]
    role: str


@app.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    account = DEMO_ACCOUNTS.get(payload.username)
    if account is None or account[0] != payload.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    _, role = account
    token = secrets.token_urlsafe(24)
    SESSIONS[token] = role
    return LoginResponse(token=token, role=role)


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest) -> ChatResponse:
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {payload.role!r}")

    intent = classify_intent(payload.question)

    if intent == "sql":
        if not is_sql_rag_permitted(payload.role):
            return ChatResponse(
                answer=(
                    f"As a {payload.role}, you do not have access to analytics queries. "
                    "I can only answer document questions from your permitted collections."
                ),
                sources=[],
                retrieval_type="sql_rag",
                role=payload.role,
            )
        answer = sql_rag_chain(payload.question)
        return ChatResponse(answer=answer, sources=[], retrieval_type="sql_rag", role=payload.role)

    # Document RAG: hybrid retrieval (RBAC-filtered, broad candidate set) -> rerank (narrow) -> LLM.
    hybrid_results = hybrid_search(
        qdrant_client, COLLECTION_NAME, dense_embedder, sparse_embedder, payload.question, payload.role, limit=HYBRID_TOP_K
    )
    candidates = [point.payload for point in hybrid_results.points]

    if not candidates:
        allowed = sorted(c for c, roles in COLLECTION_ACCESS_ROLES.items() if payload.role in roles)
        return ChatResponse(
            answer=(
                f"As a {payload.role}, I couldn't find anything relevant in the collections you can "
                f"access ({', '.join(allowed)})."
            ),
            sources=[],
            retrieval_type="hybrid_rag",
            role=payload.role,
        )

    reranked = rerank(payload.question, candidates, top_k=RERANK_TOP_K)
    answer = generate_answer(payload.question, reranked)
    sources = [
        SourceOut(source_document=c["source_document"], section_title=c["section_title"], collection=c["collection"])
        for c in reranked
    ]
    return ChatResponse(answer=answer, sources=sources, retrieval_type="hybrid_rag", role=payload.role)


@app.get("/collections/{role}")
def get_collections(role: str) -> dict[str, object]:
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role!r}")
    collections = sorted(c for c, roles in COLLECTION_ACCESS_ROLES.items() if role in roles)
    return {"role": role, "collections": collections}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    html = """<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>MediBot API</title>
        <style>body{font-family:system-ui,Segoe UI,Roboto,-apple-system,Helvetica,Arial;margin:2rem;color:#0f172a}a{color:#2563eb}code{background:#f1f5f9;padding:0.1rem 0.3rem;border-radius:4px}</style>
    </head>
    <body>
        <h1>MediBot API</h1>
        <p>Internal RAG assistant for MediAssist Health Network staff.</p>
        <p>Interactive API docs: <a href="/docs">/docs</a></p>
        <hr>
        <p>Try: <code>curl -X POST http://127.0.0.1:8000/login -H "Content-Type: application/json" -d '{"username":"dr.mehta","password":"doctor"}'</code></p>
    </body>
</html>"""
    return HTMLResponse(content=html, status_code=200)
