"""Create the demo account and load the sample documents into a running stack. Safe to re-run.

    python scripts/seed_demo.py
"""
import os
from pathlib import Path

import httpx

API = os.getenv("API_URL", "http://localhost:8000")
EMAIL, PASSWORD = "demo@example.com", "demo-password-1"
CORPUS = Path(__file__).resolve().parent.parent / "eval" / "corpus"


def main() -> None:
    c = httpx.Client(base_url=API, timeout=60)
    r = c.post("/auth/register", json={"email": EMAIL, "password": PASSWORD})
    print("account:", "created" if r.status_code == 201 else "already exists" if r.status_code == 409 else r.text)
    token = c.post("/auth/login", data={"username": EMAIL, "password": PASSWORD}).raise_for_status().json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    existing = {d["filename"] for d in c.get("/documents", headers=headers).json()}
    for path in sorted(CORPUS.iterdir()):
        if path.name in existing:
            print(f"skip   {path.name}")
            continue
        c.post("/documents", headers=headers, files={"file": (path.name, path.read_bytes(), "text/plain")}).raise_for_status()
        print(f"upload {path.name}")
    print(f"\nLog in at http://localhost:3000 with {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    main()
