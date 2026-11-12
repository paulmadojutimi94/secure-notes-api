# Backend engineering from first principles

*Written for a first-year CS student with no backend experience. Read it top to bottom once, then keep it open while you read the code.*

---

## 1. What is a "backend"?

Think of a restaurant.
- The **frontend** is the dining room: the menu and the table, what you see and touch.
- The **backend** is the kitchen: where the real work happens and where the ingredients (data) are kept.
- The **API** is the **waiter**. You never walk into the kitchen yourself. You give the waiter an order in a fixed format, and they bring back a plate or say "sorry, we're out".

This project is a kitchen and a waiter. There's no dining room, but FastAPI gives us a free menu you can click: the `/docs` page.

## 2. HTTP: how you talk to the waiter

Every request has:
- A **method** (the verb): `GET` = read, `POST` = create, `PATCH` = change part of something, `DELETE` = remove.
- A **path** (the noun): `/notes/7` means "note number 7".
- **Headers** (extra information on the envelope), for example `Authorization: Bearer <token>`.
- Sometimes a **body**, usually JSON: `{"title": "Groceries"}`.

Every response has a **status code**, a 3-digit mood:

| Code | Meaning | In this project |
|---|---|---|
| 200 / 201 / 204 | OK / Created / Done, nothing to show | Success |
| 401 | "I don't know who you are" | Missing or bad token |
| 404 | "That doesn't exist" | Also used when it's **someone else's** note (see §7) |
| 409 | "Conflict" | Email already registered |
| 422 | "Your order doesn't make sense" | Validation failed |

**CRUD** = Create, Read, Update, Delete. These are the four things you can do to data, and they map onto POST, GET, PATCH and DELETE.

## 3. The database: a very organised spreadsheet

A SQL database is a set of spreadsheets (**tables**) with strict rules.

`users` table:

| id | email | password_hash |
|---|---|---|
| 1 | alice@example.com | scrypt$131072$8$1$… |

`notes` table:

| id | owner_id | title |
|---|---|---|
| 1 | **1** | Alice's secret |

`owner_id` is a **foreign key**: it points at a row in `users`. That one column is how we know who owns each note.

**SQLAlchemy** (an *ORM*) lets us describe the tables as Python classes and write queries in Python instead of raw SQL strings. That matters for safety, as §8 explains.

## 4. Input validation: the bouncer checks your ID *format*

Before anything reaches the kitchen, **Pydantic** checks the order:
- Is the email shaped like an email?
- Is the password 12–128 characters long?
- Is the title between 1 and 200 characters?
- **Did you send any field we didn't ask for?** If you did, you're rejected.

That last rule stops a sneaky attack called **mass assignment**. Imagine a form asking for your name, and you add `"is_admin": true` hoping the server saves it blindly. Our server says 422 to anything it didn't ask for.

Why validate at the door? Once you've checked IDs at the entrance, nobody inside has to check again. The rest of the code can trust its inputs.

## 5. Password hashing: the smoothie that can't be un-blended

**Never store passwords.** If the database leaks (and databases do leak), every user's password leaks with it, and people reuse passwords everywhere.

Instead we store a **hash**:
- **Hashing is like a smoothie blender.** Put in strawberries and you always get the same strawberry smoothie, but you can't turn a smoothie back into strawberries.
- At login we blend the password you just typed and compare the smoothies. If they match, the password was right. We never needed to keep the strawberries.

Two extra ingredients:
- **Salt:** a random value mixed in for each user. Two people with the password `password123` get completely different hashes, so an attacker can't crack everyone at once with a pre-computed table ("rainbow table").
- **Slow on purpose:** our blender (scrypt) takes about 0.4 seconds and 128 MB of memory per blend. For you, logging in once, that's nothing. For an attacker trying a billion guesses, it's roughly 12 years per CPU core. Normal hash functions like SHA-256 are fast, which is great for checking files and terrible for passwords.

## 6. Authentication: the festival wristband (JWT)

Typing your password on every request would be slow (0.4 s each time) and risky. So:

1. You log in once with your email and password.
2. The server gives you a **token**, a **festival wristband**.
3. You show the wristband on every later request: `Authorization: Bearer <token>`.

Our wristband is a **JWT** (JSON Web Token). It has three parts separated by dots:
`header.payload.signature`
- **Payload:** `{"sub": "1", "exp": …}`, meaning "this is user 1, valid until 17:30".
- **Signature:** a stamp made with a **secret key** that only the server knows.

Anyone can *read* a wristband, but nobody can **forge** one, because changing a single character breaks the stamp. Our tests try to forge them in four ways (wrong key, no signature at all, expired, edited payload), and all of them are rejected.

**Authentication** = *who are you?* (the wristband).
**Authorisation** = *are you allowed to do this?* (next section).

## 7. Authorisation: the hotel key card (the BONUS)

Here's the bug this project exists to prevent. A hotel gives you a key card for room 101. You're a legitimate guest with a valid card. But what if your card *also opens room 102*?

In APIs this is called **IDOR** (Insecure Direct Object Reference) or **BOLA**. It's the **#1 API security risk** on OWASP's list. Alice owns `/notes/1`. Bob logs in properly and then simply asks for `/notes/1`. A naïve server checks "is Bob logged in?" (yes) and hands it over.

Our fix: the database query itself includes the owner:

```sql
SELECT * FROM notes WHERE id = 1 AND owner_id = <Bob's id>
```

For Bob, that returns nothing, *by construction*. He can't forget the check, because the check is part of the question being asked.

Why **404** and not **403 Forbidden**? 403 means "it exists, but you can't have it", which confirms the note exists. 404 tells Bob nothing. A good hotel says "no such room", not "that's someone else's room".

## 8. SQL injection: why we never glue strings together

If code built SQL like this:

```python
"SELECT * FROM users WHERE email = '" + email + "'"
```

then an attacker types the email `' OR '1'='1`, and the query becomes "find users where email is blank **or 1 equals 1**", which matches everyone. SQLAlchemy sends your data **separately** from the query (as *parameters*), so the database treats it purely as text, never as commands. Our tests try four injection payloads. Each one is just stored or looked up as harmless text.

## 9. Tests: proving it, not hoping it

- **Unit tests** check one small piece on its own (for example "does `verify_password` reject a wrong password?").
- **API tests** send real HTTP requests to the app, using a throwaway in-memory database for each test.
- **Attack tests** act like Bob the attacker. *If any attack ever succeeds, the build goes red.*

We run them automatically on every push with **GitHub Actions (CI)** on three Python versions. See POSTMORTEM.md for why "green" isn't always green.

## 10. Words to use in an interview

| Term | One-line meaning |
|---|---|
| Hashing vs encryption | Hashing is one-way (passwords). Encryption is two-way, with a key (messages) |
| Salt | Random value per user so identical passwords produce different hashes |
| Work factor / cost | How slow the hash is on purpose (scrypt's N) |
| JWT | A signed, self-contained token; stateless authentication |
| Stateless | The server doesn't need to remember sessions; the token carries the information |
| AuthN vs AuthZ | Who you are vs what you're allowed to do |
| IDOR / BOLA | Accessing another user's object by changing an ID |
| Mass assignment | Sneaking extra fields such as `owner_id` or `is_admin` into a request |
| Timing attack | Learning secrets from *how long* a response takes |
| Dependency injection | FastAPI hands each route its database session and current user automatically |
| ORM | Python classes ↔ database tables |
| p50 / p95 latency | The time half / 95% of requests finish under |
