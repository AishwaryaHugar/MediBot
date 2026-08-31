"""
Live question-checking script for MediBot.

Logs in as each demo user, sends one role-appropriate question,
and prints the answer + sources so you can verify the system end-to-end.

Requirements: backend must be running on http://localhost:8000

Usage:
    python tests/check_per_user.py
"""

import textwrap
import requests

BASE_URL = "http://localhost:8000"

# One representative question per user / role
USER_QUESTIONS = [
    {
        "username": "doctor_user",
        "password": "password123",
        "question": "What is the treatment protocol for sepsis?",
    },
    {
        "username": "nurse_user",
        "password": "password123",
        "question": "What are the ICU hand hygiene steps for infection control?",
    },
    {
        "username": "billing_user",
        "password": "password123",
        "question": "How many claims are currently pending?",
    },
    {
        "username": "tech_user",
        "password": "password123",
        "question": "How do I calibrate the MRI machine?",
    },
    {
        "username": "admin_user",
        "password": "password123",
        "question": "What is the total approved claim amount across all departments?",
    },
]

SEP = "─" * 70


def login(username: str, password: str) -> tuple[str, str, list[str]]:
    resp = requests.post(f"{BASE_URL}/login", json={"username": username, "password": password}, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data["token"], data["role"], data["accessible_collections"]


def ask(token: str, question: str) -> dict:
    resp = requests.post(f"{BASE_URL}/chat", json={"token": token, "question": question}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def run():
    print(f"\n{'MediBot — Per-User Question Check':^70}")
    print(SEP)

    for entry in USER_QUESTIONS:
        username = entry["username"]
        question = entry["question"]

        print(f"\n USER : {username}")

        # Login
        try:
            token, role, collections = login(username, entry["password"])
        except Exception as e:
            print(f"  LOGIN FAILED: {e}")
            print(SEP)
            continue

        print(f" ROLE : {role}")
        print(f" ACCESS : {', '.join(collections)}")
        print(f" QUESTION : {question}")

        # Ask
        try:
            result = ask(token, question)
        except Exception as e:
            print(f"  CHAT FAILED: {e}")
            print(SEP)
            continue

        print(f" RETRIEVAL : {result['retrieval_type']}")
        print(f"\n ANSWER:")
        wrapped = textwrap.fill(result["answer"], width=68, initial_indent="  ", subsequent_indent="  ")
        print(wrapped)

        if result["sources"]:
            print(f"\n SOURCES:")
            for src in result["sources"]:
                score = f"  score={src['score']:.3f}" if src.get("score") else ""
                print(f"  • [{src['collection']}] {src['source_document']} — {src['section_title']}{score}")
        else:
            print("\n SOURCES: (SQL result — no document sources)")

        print(SEP)

    print("\nDone.\n")


if __name__ == "__main__":
    try:
        requests.get(f"{BASE_URL}/health", timeout=5).raise_for_status()
    except Exception:
        print(f"\n ERROR: Backend not reachable at {BASE_URL}")
        print(" Start it first:  python backend/main.py\n")
        raise SystemExit(1)

    run()
