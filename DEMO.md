# 3-minute demo script

**Setup before recording:** terminal and browser side by side. `rm -f notes.db`, export `SECRET_KEY`, run `uvicorn app.main:app`. Open `http://127.0.0.1:8000/docs`.

| Time | Show | Say |
|---|---|---|
| 0:00–0:20 | README top section | "This is an authenticated API. Registering and logging in is the easy part. The hard part is making sure **you can never see my data**. That bug, called IDOR, is number one on OWASP's API Top 10." |
| 0:20–0:45 | Swagger: `POST /auth/register` with `alice@example.com` / `correct-horse-battery`. Then try `"password": "short"` → 422 | "Validation happens at the door. Weak passwords never reach the database. The response doesn't include the password hash." |
| 0:45–1:05 | Terminal: `sqlite3 notes.db "select email, password_hash from users"` | "The password is stored as a scrypt hash: salted, slow on purpose, and impossible to reverse. Each guess costs an attacker 0.4 seconds and 128 MB of RAM." |
| 1:05–1:30 | **Authorize** as Alice → `POST /notes` "PIN 1234" → note id 1 | "Logging in gives a signed token that expires in 30 minutes. Every request carries it, a bit like a festival wristband." |
| 1:30–2:05 | Log out, register and authorise as **Bob**. `GET /notes/1` → **404**. `PATCH /notes/1` → 404. `GET /notes` → `[]` | "Bob is logged in, but he isn't the owner. He gets 404, not 403, so he can't even confirm the note exists. Every query includes `owner_id = me`." |
| 2:05–2:20 | `POST /notes` with `{"title":"x","owner_id":1}` → 422 | "He can't plant data in Alice's account either. Unknown fields are rejected." |
| 2:20–2:45 | Terminal: `pytest -q` → 54 passed; then the GitHub Actions summary with the eval table | "54 tests on three Python versions. Fourteen of them are attacks: forged tokens, `alg=none`, SQL injection, ID enumeration. The attack success rate is zero." |
| 2:45–3:00 | README "Known failures" | "What's next: rate limiting and token revocation. I've documented exactly what this doesn't do yet." |

**Recording tips:** 1080p, zoom the browser to 125%, hide bookmarks, and pre-type the JSON bodies in a scratch file.
