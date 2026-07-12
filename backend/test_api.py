"""Quick manual check that the backend is alive and answering.

Run against your local server:
    uv run python test_api.py

Run against a deployed server (e.g. Railway):
    uv run python test_api.py https://your-app.up.railway.app
"""

import sys

import requests

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

print(f"Testing backend at {BASE_URL}\n")

print("1. Health check: GET /")
res = requests.get(f"{BASE_URL}/", timeout=10)
print(f"   status={res.status_code} body={res.json()}")
assert res.status_code == 200, "Health check failed"

print("\n2. Chat check: POST /chat")
res = requests.post(
    f"{BASE_URL}/chat",
    json={"message": "should I buy BTC?"},
    timeout=30,
)
print(f"   status={res.status_code}")
if res.status_code != 200:
    print(f"   body={res.text}")
    raise SystemExit(
        "Chat request failed. Check GROQ_API_KEY is set correctly on the backend."
    )
print(f"   body={res.json()}")
assert "reply" in res.json(), "Response is missing 'reply'"

print("\nAll checks passed! The backend is working.")
