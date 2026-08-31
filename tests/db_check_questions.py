"""
DB connection check questions for MediBot.

Sends targeted questions to the /chat endpoint that require live SQLite access.
Each question maps to a specific table, column, and SQL operation so you can
verify the DB is connected and returning real data.

Users: billing_user (billing_executive) and admin_user (admin) — both SQL-permitted.

Requirements: backend running on http://localhost:8000

Usage:
    python tests/db_check_questions.py
"""

import requests

BASE_URL = "http://localhost:8000"
SEP = "─" * 72

# ------------------------------------------------------------------
# Questions grouped by what they verify
# ------------------------------------------------------------------

CHECKS = [
    # ── claims table ───────────────────────────────────────────────
    {
        "label":    "claims · row count",
        "user":     "billing_user",
        "question": "How many claims are in the system in total?",
        "expect":   "85",
    },
    {
        "label":    "claims · status filter (pending)",
        "user":     "billing_user",
        "question": "How many claims are currently pending?",
        "expect":   None,   # number will vary; just check it's a number
    },
    {
        "label":    "claims · status filter (approved)",
        "user":     "billing_user",
        "question": "How many claims have been approved?",
        "expect":   None,
    },
    {
        "label":    "claims · SUM column",
        "user":     "billing_user",
        "question": "What is the total claimed amount across all claims?",
        "expect":   None,
    },
    {
        "label":    "claims · AVG column",
        "user":     "billing_user",
        "question": "What is the average approved amount per claim?",
        "expect":   None,
    },
    {
        "label":    "claims · GROUP BY department",
        "user":     "billing_user",
        "question": "What is the total claimed amount broken down by department?",
        "expect":   "cardiology",   # should appear in breakdown
    },
    {
        "label":    "claims · GROUP BY insurer",
        "user":     "billing_user",
        "question": "How many claims does each insurer have?",
        "expect":   "Star Health",  # known insurer in DB
    },
    {
        "label":    "claims · date range",
        "user":     "billing_user",
        "question": "What is the date range of all submitted claims?",
        "expect":   "2024",
    },
    {
        "label":    "claims · top department",
        "user":     "admin_user",
        "question": "Which department has the highest total claimed amount?",
        "expect":   None,
    },
    {
        "label":    "claims · rejected count",
        "user":     "admin_user",
        "question": "How many claims have been rejected?",
        "expect":   None,
    },
    # ── maintenance_tickets table ───────────────────────────────────
    {
        "label":    "tickets · row count",
        "user":     "admin_user",
        "question": "How many maintenance tickets are there in total?",
        "expect":   "78",
    },
    {
        "label":    "tickets · open tickets",
        "user":     "admin_user",
        "question": "How many maintenance tickets are currently open?",
        "expect":   None,
    },
    {
        "label":    "tickets · GROUP BY campus",
        "user":     "admin_user",
        "question": "How many maintenance tickets does each campus have?",
        "expect":   "Hyderabad",   # known campus
    },
    {
        "label":    "tickets · GROUP BY category",
        "user":     "admin_user",
        "question": "What is the breakdown of maintenance tickets by category?",
        "expect":   "radiology",   # known category
    },
    {
        "label":    "tickets · escalated",
        "user":     "admin_user",
        "question": "How many maintenance tickets have been escalated?",
        "expect":   None,
    },
    {
        "label":    "tickets · resolved count",
        "user":     "admin_user",
        "question": "How many maintenance tickets have been resolved?",
        "expect":   None,
    },
]

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

_tokens: dict[str, str] = {}

CREDS = {
    "billing_user": "password123",
    "admin_user":   "password123",
}


def get_token(username: str) -> str:
    if username not in _tokens:
        r = requests.post(f"{BASE_URL}/login",
                          json={"username": username, "password": CREDS[username]},
                          timeout=10)
        r.raise_for_status()
        _tokens[username] = r.json()["token"]
    return _tokens[username]


def ask(username: str, question: str) -> dict:
    token = get_token(username)
    r = requests.post(f"{BASE_URL}/chat",
                      json={"token": token, "question": question},
                      timeout=60)
    r.raise_for_status()
    return r.json()


def check_answer(answer: str, expect: str | None) -> str:
    if expect is None:
        return "PASS (manual review)"
    if expect.lower() in answer.lower():
        return f"PASS (found '{expect}')"
    return f"FAIL — expected '{expect}' in answer"


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def run():
    print(f"\n{'MediBot — DB Connection Question Check':^72}")
    print(f"{'85 claims · 78 maintenance_tickets · SQLite':^72}")
    print(SEP)

    passed = 0
    failed = 0
    manual = 0

    for chk in CHECKS:
        label    = chk["label"]
        username = chk["user"]
        question = chk["question"]
        expect   = chk["expect"]

        print(f"\n CHECK : {label}")
        print(f" USER  : {username}")
        print(f" Q     : {question}")

        try:
            result = ask(username, question)
        except Exception as e:
            print(f" ERROR : {e}")
            failed += 1
            print(SEP)
            continue

        retrieval = result["retrieval_type"]
        answer    = result["answer"]

        verdict = check_answer(answer, expect)
        if "PASS" in verdict and "manual" not in verdict:
            passed += 1
        elif "FAIL" in verdict:
            failed += 1
        else:
            manual += 1

        # Trim long answers for display
        display = answer if len(answer) <= 200 else answer[:197] + "..."

        print(f" TYPE  : {retrieval}")
        print(f" A     : {display}")
        print(f" ✓/✗   : {verdict}")
        print(SEP)

    total = len(CHECKS)
    print(f"\nResults: {passed} auto-passed · {manual} manual-review · {failed} failed  (of {total})\n")


if __name__ == "__main__":
    try:
        requests.get(f"{BASE_URL}/health", timeout=5).raise_for_status()
    except Exception:
        print(f"\n ERROR: Backend not reachable at {BASE_URL}")
        print(" Start it first:  python backend/main.py\n")
        raise SystemExit(1)

    run()
