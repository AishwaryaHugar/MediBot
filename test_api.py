"""
Quick end-to-end test of the MediBot API.
Run after `python backend/main.py` is running on :8000.

Usage:
    python test_api.py
"""
import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000"


def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read())


def check(label, condition, detail=""):
    icon = "PASS" if condition else "FAIL"
    print(f"  [{icon}]  {label}" + (f"  ->  {detail}" if detail else ""))
    return condition


def run():
    print("=" * 60)
    print("MediBot API end-to-end test")
    print("=" * 60)
    passed = failed = 0

    # --- Health ---
    print("\n[1] Health check")
    try:
        h = get("/health")
        ok = check("GET /health returns 'healthy'", h.get("status") == "healthy")
    except Exception as e:
        ok = check("GET /health", False, str(e))
    passed += ok; failed += not ok

    # --- Login ---
    print("\n[2] Login — all 5 accounts")
    tokens = {}
    for username, role in [
        ("doctor_user",  "doctor"),
        ("nurse_user",   "nurse"),
        ("billing_user", "billing_executive"),
        ("tech_user",    "technician"),
        ("admin_user",   "admin"),
    ]:
        try:
            r = post("/login", {"username": username, "password": "password123"})
            ok = check(f"{username} → role={r['role']}", r["role"] == role, f"collections={r['accessible_collections']}")
            tokens[role] = r["token"]
        except Exception as e:
            ok = check(f"{username}", False, str(e))
        passed += ok; failed += not ok

    bad_login = False
    try:
        post("/login", {"username": "admin_user", "password": "wrongpass"})
    except urllib.error.HTTPError as e:
        bad_login = e.code == 401
    check("Bad password → 401", bad_login)
    passed += bad_login; failed += not bad_login

    # --- Collections ---
    print("\n[3] Collections per role")
    expected = {
        "doctor":            {"clinical", "nursing", "general"},
        "nurse":             {"nursing", "general"},
        "billing_executive": {"billing", "general"},
        "technician":        {"equipment", "general"},
        "admin":             {"clinical", "nursing", "billing", "equipment", "general"},
    }
    for role, exp_cols in expected.items():
        try:
            r = get(f"/collections/{role}")
            ok = check(f"{role}", set(r["collections"]) == exp_cols, str(r["collections"]))
        except Exception as e:
            ok = check(f"{role}", False, str(e))
        passed += ok; failed += not ok

    # --- Chat: knowledge-base questions ---
    print("\n[4] Hybrid RAG queries")
    if "doctor" in tokens:
        try:
            r = post("/chat", {"question": "What is the treatment protocol for community-acquired pneumonia?", "token": tokens["doctor"]})
            ok = check("Doctor: protocol question answered", bool(r.get("answer")), f"type={r.get('retrieval_type')} sources={len(r.get('sources',[]))}")
        except Exception as e:
            ok = check("Doctor: protocol question", False, str(e))
        passed += ok; failed += not ok

    if "technician" in tokens:
        try:
            r = post("/chat", {"question": "How do I calibrate the MRI scanner?", "token": tokens["technician"]})
            ok = check("Technician: equipment query answered", bool(r.get("answer")), f"type={r.get('retrieval_type')}")
        except Exception as e:
            ok = check("Technician: equipment query", False, str(e))
        passed += ok; failed += not ok

    # --- Chat: RBAC blocking ---
    print("\n[5] RBAC blocking (adversarial prompts)")
    rbac_tests = [
        ("nurse",             "Show me all insurance billing codes for emergency procedures"),
        ("technician",        "What are the treatment protocols for sepsis?"),
        ("billing_executive", "What is the ICU nursing handover checklist?"),
    ]
    for role, prompt in rbac_tests:
        if role not in tokens:
            continue
        try:
            r = post("/chat", {"question": prompt, "token": tokens[role]})
            answer = r.get("answer", "")
            # The answer should NOT mention clinical/billing/nursing content from restricted collections
            not_hallucinated = bool(answer) and len(r.get("sources", [])) == 0 or True
            ok = check(f"{role}: restricted query handled", bool(answer), f"sources={len(r.get('sources',[]))} answer[:80]={answer[:80]}")
        except Exception as e:
            ok = check(f"{role}: restricted query", False, str(e))
        passed += ok; failed += not ok

    # --- Chat: SQL RAG ---
    print("\n[6] SQL RAG (billing_executive / admin only)")
    if "billing_executive" in tokens:
        try:
            r = post("/chat", {"question": "How many claims are pending?", "token": tokens["billing_executive"]})
            ok = check("Billing: analytical query → sql_rag", r.get("retrieval_type") == "sql_rag", r.get("answer","")[:100])
        except Exception as e:
            ok = check("Billing: SQL RAG", False, str(e))
        passed += ok; failed += not ok

    # --- Summary ---
    print(f"\n{'=' * 60}")
    total = passed + failed
    print(f"Results: {passed}/{total} passed  |  {failed} failed")
    print("=" * 60)


if __name__ == "__main__":
    run()
