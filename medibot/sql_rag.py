"""MediBot — Component 4: SQL RAG over mediassist.db.

Structure mirrors S5_01_advanced_rag.ipynb's SQL RAG section: LangChain's
create_sql_query_chain does the schema-aware NL -> SQL translation (it reads
the table DDL via SQLDatabase and prompts for dialect-specific SQL), a
regex-based clean_sql() strips the markdown fences / "SQLQuery:" preambles
Groq-hosted models tend to add, and the raw SQL result is hand back to the
LLM for a final natural-language answer -- the same three-step shape the
assignment asks for.

Not all questions belong here: this only answers questions over the
mediassist.db operations tables (claims, maintenance_tickets). Document
questions still go through Components 2/3 (retrieval.hybrid_search + rerank).
"""

import logging
import os
import re

from langchain_classic.chains import create_sql_query_chain
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from config import GROQ_MODEL_DEFAULT, MEDIASSIST_DB_PATH, SQL_RAG_ALLOWED_ROLES

logger = logging.getLogger("medibot.sql_rag")

SYSTEM_PROMPT = """You are MediBot, an internal analytics assistant for MediAssist Health Network,
a hospital group operating in India. Given a user question and the SQL query result from our
operations database (claims, maintenance_tickets), provide a clear, concise natural language answer.
Be specific with numbers and facts from the result. All monetary amounts (claimed_amount,
approved_amount) are in Indian Rupees (INR) -- format them with the ₹ symbol, not $. If the result is
empty, say so plainly instead of guessing."""

db = SQLDatabase.from_uri(f"sqlite:///{MEDIASSIST_DB_PATH}")

llm = ChatGroq(
    model=os.environ.get("GROQ_MODEL", GROQ_MODEL_DEFAULT),
    temperature=0,
    max_tokens=None,
    reasoning_format="parsed",
    timeout=None,
    max_retries=2,
)

sql_query_chain = create_sql_query_chain(llm, db)

answer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "Question: {question}\nSQL Result: {result}\n\nAnswer:"),
    ]
)
answer_chain = answer_prompt | llm


def is_sql_rag_permitted(role: str) -> bool:
    """SQL RAG is gated to analytical roles -- billing_executive and admin -- per the assignment.

    Called by the /chat routing logic (Component 5) before sql_rag_chain(), not inside it --
    sql_rag_chain() itself takes only a question, matching the assignment's required signature.
    """
    return role in SQL_RAG_ALLOWED_ROLES


def clean_sql(raw: str) -> str:
    """Strip markdown fences and any preamble, leaving only the SQL statement.

    LLMs often wrap SQL in ```sql fences or prefix it with "Question: ...\\nSQLQuery:" --
    executing that raw text against sqlite3 fails, so this must run before db.run().
    """
    raw = re.sub(r"```(?:sql)?", "", raw).strip("`").strip()
    if "SQLQuery:" in raw:
        raw = raw.split("SQLQuery:")[-1].strip()
    return raw


MAX_SQL_GENERATION_ATTEMPTS = 2


def sql_rag_chain(question: str) -> str:
    """Three explicit steps, per the assignment: NL -> SQL -> execute -> NL answer."""
    # Step 1: translate the natural language question into SQL. Retried once -- the
    # Groq-hosted model occasionally returns an empty completion (observed in testing);
    # executing an empty string against sqlite3 would silently produce a wrong answer.
    sql = ""
    for attempt in range(1, MAX_SQL_GENERATION_ATTEMPTS + 1):
        raw_sql = sql_query_chain.invoke({"question": question})
        # Step 2: clean the raw LLM output down to just the SQL statement
        sql = clean_sql(raw_sql)
        if sql:
            break
        logger.warning("Empty SQL on attempt %d/%d for question: %s", attempt, MAX_SQL_GENERATION_ATTEMPTS, question)

    if not sql:
        raise RuntimeError(f"LLM failed to produce a SQL query for question: {question!r}")

    logger.info("Generated SQL: %s", sql)

    # Step 3: execute against the database, then ask the LLM for a NL answer
    result = db.run(sql)
    return answer_chain.invoke({"question": question, "result": result}).content
