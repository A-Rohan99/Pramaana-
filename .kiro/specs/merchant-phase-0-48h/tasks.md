# Implementation Plan: Satark Setu Merchant MVP — Phase 0 (48h Checkpoint)

## Overview

Phase 0 focuses on foundational MVP features needed by 48 hours into the hackathon:
1. **JWT authentication infrastructure** — user registration, login, token generation
2. **Merchant-scoped data isolation** — each merchant's data is isolated via shop_id in JWT
3. **Demo merchant fixture** — pre-created test accounts for demo flow
4. **Scam pipeline regression check** — verify core verification pipeline still works
5. **Frontend auth UI** — login form, JWT storage, redirect to dashboard
6. **Phase 0 checkpoint** — comprehensive end-to-end verification

All tasks are incremental and build on each other. Each task is marked as `not_started` initially.

---

## Tasks

- [x] 0.1 Set up JWT authentication infrastructure
  - Create `auth/` package with `__init__.py`, `jwt_utils.py`, `password.py`, `models.py`
  - Implement password hashing using bcrypt (`hash_password()`, `verify_password()`)
  - Implement JWT token generation (`create_access_token()`, `decode_token()`)
  - Create database tables: `User` (email, password_hash, created_at), `Shop` (shop_name, user_id FK, created_at)
  - Token payload includes: `shop_id`, `email`, `exp` (expiry: 30 days)
  - JWT secret: read from `JWT_SECRET` env var (generate with `secrets.token_urlsafe(32)` if missing)
  - _Requirements: Merchant authentication, shop isolation, token security_
  - _Acceptance:_
    - `hash_password("test123")` returns hashed string
    - `verify_password("test123", hashed)` returns True
    - `create_access_token({"shop_id": 1})` returns valid JWT string
    - `decode_token(jwt_str)` returns dict with shop_id, email, exp
    - User and Shop tables exist in DB with proper foreign keys

- [x] 0.2 Set up JWT middleware and request scope injection
  - Create `auth/middleware.py` — FastAPI middleware that extracts shop_id from JWT token
  - For every request except `/auth/signup`, `/auth/login`, `/`: require valid JWT header (`Authorization: Bearer <token>`)
  - Extract `shop_id` from decoded token and inject into `request.scope["shop_id"]`
  - Return HTTP 401 if token missing or invalid
  - Allow public endpoints: `/`, `/auth/signup`, `/auth/login`
  - _Requirements: Merchant isolation, request scoping_
  - _Acceptance:_
    - Request with valid JWT has `request.scope["shop_id"]` set
    - Request without JWT token to protected endpoint returns HTTP 401
    - Request with expired/invalid JWT returns HTTP 401
    - `/` and `/auth/endpoints` accessible without JWT

- [-] 0.3 Implement `/auth/signup` endpoint
  - POST `{"email": "merchant@example.com", "password": "password123", "shop_name": "My Store"}`
  - Validate email format (basic regex: `^[^\s@]+@[^\s@]+\.[^\s@]+$`)
  - Validate password length (min 8 chars)
  - Check for duplicate email — return HTTP 400 if email already exists
  - Create User record with hashed password
  - Create Shop record linked to user
  - Generate access token and return JWT in response
  - Response: `{"access_token": "<jwt>", "token_type": "bearer", "shop_id": 1, "shop_name": "My Store"}`
  - _Requirements: Merchant registration, shop creation_
  - _Acceptance:_
    - Signup with valid email/password/shop_name succeeds, returns JWT
    - Signup with duplicate email returns HTTP 400
    - Signup with password < 8 chars returns HTTP 400
    - Returned JWT decodes to correct shop_id and email

- [-] 0.4 Implement `/auth/login` endpoint
  - POST `{"email": "merchant@example.com", "password": "password123"}`
  - Query User table for matching email
  - If not found or password doesn't verify, return HTTP 401 (generic: "Invalid email or password")
  - If valid, generate new access token for user's shop_id
  - Response: `{"access_token": "<jwt>", "token_type": "bearer", "shop_id": 1}`
  - _Requirements: Merchant authentication_
  - _Acceptance:_
    - Login with correct credentials returns JWT
    - Login with wrong password returns HTTP 401
    - Login with nonexistent email returns HTTP 401
    - Returned JWT has correct shop_id

- [ ] 0.5 Create demo merchant fixture script
  - Create `scripts/setup_demo_merchants.py` — run at server startup or via manual command
  - Script creates two demo merchants:
    - `demo@merchant.local` / `DemoPass123!` — shop_name: "Demo Merchant 1" → shop_id will be 1
    - `demo2@merchant.local` / `DemoPass456!` — shop_name: "Demo Merchant 2" → shop_id will be 2
  - Each merchant's data is completely isolated (different shop_id in JWT)
  - Script idempotent — check for existing email before creating (no duplicate errors on re-run)
  - Call `setup_demo_merchants()` in `api.py` startup event
  - Log output: `"Demo merchants created: demo@merchant.local (shop_id=1), demo2@merchant.local (shop_id=2)"`
  - _Requirements: Demo readiness, repeatable setup_
  - _Acceptance:_
    - Script runs without errors
    - Both demo merchants appear in User table
    - Both merchants' shops appear in Shop table
    - Can login with either demo email and get valid JWT

- [x] 0.6 Verify core scam verification pipeline still works (regression check)
  - Test `/api/verify-text` endpoint with sample English scam message (no JWT required — assume public endpoint for MVP)
  - Input: `{"text": "Your SBI KYC is pending, update now or account will be blocked", "language": "english"}`
  - Expected: Returns ≥1 typology match (fake_kyc or similar) with confidence ≥55
  - Test with Hindi Devanagari scam: `{"text": "आपका SBI KYC पेंडिंग है, अभी अपडेट करें", "language": "hindi"}`
  - Expected: Returns ≥1 typology match (via to_english_for_matching translation)
  - Test with benign message: `{"text": "Please call me back", "language": "english"}`
  - Expected: Returns 0 matches (no false positives)
  - _Requirements: Scam classification regression, core pipeline integrity_
  - _Acceptance:_
    - English scam text → ≥1 match
    - Hindi scam text → ≥1 match (if IndicTrans2 model available)
    - Benign text → 0 matches
    - No HTTP errors or trace backs returned

- [ ] 0.7 Implement frontend login/logout UI
  - Update `frontend/index.html` with login form (initial UI before dashboard)
  - Form fields: email, password, shop_name (for signup toggle)
  - Add signup/login toggle (single form that switches between modes)
  - On successful login/signup: store JWT in localStorage as `authToken`
  - Redirect to dashboard at `/#/dashboard` or `/dashboard`
  - Add logout button in dashboard header — clears `authToken` from localStorage and redirects to login
  - Add "Request code" button in login form that calls a public endpoint for demo code (optional — can skip for MVP)
  - _Requirements: Merchant UX, authentication flow, session persistence_
  - _Acceptance:_
    - Login form visible at startup
    - Form accepts email and password input
    - Submit calls `/auth/login` with correct payload
    - JWT stored in localStorage after successful login
    - Dashboard loads after login
    - Logout button clears token and redirects to login

- [ ] 0.8 Phase 0 checkpoint — comprehensive end-to-end verification
  - Run full demo flow:
    1. Start server: `uvicorn api:app --reload --port 8000` from project root
    2. Server startup logs show: "Demo merchants created: demo@merchant.local (shop_id=1), demo2@merchant.local (shop_id=2)"
    3. Open frontend at `http://localhost:8000`
    4. See login form
    5. Login with `demo@merchant.local` / `DemoPass123!`
    6. See dashboard (or placeholder dashboard)
    7. Verify token in browser localStorage contains `shop_id: 1`
    8. Click logout — token cleared, redirect to login
    9. Test verify-text endpoint with curl or Postman: English scam message returns ≥1 match
    10. Test verify-text with Hindi scam: ≥1 match (if model available)
    11. Document any blockers
  - All auth tests pass: `pytest tests/test_auth.py -v` (if tests exist)
  - All core pipeline tests pass: `pytest tests/test_pipeline.py -v`
  - No HTTP 500 errors in logs during full demo flow
  - _Requirements: MVP readiness, end-to-end verification, demo success_
  - _Acceptance:_
    - Demo flow completes without errors
    - Merchants can login with JWT
    - JWT contains correct shop_id
    - Scam classification still works
    - No regressions from prior verification spec
    - Documentation of env setup (`.env` variables needed)

---

## Task Dependencies

```
0.1 (JWT infrastructure)
 ├─→ 0.2 (Middleware setup)
 │    ├─→ 0.3 (Signup endpoint)
 │    │    └─→ 0.5 (Demo merchants)
 │    │         └─→ 0.8 (Checkpoint)
 │    └─→ 0.4 (Login endpoint)
 │         └─→ 0.7 (Frontend login)
 │              └─→ 0.8 (Checkpoint)
 │
 0.6 (Verification regression — parallel with auth tasks)
 └─→ 0.8 (Checkpoint)
```

**Sequential order for implementation**:
1. 0.1 (Auth infrastructure) — must be done first
2. 0.2 (Middleware) — depends on 0.1
3. 0.3 + 0.4 (Signup + Login endpoints) — depend on 0.1 and 0.2
4. 0.5 (Demo fixture) — depends on 0.3 and 0.4
5. 0.6 (Pipeline regression) — can run in parallel, but confirm before checkpoint
6. 0.7 (Frontend auth UI) — depends on 0.3, 0.4, 0.2
7. 0.8 (Checkpoint) — depends on all above, runs last

---

## Environment Setup Required

Before starting any tasks, ensure:

- Python 3.10+ with `.venv` activated
- `pip install -r requirements.txt` succeeds
- `.env` file exists with at minimum:
  ```
  JWT_SECRET=<generate with: python -c "import secrets; print(secrets.token_urlsafe(32))">
  DATABASE_URL=sqlite:///./pramaan.db
  ```
- Database: SQLite (default, no special setup)
- FastAPI and uvicorn installed and working

---

## Testing Strategy (Optional but Recommended)

Create `tests/test_auth.py`:
- `test_signup_creates_user_and_shop()` — verify User and Shop tables populated
- `test_signup_duplicate_email_fails()` — HTTP 400 on duplicate
- `test_login_returns_jwt()` — JWT in response
- `test_login_wrong_password_fails()` — HTTP 401 on wrong password
- `test_middleware_injects_shop_id()` — shop_id in request.scope
- `test_middleware_rejects_no_token()` — HTTP 401 without JWT

Run: `pytest tests/test_auth.py -v` before task 0.8 checkpoint.

---

## Success Criteria for Phase 0

✅ All 8 tasks completed and passing  
✅ Demo merchants can login and receive valid JWT  
✅ Merchant data is isolated by shop_id  
✅ Scam verification pipeline works without regression  
✅ Frontend loads and has working login flow  
✅ No HTTP 500 errors during full demo flow  
✅ Documentation of env vars and startup command provided  

---

## Known Limitations (MVP 48h Checkpoint)

- Rate limiter is in-memory only (does not survive process restart)
- JWT tokens expire after 30 days (no refresh token yet)
- Dashboard is placeholder (full merchant features come in Phase 1)
- No merchant profile/settings page (Phase 1+)
- CORS is wide-open (will be tightened pre-production)
- Single-process FastAPI (horizontal scaling Phase 2+)

---

## Timeline Estimate

**Assuming 2–3 developers working in parallel:**
- Task 0.1: 1.5 hours
- Task 0.2: 1 hour
- Task 0.3: 1 hour
- Task 0.4: 45 minutes
- Task 0.5: 45 minutes
- Task 0.6: 30 minutes (mostly testing existing pipeline)
- Task 0.7: 2 hours (frontend + integration)
- Task 0.8: 1 hour (verification + documentation)

**Total: ~9 hours of development work** (suitable for 2–3 devs working 4–5 hours each over ~48h)

Parallel tracks:
- **Track A** (Auth): 0.1 → 0.2 → 0.3, 0.4 → 0.5 (sequential, ~5 hours)
- **Track B** (Frontend): 0.7 (waits on Track A, ~2 hours)
- **Track C** (Regression): 0.6 (parallel, ~1 hour)
- **Convergence**: 0.8 checkpoint (~1 hour)

