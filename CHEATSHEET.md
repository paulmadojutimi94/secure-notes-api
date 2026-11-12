# CHEATSHEET: every line, explained

Use this to go deep with an interviewer. Each file is shown in order: **code → what it does → why (the interview answer)**. Blank lines and closing brackets are skipped.

**Request journey (memorise this):** `main.py` receives the request → FastAPI parses the body with a `schemas.py` model (422 if bad) → the `deps.py` dependencies open a DB session and turn the token into a `User` (401 if bad) → a `routers/*.py` handler runs a query that is **always scoped to that user** → the response is filtered through an `…Out` schema → JSON.

---

## `app/config.py`: settings from the environment

| Code | What | Why (interview answer) |
|---|---|---|
| `"""Application settings…"""` | Module docstring | Says what the file is for |
| `import logging, os, secrets` | Std-lib modules | `os.getenv` reads env vars; `secrets` is the **cryptographically secure** random generator (never use `random` for keys) |
| `from dataclasses import dataclass` | Lightweight class helper | Fields without boilerplate |
| `logger = logging.getLogger(__name__)` | Per-module logger | Log lines show which module they came from |
| `@dataclass(frozen=True)` | Immutable settings object | Nothing can change config at runtime by accident |
| `database_url: str` … `jwt_algorithm: str = "HS256"` | The five settings | One typed place for all config ("12-factor app": config lives in the environment, not in code) |
| `def _read_scrypt_n()` | Reads `SCRYPT_N`, default `2**17` | 2^17 is OWASP's minimum for scrypt |
| `if n < 2 or n & (n - 1): raise` | Power-of-two check | scrypt requires N to be a power of two. `n & (n-1) == 0` only for powers of two (bit trick: a power of two has exactly one 1-bit). **Fail fast** at startup, not on the first login |
| `secret = os.getenv("SECRET_KEY")` | The JWT signing key | Never hard-coded, never committed to git |
| `if not secret: secret = secrets.token_urlsafe(32)` + warning | Fallback random key | Dev still works, but tokens die on restart, and the loud warning tells you why |
| `return Settings(...)` with `os.getenv(..., default)` | Builds the settings | Defaults: SQLite file, 30-minute tokens |
| `settings = load_settings()` | Module-level singleton | Read once at import; every module imports this same object |

## `app/database.py`: connection and sessions

| Code | What | Why |
|---|---|---|
| `from collections.abc import Iterator` | Type hint for a generator | `get_db` *yields* |
| `from sqlalchemy import create_engine` | Engine = connection pool | One per app, created once |
| `from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker` | ORM building blocks | SQLAlchemy 2.0 style |
| `_connect_args = {"check_same_thread": False} if …sqlite…` | SQLite-only flag | SQLite refuses by default to share a connection across threads, and FastAPI runs sync routes in a **thread pool**. Postgres doesn't need this |
| `engine = create_engine(settings.database_url, …)` | Creates the pool | Swap databases by changing one env var |
| `SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)` | Session factory | `expire_on_commit=False`: objects stay readable after commit (no surprise extra queries when serialising). `autoflush=False`: we decide when SQL is sent |
| `class Base(DeclarativeBase): pass` | Parent for all tables | `Base.metadata` collects every table, used by `create_all` |
| `def get_db():` / `db = SessionLocal()` / `try: yield db` / `finally: db.close()` | **Dependency with cleanup** | One session per request. `finally` guarantees the connection goes back to the pool **even if the route raises**. Tests replace this function to use an in-memory DB (dependency override) |

## `app/models.py`: the tables

| Code | What | Why |
|---|---|---|
| `from datetime import UTC, datetime` | Time-zone-aware time | Always store UTC; convert for display at the edges |
| `from sqlalchemy import DateTime, ForeignKey, String, Text` | Column types | |
| `from sqlalchemy.orm import Mapped, mapped_column, relationship` | 2.0 typed mapping | `Mapped[int]` lets type checkers understand columns |
| `def utcnow(): return datetime.now(UTC)` | Default timestamp function | Passed as a *function* (not called), so it runs per row, not once at import |
| `class User(Base): __tablename__ = "users"` | Users table | |
| `id: Mapped[int] = mapped_column(primary_key=True)` | Auto-incrementing id | Primary key = unique row identifier |
| `email: … String(254), unique=True, index=True` | Email column | 254 = maximum email length in the RFCs. `unique` = the **database** enforces one account per email (the final safety net against race conditions). `index` = fast lookup at login |
| `password_hash: … String(255)` | Stores the hash, **never the password** | |
| `created_at: … DateTime(timezone=True), default=utcnow` | Audit timestamp | |
| `notes: Mapped[list["Note"]] = relationship(back_populates="owner", cascade="all, delete-orphan")` | Python-side link user → notes | `cascade`: deleting a user deletes their notes, so there are no orphaned private data |
| `class Note(Base)` / `__tablename__ = "notes"` | Notes table | |
| `owner_id: … ForeignKey("users.id"), index=True` | **The ownership column** | The heart of isolation. Indexed because *every* notes query filters on it |
| `title: … String(200)` / `body: … Text, default=""` | Content | Limits mirror the validation in `schemas.py` |
| `updated_at: … default=utcnow, onupdate=utcnow` | Auto-updated timestamp | SQLAlchemy sets it on every UPDATE |
| `owner: Mapped[User] = relationship(back_populates="notes")` | Note → user link | |

## `app/schemas.py`: validation (the bouncer)

| Code | What | Why |
|---|---|---|
| `import re` | Regular expressions | For the email shape check |
| `from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator` | Pydantic v2 tools | |
| `EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")` | "something@something.something", no spaces | Compiled once (fast). Deliberately simple; known limitation #5 |
| `Email = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254)]` | Reusable email type | Trim and lowercase **before** the length check, so `" Alice@X.com "` and `alice@x.com` are one account |
| `# Passwords are never stripped…` | Comment | The near-miss in POSTMORTEM.md |
| `Password = Annotated[str, StringConstraints(min_length=12, max_length=128)]` | Length rules only | NIST 800-63B: length beats "must contain a symbol". The **max** stops someone sending a 10 MB "password" to burn CPU on hashing (DoS) |
| `Title = …strip…, min_length=1, max_length=200` | Title rules | `"   "` becomes `""` and fails min_length, so whitespace-only titles are blocked |
| `Body = …max_length=10_000` | Body cap | Stops giant payloads |
| `class StrictModel(BaseModel): model_config = ConfigDict(extra="forbid")` | Base for **inputs** | Unknown fields → 422. **Mass-assignment defence**: `owner_id`, `is_admin` and so on can't be smuggled in |
| `class UserCreate(StrictModel): email: Email; password: Password` | Registration body | |
| `@field_validator("email") … if not EMAIL_PATTERN.match(value): raise ValueError` | Shape check | Runs **after** trimming/lowercasing; `ValueError` becomes a clean 422 |
| `class UserOut(BaseModel): model_config = ConfigDict(from_attributes=True)` | Response shape | `from_attributes` lets Pydantic read a SQLAlchemy object. **There's no `password_hash` field, so it can never leak** in a response (output filtering) |
| `class Token(BaseModel): access_token; token_type = "bearer"; expires_in` | Login response | The OAuth2 standard shape, which Swagger's Authorize button expects |
| `class NoteCreate(StrictModel): title: Title; body: Body = ""` | Create body | **No `owner_id` field**: the server sets it from the token |
| `class NoteUpdate(StrictModel): title: Title \| None = None; body: …` | PATCH body | All optional: a partial update |
| `@model_validator(mode="after") def no_null_values` | Reject explicit `null` | `{"title": null}` would otherwise try to save NULL into a NOT NULL column. `model_fields_set` = only the fields the client *actually sent* |
| `class NoteOut(BaseModel)` + `from_attributes=True` | Note response | No `owner_id` in output either; the client doesn't need it |

## `app/security.py`: hashing and tokens (no web code here)

| Code | What | Why |
|---|---|---|
| `import base64, hashlib, hmac, os` | Std-lib crypto | `hashlib.scrypt` = the hash; `hmac.compare_digest` = constant-time compare; `os.urandom` = secure random salt |
| `import jwt` | PyJWT | Industry-standard JWT library |
| `SCRYPT_R = 8; SCRYPT_P = 1; SALT_BYTES = 16; KEY_BYTES = 32` | Constants | r = block size, p = parallelism (OWASP values); a 128-bit salt and a 256-bit output |
| `def _scrypt(...)` / `maxmem = 128 * n * r + 1024 * 1024` | Memory budget | scrypt needs about `128·N·r` bytes = 128 MiB at N=2^17. Python's default cap is 32 MiB and would raise `ValueError`, so we compute the need and add 1 MiB of headroom |
| `return hashlib.scrypt(password.encode(), salt=…, n=…, r=…, p=…, maxmem=…, dklen=…)` | The actual hash | `.encode()` turns text into bytes (UTF-8) |
| `def hash_password(password, n=None)` / `n = n or settings.scrypt_n` | Hash with the current cost | The `n` argument lets tests and rehash checks use other costs |
| `salt = os.urandom(SALT_BYTES)` | **Fresh random salt per password** | Same password → different hash; defeats rainbow tables |
| `return f"scrypt${n}${SCRYPT_R}${SCRYPT_P}${salt_b64}${key_b64}"` | Self-describing string | Stores algorithm + parameters + salt + hash together, so we can **change the cost later** and still verify old hashes (the same idea as the `$2b$` format in bcrypt) |
| `def verify_password(password, stored_hash)` / `split("$")` / `b64decode(..., validate=True)` / `int(...)` | Parse the stored hash | Any malformed value → `ValueError` → `return False`. **Never crash on bad data** |
| `if algorithm != "scrypt": return False` | Unknown algorithm | Refuse rather than guess |
| `actual = _scrypt(password, salt, n, r, p, len(expected))` | Re-hash the attempt with the *stored* salt and cost | That's how you compare without ever storing the password |
| `return hmac.compare_digest(actual, expected)` | **Constant-time comparison** | `==` stops at the first differing byte, so response time leaks how many bytes matched. `compare_digest` always takes the same time |
| `def needs_rehash(...)` | Is this hash weaker than today's setting? | Login upgrades it (`auth.py`). This is how you raise security over time without forcing password resets |
| `@cache def dummy_hash()` | One real hash, computed lazily once | Used when the email doesn't exist (see `auth.py`). `@cache` avoids paying the 0.4 s more than once and avoids slowing startup |
| `def create_access_token(user_id)` / `now = datetime.now(UTC)` / `lifetime = timedelta(minutes=…)` | Token timing | |
| `payload = {"sub": str(user_id), "iat": now, "exp": now + lifetime, "type": "access"}` | JWT claims | `sub` = subject (user id, **must be a string** per the JWT spec, and PyJWT enforces this). `iat` = issued at. `exp` = expiry, checked automatically on decode. `type` stops other token kinds (for example a future refresh token) being used as access tokens |
| `jwt.encode(payload, settings.secret_key, algorithm=…)` | Sign with HMAC-SHA256 | Signature = HMAC(secret, header.payload) |
| `return token, int(lifetime.total_seconds())` | Token + seconds left | Clients know when to log in again |
| `def decode_access_token(token) -> int \| None` | Returns the user id or None | **One choke point**: every way a token can be bad becomes `None` |
| `jwt.decode(token, key, algorithms=[settings.jwt_algorithm], options={"require": ["exp","iat","sub"]})` | Verify the signature + expiry | `algorithms=[...]` is an **allow-list**. Without it an attacker could send `alg: none` (no signature) and some libraries would accept it. `require` rejects tokens missing these claims |
| `except jwt.PyJWTError: return None` | Catches every JWT failure | Bad signature, expired, malformed: all treated the same |
| `if payload.get("type") != "access": return None` | Token-type check | |
| `try: return int(payload["sub"]) except (TypeError, ValueError): return None` | Subject must be a number | A non-numeric `sub` can't crash the app |

## `app/deps.py`: "who is calling?"

| Code | What | Why |
|---|---|---|
| `from fastapi import Depends, HTTPException, status` | DI and errors | `status.HTTP_401_UNAUTHORIZED` is more readable than a bare `401` |
| `from fastapi.security import OAuth2PasswordBearer` | Extracts `Authorization: Bearer xxx` | Also wires up Swagger's Authorize button |
| `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")` | Where clients get tokens | If the header is missing, FastAPI returns **401 automatically** |
| `DbSession = Annotated[Session, Depends(get_db)]` | Reusable type alias | Write `db: DbSession` in any route and you get a session. FastAPI **caches** dependencies per request, so the user lookup and the route share one session |
| `def unauthorized(detail=...)` → `HTTPException(401, …, headers={"WWW-Authenticate": "Bearer"})` | Builds a 401 | The HTTP spec says a 401 should include `WWW-Authenticate`. A *function* (not a shared object) gives each request a fresh exception |
| `def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User` | The auth dependency | Dependencies can depend on dependencies; FastAPI resolves the tree |
| `user_id = decode_access_token(token)` / `if user_id is None: raise unauthorized()` | Bad token → 401 | |
| `user = db.get(User, user_id)` / `if user is None: raise unauthorized()` | Valid signature but the user is gone | Covers deleted accounts (tested by `test_valid_signature_for_nonexistent_user_is_rejected`) |
| `CurrentUser = Annotated[User, Depends(get_current_user)]` | Alias | `user: CurrentUser` in a route means "this route requires login". **Declarative security**: you can see it in the function signature |

## `app/routers/auth.py`: register, login, me

| Code | What | Why |
|---|---|---|
| `from fastapi.security import OAuth2PasswordRequestForm` | Standard login form | Fields `username` and `password`, sent as **form data** (not JSON) per the OAuth2 spec. Needs `python-multipart` |
| `from sqlalchemy.exc import IntegrityError` | DB constraint error | Raised when the `unique` email rule is violated |
| `router = APIRouter(prefix="/auth", tags=["auth"])` | Groups routes | Prefix saves repetition; tags group them in `/docs` |
| `EMAIL_TAKEN` / `BAD_LOGIN` constants | Messages defined once | Guarantees "wrong password" and "no such user" say *exactly* the same thing |
| `@router.post("/register", response_model=UserOut, status_code=201)` | Route declaration | `response_model` **filters the output**: even though we return a `User` with a hash, only `id`, `email` and `created_at` go out. 201 = Created |
| `def register(payload: UserCreate, db: DbSession) -> User:` | `def`, not `async def` | **Important:** scrypt is CPU-heavy and blocking. FastAPI runs plain `def` routes in a thread pool, so one slow hash doesn't freeze every other request. An `async def` here would block the event loop |
| `if db.scalar(select(User).where(User.email == payload.email)) is not None: raise 409` | Friendly duplicate check | Fast path with a clear error |
| `user = User(email=…, password_hash=hash_password(payload.password))` | Hash **before** storing | The plain password only lives in memory for this request |
| `db.add(user)` / `try: db.commit()` | Insert | |
| `except IntegrityError: db.rollback(); raise HTTPException(409…) from None` | **Race condition** guard | Two simultaneous sign-ups can both pass the check above; the DB's unique constraint catches the second. `rollback` resets the session; `from None` hides the internal traceback |
| `db.refresh(user)` / `return user` | Reload the generated `id` and `created_at` | |
| `@router.post("/login", response_model=Token)` | Login route | |
| `def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession)` | Parse the form | `Depends()` with no argument means "build this class from the request" |
| `email = form.username.strip().lower()` | Same normalisation as registration | Otherwise `Alice@x.com` couldn't log in |
| `user = db.scalar(select(User).where(User.email == email))` | Look up by email | Parameterised query, so injection-safe |
| `if user is None: verify_password(form.password, dummy_hash()); raise unauthorized(BAD_LOGIN)` | **Timing-attack defence** | Without the dummy check, "no such user" would answer in about 4 ms and "wrong password" in about 400 ms, so an attacker could map which emails are registered. Measured after the fix: 399.5 vs 400.2 ms p50 |
| `if not verify_password(...): raise unauthorized(BAD_LOGIN)` | Wrong password → 401 | Same message as above |
| `if needs_rehash(...): user.password_hash = hash_password(form.password); db.commit()` | **Transparent upgrade** | The only moment we have the plain password is at login, so that's when we re-hash with the stronger cost |
| `token, expires_in = create_access_token(user.id)` / `return Token(...)` | Issue the wristband | |
| `@router.get("/me", response_model=UserOut) def read_me(user: CurrentUser)` | Who am I | Shows the dependency doing all the work: the function body is one line |

## `app/routers/notes.py`: CRUD with isolation (the BONUS)

| Code | What | Why |
|---|---|---|
| `router = APIRouter(prefix="/notes", tags=["notes"])` | Groups routes | |
| `def get_owned_note(db, note_id, user) -> Note:` | **The single gatekeeper** | GET, PATCH and DELETE on a single note all go through this one function, so there's one place to audit and no chance of forgetting the check |
| `select(Note).where(Note.id == note_id, Note.owner_id == user.id)` | **Ownership inside the query** | Two conditions joined by AND. For someone else's note the DB returns *nothing*. We never load another user's data into memory |
| `if note is None: raise HTTPException(404, "Note not found")` | 404, not 403 | 403 would confirm the note exists (information leak). "Missing" and "not yours" are indistinguishable, as proven by the enumeration test |
| `@router.post("", …, status_code=201) def create_note(payload: NoteCreate, user: CurrentUser, db: DbSession)` | Create | `user: CurrentUser` makes login required |
| `note = Note(owner_id=user.id, **payload.model_dump())` | **Owner comes from the token, never from the client** | `**` unpacks `{"title":…, "body":…}` into keyword arguments. Safe because `NoteCreate` can only contain those two fields |
| `db.add(note); db.commit(); db.refresh(note); return note` | Save, reload id/timestamps, return | |
| `def list_notes(…, limit: Annotated[int, Query(ge=1, le=100)] = 20, offset: Annotated[int, Query(ge=0)] = 0)` | Pagination with bounds | `le=100` stops `?limit=1000000` dumping the table (DoS). Out-of-range values → 422 |
| `select(Note).where(Note.owner_id == user.id).order_by(Note.id).limit(limit).offset(offset)` | **Scoped list** | `order_by` makes pages stable (SQL doesn't guarantee an order otherwise) |
| `return list(db.scalars(query))` | Run the query, return ORM objects | `response_model=list[NoteOut]` serialises them |
| `def read_note(note_id: int, …)` → `get_owned_note(...)` | Read one | `note_id: int` means `/notes/abc` → 422 automatically |
| `def update_note(...)` / `for field, value in payload.model_dump(exclude_unset=True).items(): setattr(note, field, value)` | **PATCH = partial update** | `exclude_unset` only includes fields the client sent, so omitted fields stay unchanged |
| `@router.delete("/{note_id}", status_code=204) … db.delete(note); db.commit()` | Delete | 204 = success with no body |

## `app/main.py`: wiring

| Code | What | Why |
|---|---|---|
| `from contextlib import asynccontextmanager` | For the lifespan hook | |
| `from . import models  # noqa: F401` | Import for its side effect | Defining the classes registers the tables on `Base.metadata`. Without this import `create_all` would create **no tables**. `noqa` tells the linter the "unused" import is intentional |
| `@asynccontextmanager async def lifespan(_):` / `Base.metadata.create_all(bind=engine)` / `yield` | Startup hook | Code before `yield` runs at startup, after it at shutdown. Replaces the deprecated `@app.on_event("startup")`. `create_all` only creates missing tables (no migrations; known limitation #4) |
| `app = FastAPI(title=…, version=…, description=…, lifespan=lifespan)` | The app | Title and description appear in `/docs` |
| `app.include_router(auth.router); app.include_router(notes.router)` | Mount the routes | |
| `@app.get("/health") def health()` | Liveness probe | Load balancers and Kubernetes call this to check the process is alive |

---

## Tests (`tests/`)

**`conftest.py`**: pytest loads it automatically.
- `os.environ.setdefault(...)` lines run **before any `app` import**, because `config.py` reads env at import time. `SCRYPT_N=1024` makes hashing about 3 ms instead of 400 ms, so the suite runs in about 1 s.
- `client` fixture: `importorskip("fastapi")` (see the postmortem), then a **fresh in-memory SQLite per test** with `StaticPool` (in-memory SQLite disappears when its connection closes; StaticPool keeps exactly one connection alive). `app.dependency_overrides[get_db] = override_get_db` swaps the real DB for the test DB, which is dependency injection paying off. `with TestClient(app)` runs the lifespan. `overrides.clear()` and `engine.dispose()` clean up so tests can't affect each other.
- `register_and_login()` returns ready-to-use auth headers. The `alice` and `bob` fixtures each create a user.

**`test_security.py`** (unit, 12 tests): hash format and no plaintext · right/wrong password · salt makes hashes differ · whitespace significant · malformed hashes return False (never crash) · rehash detection · token round-trip · rejects: foreign key, expired, `alg=none`, spliced payload (header + *other* payload + original signature), wrong type, missing `exp`, non-numeric `sub`, garbage.

**`test_schemas.py`** (unit, 14 cases): email normalisation · 5 bad emails · 3 bad password lengths · passwords not trimmed · extra fields rejected · title trim/blank/too long · body limit · PATCH partial vs null.

**`test_auth.py`** (API, 10): register output has no hash · case-insensitive duplicate → 409 · 4 invalid bodies → 422 · login with messy email works · **wrong password and unknown email give byte-identical responses** · `/me` with good/none/garbage token · health.

**`test_notes.py`** (API, 4): full CRUD lifecycle · pagination values and bounds · login required · invalid input.

**`test_attacks.py`** (API, **14 attacks**, the red team): Bob vs Alice's note with GET/PATCH/DELETE (and Alice's note is checked unchanged afterwards) · list leak · enumerate ids 1–49 · mass-assign `owner_id` · token signed with a guessed key · `alg=none` · expired token · valid signature for a non-existent user · 3 SQL injections in login (and the users table survives) · SQL injection in a note title is stored as literal text.

## `scripts/eval.py`: the hard numbers
- Sets production `SCRYPT_N=2**17` so latency is realistic.
- `run_pytest()` runs pytest in a **subprocess** (with cheap hashing) and parses the final "N passed, M failed" line. Attack success rate = failed attack tests ÷ total attack tests.
- `measure()` times a function N times with `time.perf_counter()` (a monotonic, high-resolution clock). `percentile()` uses `statistics.quantiles(n=100)` for p50/p95.
- `latency_table()` builds an isolated app + DB, then times each endpoint, plus the **timing side-channel pair** (wrong password vs unknown email).
- Prints Markdown. CI appends it to the GitHub Actions job summary.

## CI (`.github/workflows/ci.yml`)
On every push: Python 3.11/3.12/3.13 matrix → install → `ruff check` (lint, including `S` = bandit security rules) → pytest, **failing on any skip** → eval report (3.12 only).

## Likely interview questions
- **"Why not bcrypt?"** It truncates at 72 bytes and isn't memory-hard. Argon2id would be my production pick; scrypt gave me memory-hardness with zero dependencies. See DESIGN.md.
- **"How do you log a user out with JWTs?"** You can't, by design; that's the trade-off of stateless tokens. Options: short expiry (done), a refresh token with rotation, a `jti` denylist in Redis.
- **"Why 404 not 403?"** 403 confirms existence. Don't leak.
- **"Where could IDOR still creep in?"** A new route that queries `Note` without going through `get_owned_note`. Mitigation: code review rule plus copying the attack test pattern. Postgres row-level security would enforce it at the database level.
- **"What happens under load?"** Login is CPU- and RAM-bound (0.4 s, 128 MiB). Rate-limit it, scale workers horizontally, and tune `SCRYPT_N`.
