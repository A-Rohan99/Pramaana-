# Satark Setu Merchant MVP — Phase 0 (48h Checkpoint) — SUMMARY

## Mission

Build foundational merchant authentication and demo infrastructure within the first 48 hours of the hackathon, integrating JWT-based multi-tenant isolation with the existing Pramaan scam verification pipeline.

## What Gets Delivered

By the end of Phase 0 (48 hours), users will be able to:

1. **Sign up** as a new merchant with email, password, and shop name
2. **Log in** to retrieve a JWT token that identifies their merchant/shop
3. **Demo the verification flow** using pre-created test merchant accounts
4. **See the dashboard** (placeholder UI initially) after successful login
5. **Verify the core scam detection pipeline** still works without regression

## Core Components

### 1. JWT Authentication (`auth/` package)
- Password hashing with bcrypt
- JWT token generation (30-day expiry)
- Token payload: `{shop_id, email, exp}`
- Database models: `User` (email, password_hash), `Shop` (shop_name, user_id FK)

### 2. Request Middleware
- Extract `shop_id` from JWT header
- Inject into `request.scope["shop_id"]` for shop-scoped queries
- Protect all endpoints except public ones (`/`, `/auth/*`)

### 3. REST Endpoints
- **POST /auth/signup** — Create user + shop, return JWT
- **POST /auth/login** — Authenticate email/password, return JWT
- Both endpoints validate input and return proper HTTP status codes (400, 401)

### 4. Demo Merchant Fixture
- Two pre-created accounts: `demo@merchant.local` and `demo2@merchant.local`
- Each with isolated shop_id (1, 2) and independent data
- Created automatically at server startup (idempotent)

### 5. Frontend Login UI
- Email + password form
- Signup/login toggle
- JWT stored in localStorage after successful auth
- Redirect to dashboard on success
- Logout button that clears token and redirects

### 6. Pipeline Regression Check
- Verify `/api/verify-text` still classifies scams correctly
- Test with English, Hindi (Devanagari), and benign text
- Ensure no HTTP 500 errors from auth changes

## Task Breakdown (8 Tasks)

| Task | Title | Duration | Dependencies |
|---|---|---|---|
| 0.1 | JWT infrastructure | 1.5h | None |
| 0.2 | Middleware setup | 1h | 0.1 |
| 0.3 | Signup endpoint | 1h | 0.1, 0.2 |
| 0.4 | Login endpoint | 45m | 0.1, 0.2 |
| 0.5 | Demo merchants | 45m | 0.3, 0.4 |
| 0.6 | Pipeline regression | 30m | (parallel) |
| 0.7 | Frontend auth UI | 2h | 0.3, 0.4, 0.2 |
| 0.8 | Checkpoint | 1h | All above |

**Total**: ~9 hours (suitable for 2–3 devs working 4–5 hours each)

## Implementation Sequence

```
Start: Day 0 Hour 0
│
├─ Dev A: Start 0.1 (JWT infrastructure) ──→ 1.5h
│  ├─ Dev B: Wait for 0.1 complete, start 0.2 (Middleware) ──→ 1h
│  │  ├─ Dev A: Start 0.3 (Signup) in parallel with 0.2 ──→ 1h
│  │  │  ├─ Dev B: Start 0.4 (Login) after 0.2 done ──→ 45m
│  │  │  │  ├─ Dev C: Start 0.5 (Demo fixture) after 0.3,0.4 ──→ 45m
│  │  │  │  └─ Dev A: Start 0.7 (Frontend) after 0.4 ──→ 2h
│  │  │  │
│  ├─ Dev C: Start 0.6 (Regression) in parallel ──→ 30m
│  │
│  └─ All: Converge at 0.8 (Checkpoint) ──→ 1h
│
End: Day 0 Hour ~9 (or by Hour 48 with breaks/reviews)
```

**Critical path**: 0.1 → 0.2 → 0.3/0.4 → 0.7 → 0.8 (sequential, ~7–8 hours)  
**Parallel tracks reduce time** to ~6–7 hours of critical path with 2–3 devs.

## Success Criteria

✅ **Task 0.1**: Password hashing and JWT token generation work correctly  
✅ **Task 0.2**: Middleware injects shop_id into request scope; rejects missing/invalid JWT  
✅ **Task 0.3**: Signup creates User + Shop, validates inputs, returns JWT  
✅ **Task 0.4**: Login authenticates and returns JWT; rejects wrong password  
✅ **Task 0.5**: Demo merchants created at startup; both login successfully  
✅ **Task 0.6**: Scam classification endpoint returns ≥1 match for scam text, 0 for benign  
✅ **Task 0.7**: Frontend loads, login form functional, token stored in localStorage, logout works  
✅ **Task 0.8**: Full demo flow (login → dashboard → logout) completes without HTTP 500 errors  

## Key Architecture Decisions

### Multi-Tenant Isolation
- Each merchant has a unique `shop_id` (primary key in Shop table)
- JWT payload includes `shop_id`; all requests filtered by this shop_id
- Future: queries automatically scope to `request.scope["shop_id"]`
- Prevents cross-merchant data leaks

### Stateless Authentication
- JWT tokens, not session cookies
- Tokens expire after 30 days (refresh token not yet implemented)
- Ideal for scalability and microservice architectures

### Public Endpoints (MVP)
- `/auth/signup`, `/auth/login`, `/` — accessible without JWT
- `/api/verify-text` — currently public (no merchant context yet, Phase 1 will add)
- All other endpoints — require valid JWT

### Database (SQLite)
- Lightweight, no external DB service needed
- Single-file storage in project directory
- Sufficient for MVP; Phase 2+ can migrate to PostgreSQL

## Known Limitations (Acceptable for MVP)

- **In-memory rate limiter** — does not survive process restart
- **No refresh token** — tokens expire after 30 days (users re-login)
- **Placeholder dashboard** — just shows "You are logged in" (Phase 1 adds merchant features)
- **No merchant profile/settings** — Phase 1+
- **CORS wide-open** — will be tightened pre-production
- **Single-process FastAPI** — no horizontal scaling yet (Phase 2+)

## Environment Setup

**Before starting development:**

```bash
# 1. Activate venv
.venv\Scripts\activate

# 2. Create/update .env
echo JWT_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(32))") >> .env
echo DATABASE_URL=sqlite:///./pramaan.db >> .env

# 3. Ensure dependencies installed
pip install -r requirements.txt

# 4. Create tables (if not auto-initialized by ORM)
python -c "import db; db.init_db()"

# 5. Start server
uvicorn api:app --reload --port 8000
```

## Files to Create/Modify

### Create
- `auth/__init__.py` (package marker)
- `auth/jwt_utils.py` (token generation/validation)
- `auth/password.py` (bcrypt hashing)
- `auth/models.py` (User, Shop ORM models)
- `auth/middleware.py` (FastAPI middleware)
- `scripts/setup_demo_merchants.py` (demo fixture)
- `tests/test_auth.py` (auth tests — optional but recommended)

### Modify
- `api.py` (add auth routes, import middleware, call demo fixture in startup)
- `db.py` (add User and Shop table schemas, init logic)
- `frontend/index.html` (add login form, logout button, localStorage JWT handling)

## Testing Strategy

**Unit tests** (create `tests/test_auth.py`):
- `test_password_hash_and_verify()`
- `test_jwt_token_creation_and_decode()`
- `test_signup_endpoint()`
- `test_login_endpoint()`
- `test_middleware_injects_shop_id()`

**Integration tests** (manual or with pytest-asyncio):
- Full signup → login → dashboard flow
- Verify scam endpoint still works
- Check localStorage JWT after login

**Command to run**:
```bash
pytest tests/test_auth.py -v
```

## Demo Flow (Task 0.8 Checkpoint)

**Step 1: Start server**
```bash
uvicorn api:app --reload --port 8000
```
Expected: Logs show "Demo merchants created: demo@merchant.local, demo2@merchant.local"

**Step 2: Open frontend**
```
http://localhost:8000
```
Expected: Login form appears

**Step 3: Login as demo merchant**
- Email: `demo@merchant.local`
- Password: `DemoPass123!`

**Step 4: Verify redirect to dashboard**
- Should see dashboard (placeholder OK)
- Check browser DevTools → localStorage → `authToken` (should contain JWT)

**Step 5: Logout**
- Click logout button
- Token cleared from localStorage
- Redirected to login form

**Step 6: Test scam verification** (via curl or Postman)
```bash
curl -X POST http://localhost:8000/api/verify-text \
  -H "Content-Type: application/json" \
  -d '{"text": "Your SBI KYC is pending, update now or account blocked", "language": "english"}'
```
Expected: `matches` contains ≥1 typology match, confidence ≥55

**Step 7: Test with Hindi Devanagari**
```bash
curl -X POST http://localhost:8000/api/verify-text \
  -H "Content-Type: application/json" \
  -d '{"text": "आपका SBI KYC पेंडिंग है, अभी अपडेट करें", "language": "hindi"}'
```
Expected: ≥1 match (if IndicTrans2 model available; else fallback returns 0 matches gracefully)

**Step 8: Document and declare Phase 0 complete**
- All tests pass
- No HTTP 500 errors in logs
- Demo flow works end-to-end
- Ready for Phase 1 (merchant features, real transaction verification)

## Next Steps (Phase 1 — Beyond 48h)

- Merchant profile page (shop name, email, phone, UPI ID)
- Role-based access (shop_owner, staff member)
- Merchant dashboard with transaction history
- SMS/WhatsApp webhook handlers scoped to merchant's shop_id
- Real transaction processing (UPI, bank, invoice integration)
- Merchant-specific settings (notification preferences, default language)
- Analytics dashboard (scams detected, transactions processed)

## Rollback / Recovery Plan

If a task fails:

1. **Task 0.1 fails**: Delete `auth/` package, revert `db.py` changes, restart
2. **Task 0.2 fails**: Comment out middleware in `api.py`, continue with manual `shop_id` passing for now
3. **Task 0.3/0.4 fail**: Revert `api.py` endpoint code, use manual curl testing instead
4. **Task 0.5 fails**: Create demo merchants manually via Python REPL:
   ```python
   import db
   from auth.password import hash_password
   db.insert_user("demo@merchant.local", hash_password("DemoPass123!"))
   # (then create Shop manually)
   ```
5. **Task 0.6 fails**: This is regression check; if it fails, debug with `local_pipeline_test.py`
6. **Task 0.7 fails**: Revert frontend changes, use curl for testing instead of browser
7. **Task 0.8 fails**: Run individual tasks' acceptance tests, fix blockers one by one

## Questions?

Refer to **tasks.md** for detailed task descriptions and acceptance criteria.

