# Phase 0 — Execution Guide

## Quick Start (Copy-Paste Commands)

### 1. Before Starting (One-time setup)

```bash
# Activate venv
cd c:\Users\rohan\OneDrive\project\satark_setu
.venv\Scripts\activate

# Generate JWT secret
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"

# Add to .env (if not already present)
echo DATABASE_URL=sqlite:///./pramaan.db >> .env
# Then manually add the JWT_SECRET line from above output
```

### 2. Start the Server

```bash
# From project root with venv activated
uvicorn api:app --reload --port 8000
```

**Expected output in logs:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
<app logger>: Demo merchants created: demo@merchant.local (shop_id=1), demo2@merchant.local (shop_id=2)
```

### 3. Test Authentication Endpoints

```powershell
# Signup a new merchant
$response = Invoke-RestMethod `
  -Uri "http://localhost:8000/auth/signup" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"email":"newmerchant@test.local","password":"TestPass123","shop_name":"Test Shop"}'
$token = $response.access_token
echo "New JWT: $token"

# Login with demo merchant
$loginResp = Invoke-RestMethod `
  -Uri "http://localhost:8000/auth/login" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"email":"demo@merchant.local","password":"DemoPass123!"}'
$demoToken = $loginResp.access_token
echo "Demo token: $demoToken"

# Use token in protected endpoint
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/protected-endpoint" `
  -Method Get `
  -Headers @{"Authorization"="Bearer $demoToken"}
```

### 4. Test Scam Verification (No JWT Required for MVP)

```powershell
# English scam
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/verify-text" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"text":"Your SBI KYC is pending, update now or account will be blocked","language":"english"}'

# Hindi Devanagari scam
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/verify-text" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"text":"आपका SBI KYC पेंडिंग है, अभी अपडेट करें","language":"hindi"}'

# Benign message
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/verify-text" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"text":"Please call me back when you are free","language":"english"}'
```

### 5. Frontend Login Flow

1. Open browser: `http://localhost:8000`
2. See login form
3. Enter credentials:
   - Email: `demo@merchant.local`
   - Password: `DemoPass123!`
4. Click "Login"
5. Verify redirect to dashboard
6. Check DevTools (F12) → Application → LocalStorage → `authToken` (should see JWT)
7. Click "Logout" — token cleared, back to login form

---

## Task Execution Order

### Phase 1: Authentication Infrastructure (Parallel possible)

**Task 0.1**: JWT Infrastructure (1.5h) ← **START HERE**
- Create `auth/` package with jwt_utils.py, password.py, models.py
- Test: `from auth.jwt_utils import create_access_token, decode_token` (import should work)
- Check: User and Shop tables exist in DB after `db.init_db()`

**Task 0.2**: Middleware Setup (1h)
- Create `auth/middleware.py` — FastAPI middleware
- Add to `api.py`: `app.add_middleware(ShopScopeMiddleware)`
- Test: Request with valid JWT → `request.scope["shop_id"]` set; request without JWT → HTTP 401

**Parallel Track A - Endpoints**:

**Task 0.3**: Signup Endpoint (1h)
- Add `POST /auth/signup` to `api.py`
- Test endpoint with curl/Postman

**Task 0.4**: Login Endpoint (45m)
- Add `POST /auth/login` to `api.py`
- Test with demo merchant email/password

**Task 0.5**: Demo Merchants (45m)
- Create `scripts/setup_demo_merchants.py`
- Call from `api.py` startup event
- Verify logs show demo merchants created

### Phase 2: Regression & Frontend (Parallel with Phase 1)

**Task 0.6**: Pipeline Regression (30m — can run anytime)
- Test `/api/verify-text` with English, Hindi, benign text
- Verify ≥1 match for scams, 0 for benign
- Document any issues found

**Task 0.7**: Frontend Auth UI (2h — wait for 0.3, 0.4)
- Update `frontend/index.html` with login form
- Add localStorage JWT handling
- Test in browser

### Phase 3: Convergence

**Task 0.8**: Phase 0 Checkpoint (1h)
- Run full demo flow
- All tests pass
- No HTTP 500 errors
- Document final status

---

## Troubleshooting

### JWT Secret Not Set
```
Error: KeyError: 'JWT_SECRET'
Fix: Run: python -c "import secrets; print(secrets.token_urlsafe(32))"
     Add to .env: JWT_SECRET=<output_from_above>
```

### Database Error on Startup
```
Error: sqlite3.OperationalError: no such table: user
Fix: Run: python -c "import db; db.init_db()"
     Restart server
```

### Middleware Not Intercepting Requests
```
Error: request.scope["shop_id"] KeyError
Fix: Ensure middleware is added to app BEFORE routes:
     app.add_middleware(ShopScopeMiddleware) must come BEFORE @app.post routes
```

### Demo Merchants Not Created
```
Error: Login fails with "Invalid email or password"
Fix: Check if setup_demo_merchants() is called in startup event
     Manually create: python -c "from scripts.setup_demo_merchants import setup_demo_merchants; setup_demo_merchants()"
```

### Frontend Not Loading
```
Error: 404 on http://localhost:8000
Fix: Ensure frontend/index.html exists
     Check api.py has: app.mount("/", StaticFiles(...))
```

### CORS Errors in Browser
```
Error: fetch() blocked by CORS policy
Fix: Ensure api.py has CORS middleware (already present in current api.py)
     Restart server after any cors changes
```

### IndicTrans2 Model Not Found
```
Error: 401 OSError on to_english_for_matching()
Fix: This is expected (model gated on HuggingFace)
     Native-script input falls back to original text gracefully
     To enable: huggingface-cli login + request access
     For MVP: this is OK, skip for now
```

---

## Acceptance Criteria Checklist

Use this to verify each task is complete:

### Task 0.1: JWT Infrastructure
- [ ] `hash_password("test")` returns non-empty string
- [ ] `verify_password("test", hashed)` returns True
- [ ] `create_access_token({"shop_id": 1})` returns JWT string
- [ ] `decode_token(jwt_str)` returns dict with shop_id, email, exp
- [ ] User table exists with columns: email, password_hash, created_at
- [ ] Shop table exists with columns: shop_name, user_id (FK), created_at

### Task 0.2: Middleware
- [ ] Request with valid JWT → `request.scope["shop_id"]` = 1 (or correct shop_id)
- [ ] Request without JWT to `/api/protected` → HTTP 401
- [ ] Request with invalid JWT → HTTP 401
- [ ] Request to `/auth/signup` → HTTP 200 (no JWT required)
- [ ] Request to `/auth/login` → HTTP 200 (no JWT required)

### Task 0.3: Signup Endpoint
- [ ] `POST /auth/signup` with valid data → HTTP 200 + JWT in response
- [ ] Response includes: `access_token`, `token_type`, `shop_id`, `shop_name`
- [ ] New User record appears in database
- [ ] New Shop record appears in database
- [ ] JWT decodes to correct shop_id and email
- [ ] Signup with duplicate email → HTTP 400
- [ ] Signup with password < 8 chars → HTTP 400
- [ ] Signup with invalid email format → HTTP 400

### Task 0.4: Login Endpoint
- [ ] `POST /auth/login` with correct credentials → HTTP 200 + JWT
- [ ] JWT decodes to correct shop_id
- [ ] Login with wrong password → HTTP 401
- [ ] Login with nonexistent email → HTTP 401
- [ ] Response format: `{"access_token": "...", "token_type": "bearer", "shop_id": 1}`

### Task 0.5: Demo Merchants
- [ ] Server startup logs: "Demo merchants created: demo@merchant.local, demo2@merchant.local"
- [ ] `demo@merchant.local` / `DemoPass123!` login succeeds, returns JWT with shop_id=1
- [ ] `demo2@merchant.local` / `DemoPass456!` login succeeds, returns JWT with shop_id=2
- [ ] Running setup script twice doesn't fail (idempotent)

### Task 0.6: Pipeline Regression
- [ ] English scam text → `/api/verify-text` returns ≥1 match, confidence ≥55
- [ ] Hindi Devanagari scam → ≥1 match (or graceful fallback if model unavailable)
- [ ] Benign text → 0 matches
- [ ] No HTTP 500 errors in any response

### Task 0.7: Frontend Auth UI
- [ ] Frontend loads at `http://localhost:8000`
- [ ] Login form visible with email + password fields
- [ ] Form accepts input and submits on "Login" button
- [ ] Successful login → token stored in localStorage as `authToken`
- [ ] Successful login → redirect to dashboard (or placeholder page)
- [ ] Dashboard shows logout button
- [ ] Click logout → token cleared from localStorage, redirect to login form

### Task 0.8: Phase 0 Checkpoint
- [ ] All tasks 0.1–0.7 complete and passing acceptance criteria
- [ ] Full demo flow (signup → login → dashboard → logout) runs without errors
- [ ] No HTTP 500 errors in server logs during full flow
- [ ] Tests pass: `pytest tests/test_auth.py -v` (if tests written)
- [ ] Scam verification endpoint still works
- [ ] Documentation of .env setup and startup command created

---

## Files to Inspect After Each Task

### Task 0.1
Check files exist:
- `auth/__init__.py`
- `auth/jwt_utils.py` (contains `create_access_token`, `decode_token`)
- `auth/password.py` (contains `hash_password`, `verify_password`)
- `auth/models.py` (contains `User`, `Shop` ORM models)

Check database:
```python
python -c "import db; db.init_db(); import sqlite3; conn = sqlite3.connect('pramaan.db'); cur = conn.cursor(); print(cur.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall())"
```
Expected: tables including 'user', 'shop'

### Task 0.2
Check in `api.py`:
- Import statement: `from auth.middleware import ShopScopeMiddleware`
- Middleware registration: `app.add_middleware(ShopScopeMiddleware)`

### Task 0.3
Check in `api.py`:
- Route exists: `@app.post("/auth/signup")`
- Function creates User and Shop records

### Task 0.4
Check in `api.py`:
- Route exists: `@app.post("/auth/login")`
- Function queries User by email and verifies password

### Task 0.5
Check file exists:
- `scripts/setup_demo_merchants.py` with function `setup_demo_merchants()`

Check in `api.py` startup:
- `setup_demo_merchants()` is called

### Task 0.6
Run and check output:
```bash
curl -X POST http://localhost:8000/api/verify-text \
  -H "Content-Type: application/json" \
  -d '{"text":"Your SBI KYC is pending, update now","language":"english"}'
```
Expected: JSON response with `matches` array containing ≥1 entry

### Task 0.7
Check files:
- `frontend/index.html` contains `<form>`, email input, password input, login button
- JavaScript function to store JWT: `localStorage.setItem('authToken', response.access_token)`
- Logout button clears token

### Task 0.8
Check logs for full flow and no errors:
```bash
# Run full demo in sequence, check logs for errors
```

---

## Time Tracking Template

Use this to track actual vs. estimate:

| Task | Estimated | Actual | Status | Blocker |
|---|---|---|---|---|
| 0.1 | 1.5h | ___ | ⬜ | ___ |
| 0.2 | 1h | ___ | ⬜ | ___ |
| 0.3 | 1h | ___ | ⬜ | ___ |
| 0.4 | 45m | ___ | ⬜ | ___ |
| 0.5 | 45m | ___ | ⬜ | ___ |
| 0.6 | 30m | ___ | ⬜ | ___ |
| 0.7 | 2h | ___ | ⬜ | ___ |
| 0.8 | 1h | ___ | ⬜ | ___ |
| **TOTAL** | **9h** | ___ | | |

Legend:
- ⬜ not_started
- 🟡 in_progress
- 🟢 completed
- 🔴 blocked

---

## Success Signals (Confirm Before Moving On)

1. **Server starts** → logs show "Demo merchants created"
2. **Login works** → JWT token returned and can be used in headers
3. **Middleware active** → requests without JWT get HTTP 401
4. **Scam classification** → English/Hindi scams return matches
5. **Frontend loads** → no 404 or JavaScript errors
6. **localStorage persists** → authToken visible in DevTools
7. **Logout clears token** → authToken removed from localStorage
8. **Checkpoint passes** → full demo flow runs end-to-end without errors

---

## Post-Phase 0 Readiness Check

✅ Is all code committed to git?  
✅ Are env vars (.env) documented?  
✅ Is database schema versioned (migration script)?  
✅ Are demo credentials documented somewhere secure?  
✅ Is the startup command documented in README?  
✅ Are there known limitations documented?  
✅ Is Phase 1 planning started?  

If all yes → **Phase 0 COMPLETE** → Ready for Phase 1

