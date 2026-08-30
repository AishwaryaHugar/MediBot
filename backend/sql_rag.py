"""
SQL RAG chain: natural-language question → SQL → execute → natural-language answer.
Only invoked for roles with analytical responsibilities: billing_executive and admin.

DB schema (mediassist.db):
  claims(claim_id, patient_id, patient_name, department, claim_type, diagnosis_code,
         insurer, claimed_amount, approved_amount, status, submitted_date, resolved_date)
  maintenance_tickets(ticket_id, equipment_name, equipment_id, category, campus,
                      issue_type, fault_code, raised_by, raised_date, resolved_date,
                      status, resolution_note)
"""
import re
import sqlite3
import logging

import anthropic

from config import ANTHROPIC_API_KEY, DATABASE_PATH, LLM_MODEL

logger = logging.getLogger("sql_rag")
_client: anthropic.Anthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def get_schema() -> str:
    conn = sqlite3.connect(DATABASE_PATH)
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table'")
    rows = cur.fetchall()
    conn.close()
    return "\n\n".join(r[0] for r in rows if r[0])


def clean_sql(raw: str) -> str:
    """Strip markdown fences and prose from LLM SQL output, leaving only the query."""
    raw = re.sub(r"```sql\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"```\s*", "", raw)
    m = re.search(r"(SELECT\b.+?)(?:;|$)", raw, re.IGNORECASE | re.DOTALL)
    if m:
        sql = m.group(1).strip()
        return sql if sql.endswith(";") else sql + ";"
    return raw.strip()


def execute_sql(sql: str) -> list[dict]:
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    finally:
        conn.close()


def sql_rag_chain(question: str) -> str:
    """
    FR-16 → FR-19: translate NL question → SQL → execute → NL answer.
    Returns a natural-language answer string.
    """
    client = get_client()
    schema = get_schema()

    sql_prompt = (
        f"You are a SQLite expert. Given this schema:\n\n{schema}\n\n"
        f'Write a single SQL SELECT query to answer: "{question}"\n\n'
        "Return ONLY the SQL query — no explanation, no markdown fences."
    )
    sql_resp = client.messages.create(
        model=LLM_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": sql_prompt}],
    )
    raw_sql = sql_resp.content[0].text
    clean = clean_sql(raw_sql)
    logger.info("sql_rag | generated_sql=%s", clean)

    results = execute_sql(clean)
    logger.info("sql_rag | rows_returned=%d", len(results))

    answer_prompt = (
        f'User question: "{question}"\n\n'
        f"SQL executed:\n{clean}\n\n"
        f"Query results: {results}\n\n"
        "Provide a clear, concise natural-language answer based on these results. "
        "Be specific with numbers and dates."
    )
    answer_resp = client.messages.create(
        model=LLM_MODEL,
        max_tokens=512,
        messages=[{"role": "user", "content": answer_prompt}],
    )
    return answer_resp.content[0].text
