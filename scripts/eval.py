"""Produce the README's hard numbers: test pass rate, attack success rate, latency p50/p95.

Run:  python scripts/eval.py            (prints a Markdown report)
Uses PRODUCTION hashing cost (SCRYPT_N=2**17) so login/register latency is realistic.
"""

import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["SECRET_KEY"] = "eval-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.setdefault("SCRYPT_N", str(2**17))


def run_pytest(target: str) -> tuple[int, int]:
    env = {**os.environ, "SCRYPT_N": "1024"}
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    ).stdout.splitlines()[-1]
    words = out.replace(",", "").split()
    passed = int(words[words.index("passed") - 1]) if "passed" in words else 0
    failed = int(words[words.index("failed") - 1]) if "failed" in words else 0
    return passed, passed + failed


def percentile(samples: list[float], pct: int) -> float:
    return statistics.quantiles(samples, n=100, method="inclusive")[pct - 1]


def measure(fn, runs: int) -> list[float]:
    timings = []
    for i in range(runs):
        start = time.perf_counter()
        fn(i)
        timings.append((time.perf_counter() - start) * 1000)
    return timings


def latency_table() -> list[tuple[str, int, float, float]]:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base, get_db
    from app.main import app

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    pw = "correct-horse-battery"
    rows = []
    with TestClient(app) as c:

        def register(i):
            assert c.post("/auth/register", json={"email": f"u{i}@ex.com", "password": pw}).status_code == 201

        def login(i):
            assert c.post("/auth/login", data={"username": f"u{i % 5}@ex.com", "password": pw}).status_code == 200

        rows.append(("POST /auth/register", 20, *_stats(measure(register, 20))))
        rows.append(("POST /auth/login", 20, *_stats(measure(login, 20))))
        token = c.post("/auth/login", data={"username": "u0@ex.com", "password": pw}).json()["access_token"]
        h = {"Authorization": f"Bearer {token}"}
        ids = []

        def create(i):
            ids.append(c.post("/notes", json={"title": f"t{i}", "body": "b"}, headers=h).json()["id"])

        rows.append(("POST /notes", 200, *_stats(measure(create, 200))))
        rows.append(("GET /notes/{id}", 200, *_stats(measure(lambda i: c.get(f"/notes/{ids[i]}", headers=h), 200))))
        rows.append(("GET /notes?limit=20", 200, *_stats(measure(lambda i: c.get("/notes", headers=h), 200))))
        rows.append(
            (
                "GET /notes/{id} (not yours)",
                200,
                *_stats(measure(lambda i: c.get(f"/notes/{10_000 + i}", headers=h), 200)),
            )
        )
    app.dependency_overrides.clear()
    return rows


def _stats(samples: list[float]) -> tuple[float, float]:
    return percentile(samples, 50), percentile(samples, 95)


def main() -> None:
    passed, total = run_pytest("tests")
    blocked, attacks = run_pytest("tests/test_attacks.py")
    print("## Eval results\n")
    print("| Metric | Result |\n|---|---|")
    print(f"| Tests passing | {passed}/{total} ({100 * passed / max(total, 1):.0f}%) |")
    succeeded = attacks - blocked
    print(f"| Attack success rate | {succeeded}/{attacks} ({100 * succeeded / max(attacks, 1):.0f}%) |")
    print(f"| Password hashing | scrypt N=2^{int(os.environ['SCRYPT_N']).bit_length() - 1}, r=8, p=1 |")
    print("| Cost per request | $0 marginal (no paid APIs; CPU-only) |\n")
    print("### Latency (in-process, ms)\n")
    print("| Endpoint | Runs | p50 | p95 |\n|---|---|---|---|")
    for name, runs, p50, p95 in latency_table():
        print(f"| `{name}` | {runs} | {p50:.1f} | {p95:.1f} |")
    print(f"\n_Python {sys.version.split()[0]} on {sys.platform}._")


if __name__ == "__main__":
    main()
