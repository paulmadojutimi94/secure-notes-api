# Design doc: Secure Notes API

**Author:** Paul Madojutimi · **Status:** Implemented (v1.0) · **Date:** Nov 2026

## Goal
Build an API where users register, log in, and do CRUD on private notes, with **provable per-user isolation**. Success criteria: 100% test pass, a 0% attack success rate on a written red-team suite, and non-auth endpoints under 10 ms p95 in process.

## Non-goals (v1)
Rate limiting, refresh tokens, email verification, password reset, roles or admin, sharing notes between users.

## Key decisions

### 1. Password hashing: **scrypt** (Python standard library)
| Option | Verdict | Why |
|---|---|---|
| **scrypt (hashlib)** | ✅ Chosen | Memory-hard (resists GPU cracking), on OWASP's approved list, **zero extra dependencies**, parameters stored in the hash so cost can be raised later |
| Argon2id (`argon2-cffi`) | Close second | OWASP's top pick, but adds a compiled dependency. Would switch for a production system |
| bcrypt | ❌ | Silently truncates passwords at 72 bytes; not memory-hard |
| SHA-256 + salt | ❌ | Built to be *fast*. A GPU tries billions per second, which is exactly wrong for passwords |
| Plain text / encryption | ❌ | Encryption can be reversed by anyone who has the key. Hashing can't be reversed at all |

Cost: N=2^17, r=8, p=1, from OWASP's minimum. That is about 0.4 s and 128 MiB per hash. Tests use N=2^10 through an env var to stay fast. `needs_rehash()` upgrades old hashes on the next successful login.

### 2. Sessions: **stateless JWT (HS256), 30-minute expiry**
| Option | Verdict | Why |
|---|---|---|
| **JWT bearer** | ✅ | No session table; any server instance can verify it; works with FastAPI's OAuth2 support and the Swagger "Authorize" button |
| Server-side sessions + cookie | ❌ for v1 | Easy to revoke, but needs a session store and CSRF protection. A better fit for browser-only apps |
| API keys | ❌ | Long-lived, no expiry, meant for machines not people |
| RS256 (asymmetric) | Deferred | Only useful when *other* services verify our tokens. One service → HS256 |

The trade-off we accept is that tokens can't be revoked before they expire (see README known failure #2). Hardening: the algorithm allow-list is pinned (blocks `alg=none`), `exp`, `iat` and `sub` are required, and `type` must be `access`.

### 3. Data isolation: **ownership in the query, 404 for foreign rows**
| Option | Verdict | Why |
|---|---|---|
| **`WHERE id = ? AND owner_id = me`** | ✅ | You can't forget the check because the query can't return someone else's row. One helper (`get_owned_note`) is used by all three single-note routes |
| Fetch by id, then `if note.owner_id != me: 403` | ❌ | Works, but every route has to remember the second step. **403 also confirms the note exists**, which leaks information |
| Random UUID ids only | ❌ as the *only* defence | Makes guessing hard, but obscurity isn't authorisation. Good as an *extra* layer later |
| Postgres row-level security | Deferred | Strongest, but ties us to Postgres and adds operational overhead |

`owner_id` is never accepted from the client: `extra="forbid"` turns `{"owner_id": 1}` into a 422 (mass-assignment defence).

### 4. Database: **SQLAlchemy 2.0 ORM, SQLite by default**
SQLite needs no setup for development or CI. `DATABASE_URL` switches to Postgres without code changes. Raw SQL strings were rejected because parameterised ORM queries make SQL injection structurally impossible (proven by 4 attack tests).

### 5. Validation: **Pydantic v2 at the edge**
Validation happens once, at the boundary, so everything inside the app can trust its inputs. Password rule: **length 12–128 and nothing else**, following NIST SP 800-63B (length beats composition rules like "one symbol"). Passwords are deliberately **not trimmed**. Emails are trimmed and lowercased so `Alice@X.com` and `alice@x.com` are one account.

### 6. Login hardening details
- Unknown email → still runs a scrypt check against a dummy hash, so both failure paths take the same time (measured: 399.5 vs 400.2 ms p50).
- Same error message for "no such user" and "wrong password".
- Sync (`def`) route handlers, so FastAPI runs blocking scrypt in a thread pool instead of freezing the event loop.

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| Login floods use up CPU and RAM | Medium | Proxy rate limiting (next step); `SCRYPT_N` adjustable |
| `SECRET_KEY` leaks → anyone can mint tokens | Low | Env var only, never in git; a random key and a loud warning if unset |
| Developer adds a route without the owner filter | Medium | `get_owned_note` helper; the IDOR test pattern is easy to copy for new routes |
