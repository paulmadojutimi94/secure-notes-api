# Postmortem: "26 passed" that hid 28 skipped tests

**Severity:** Medium (no bad code shipped, but our confidence was false) · **Date:** 12 Nov 2026 · **Status:** Fixed

## Summary
During development the local test run printed a green result, but **more than half the suite never ran**. Every API-level test, including all 14 security attacks, had been skipped. If we had trusted the colour of the output, we would have published a "fully tested" authenticated API whose authentication had never been exercised over HTTP.

## Timeline
| Step | What happened |
|---|---|
| 1 | Wrote the unit tests (hashing, JWT, validation). These only need the standard library, PyJWT and Pydantic |
| 2 | Wrote the API tests (auth, notes CRUD, attack suite). These need FastAPI, SQLAlchemy and httpx |
| 3 | The build workspace had **no network access for `pip`**, so FastAPI couldn't be installed. `conftest.py` uses `pytest.importorskip("fastapi")`, so each API test **skipped** instead of failing |
| 4 | Output: `26 passed, 28 skipped in 0.20s`. The run looked green |
| 5 | **Detection:** read the full summary line instead of the colour and noticed that 28 > 26. The majority of tests were missing |
| 6 | Pushed to GitHub Actions, which installs real dependencies: **54 passed** on Python 3.11, 3.12 and 3.13 |
| 7 | **Fix:** CI now fails the build if the word "skipped" appears in the pytest output |

## Root cause
`importorskip` is the right tool for *optional* features. It was the wrong tool here because FastAPI isn't optional: it's the product. A missing core dependency should be a loud failure, not a polite skip. pytest's default treats skips as success (exit code 0), so nothing downstream noticed.

## Why it matters
Skips are how test suites rot quietly. A suite that is "always green" while half of it is skipped is worse than no suite, because it produces **false confidence**. In an auth system, the skipped half was the half that mattered most: the attack tests.

## What we changed
1. **CI gate:** `pytest -q -rs | tee pytest.log` followed by a failure if `skipped` appears. `-rs` also prints *why* each test was skipped.
2. **Separation kept on purpose:** unit tests still run without FastAPI, which gives fast feedback anywhere. The CI gate guarantees the full suite runs before code is trusted.
3. **Hard numbers come from CI, not laptops:** `scripts/eval.py` runs in Actions and writes to the job summary, so the README numbers are reproducible.

## Near-miss caught during design (no incident)
Pydantic's convenient `str_strip_whitespace=True` setting would have trimmed **passwords** at registration while login (an OAuth2 form) doesn't trim. Anyone whose password started or ended with a space would have been locked out forever. We applied trimming per field (emails and titles only) and added `test_password_is_not_stripped` and `test_whitespace_in_passwords_is_significant` to lock this in.

## Lessons
- Read the **numbers** in a test summary, not the colour.
- "Passed" means *ran and passed*. Make your pipeline enforce that.
- Test the attacker's path, not only the happy path. 14 of 54 tests are attacks.
