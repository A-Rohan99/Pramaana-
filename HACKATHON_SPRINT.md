# Satark Setu Merchant OS — Hackathon Sprint Plan

**Timeline**: 2–3 weeks (10–15 dev days for 1 developer working full-stack)  
**Goal**: Ship a production-ready MVP that demonstrates both scam detection AND merchant OS multi-tenancy  
**Strategy**: Reuse existing working code aggressively; focus on auth + isolation layers only; ship fast

---

## Executive Summary

### What's Already Working ✅
- **FastAPI backend** with 30+ endpoints, full pipeline (OCR, voice, AI classification)
- **Scam detection pipeline** (typology matching, risk scoring, community reports)
- **Telegram bot** + WhatsApp/SMS webhooks
- **Translations** (IndicTrans2, Whisper), **AI chat** (Gemini 2.5 Flash Lite)
- **SQLite DB** with 8 tables (messages, contacts, ledgers, inventory, etc.)
- **Static HTML frontend** (basic but functional)

### What's Missing ❌
- **Authentication** — no user login, no JWT, no session management
- **Multi-tenancy** — no shop isolation, no tenant context middleware
- **Merchant dashboard** — stats, ledger filtering, inventory scoped to shop
- **Frontend auth flows** — login/signup pages, protected routes

### What We're Skipping ⏭️
- PostgreSQL migration (SQLite is fine for hackathon; migrate post-demo)
- Next.js rewrite (too slow; enhance existing HTML frontend)
- Admin console (not needed for demo)
- Observability/monitoring beyond stdout logging
- Comprehensive test suite (test critical paths only)

### Success Criteria
1. **48h**: User can signup/login with email+password; JWT works; demo merchant account active
2. **72h**: Two independent merchants can log in; each sees only their own data; shop isolation enforced
3. **Day 5**: Ledger + inventory scoped to shop; CSV import/export works
4. **Day 7**: Mobile-responsive UI; demo script ready; zero console errors; deploy to staging

---

## Phase 0: Foundation (48 Hours)

**Objective**: Get v1.0 running with auth layer + demo merchant account

### 0.1 — Set up auth infrastructure (8 hours)
- [ ] Create `auth/` package with JWT token generation/validation
- [ ] Implement password hashing (bcrypt)
- [ ] Create User table in SQLite (`id`, `email`, `password_hash`, `shop_id`, `is_active`, `created_at`)
- [ ] Create Shop table in SQLite (`id`, `name`, `created_at`)
- [ ] Implement `/auth/signup` endpoint (POST email/password → create user+shop → return JWT)
- [ ] Implement `/auth/login` endpoint (POST email/password → validate → return JWT + shop_id)
- [ ] Add JWT middleware to extract user context from token (inject into request scope)

**Acceptance Criteria:**
- JWT token contains `user_id`, `shop_id`, `exp` (15 min), valid signature
- Signup creates user + shop with correct defaults
- Login rejects wrong password
- Middleware rejects requests without valid token

**Files Modified/Created:**
- `auth/__init__.py` (new)
- `auth/jwt_handler.py` (new) — token generation/validation
- `auth/models.py` (new) — Pydantic schemas
- `auth/router.py` (new) — `/auth/signup`, `/auth/login`
- `db.py` — add User & Shop tables
- `api.py` — add auth middleware

---

### 0.2 — Create demo merchant account + fixture data (4 hours)
- [ ] Write script to create demo user: email=`demo@merchant.local`, password=`Demo123!`
- [ ] Generate demo shop: name=`"Demo Shop"`, shop_id from user
- [ ] Seed 5–10 sample messages (mixed English/Hindi scam text) for demo
- [ ] Seed 10 sample contacts (with trust scores, txn history)
- [ ] Run script at startup if demo user doesn't exist

**Acceptance Criteria:**
- Running `python api.py` creates demo user + shop on first run
- Login with demo credentials returns valid JWT
- GET `/api/dashboard/stats` shows demo data

**Files Created:**
- `fixtures/seed_demo_data.py` (new)

---

### 0.3 — Verify scam pipeline still works (4 hours)
- [ ] Test `/api/verify-text` with English + Hindi scam messages
- [ ] Test `/api/verify-image` with a test image (if Tesseract available)
- [ ] Test Telegram webhook (send message via bot, verify processing)
- [ ] Confirm no breaking changes from step 0.1 auth additions

**Acceptance Criteria:**
- `/api/verify-text` returns proper verdict for scam messages
- Telegram bot receives and processes messages
- No regression in classification accuracy

**Test Commands:**
```bash
curl -X POST http://localhost:8000/api/verify-text \
  -H "Content-Type: application/json" \
  -d '{"text": "Your SBI KYC is pending, click here now", "language": "english"}'

python telegram_bot.py  # Run in background, send test message via Telegram
```

---

### 0.4 — Checkpoint: Auth layer working (2 hours)
- [ ] Ensure all tests pass (unit + integration)
- [ ] Run demo script: signup → login → fetch dashboard stats
- [ ] Document required env vars (JWT_SECRET, TELEGRAM_TOKEN, etc.)

**Acceptance Criteria:**
- Full auth flow works end-to-end
- Dashboard returns shop-filtered stats (even if not yet in UI)
- All endpoints require valid JWT

---

## Phase 1: Multi-Tenant Isolation (72 Hours)

**Objective**: Two merchants can log in independently; each sees only their data

### 1.1 — Add tenant context middleware (6 hours)
- [ ] Create `middleware/tenant_context.py` — extracts `shop_id` from JWT, injects into request scope
- [ ] Update all 30+ existing endpoints to filter queries by `shop_id`
- [ ] Create helper function `get_shop_id_from_request()` to simplify endpoint logic
- [ ] Verify `/api/verify-text`, `/api/dashboard/stats`, `/api/search` all filter by `shop_id`

**Critical Changes to `db.py`:**
- All SELECT queries must now include `WHERE shop_id = ?`
- All INSERT queries must now include `shop_id` in VALUES
- All UPDATE queries must filter by `shop_id` (prevent cross-tenant updates)

**Pattern (apply to every query):**
```python
# BEFORE:
messages = conn.execute("SELECT * FROM messages ORDER BY received_at DESC LIMIT 10").fetchall()

# AFTER:
messages = conn.execute(
    "SELECT * FROM messages WHERE shop_id = ? ORDER BY received_at DESC LIMIT 10",
    (current_shop_id,)
).fetchall()
```

**Acceptance Criteria:**
- Merchant A logs in, sees only data with shop_id=A
- Merchant B logs in, sees only data with shop_id=B
- A cannot access B's messages even with direct API calls (endpoint filters correctly)

**Files Modified:**
- `db.py` — ALL SELECT/INSERT/UPDATE queries
- `api.py` — add tenant context middleware, pass shop_id to all db calls
- `middleware/tenant_context.py` (new)

---

### 1.2 — Add second demo merchant + isolation test (4 hours)
- [ ] Create second demo user: `demo2@merchant.local`, password `Demo123!`
- [ ] Each user gets their own `shop_id`
- [ ] Seed merchant 2 with different sample data
- [ ] Test: Merchant 1 logs in → sees only shop 1 data; Merchant 2 logs in → sees only shop 2 data

**Acceptance Criteria:**
- Both users can login simultaneously (separate JWT tokens)
- `/api/dashboard/stats` returns different stats for each user
- Cross-shop data access is impossible

---

### 1.3 — Webhook multi-tenancy (4 hours)
- [ ] Add `shop_id` parameter to Telegram webhook (either from context or as URL param: `/webhook/telegram?shop_id=...`)
- [ ] Verify WhatsApp/SMS webhooks also route to correct shop
- [ ] Update bot to include shop context in stored messages

**Acceptance Criteria:**
- Telegram message from shop 1 bot → stored with shop_id=1
- Telegram message from shop 2 bot → stored with shop_id=2
- Dashboard shows messages from correct shop only

**Files Modified:**
- `telegram_bot.py` — accept shop context
- `api.py` — webhook endpoints accept shop_id param

---

### 1.4 — Shop switching UI (2 hours)
- [ ] Add dropdown / radio buttons to HTML frontend to switch between merchant 1 & 2
- [ ] Store selected shop in localStorage
- [ ] On page reload, restore shop context and fetch correct data

**Files Modified:**
- `frontend/index.html` — add shop selector

---

### 1.5 — Checkpoint: Multi-tenant isolation working (2 hours)
- [ ] Ensure zero data leakage between shops
- [ ] Test cross-shop API attack (try to fetch shop B data as shop A) → should return 403 or empty
- [ ] Document tenant context architecture

---

## Phase 2: Feature Completion (Day 5)

**Objective**: Inventory, ledger, and exports scoped to shop; all core features working

### 2.1 — Ledger multi-tenancy (3 hours)
- [ ] Update `/api/ledger/create` to accept ledger_month; store with shop_id
- [ ] Update `/api/ledger/list` to return only ledgers for current shop
- [ ] Update dashboard stats to accept `?ledger=YYYY-MM` param; filter messages + transactions by ledger

**Pattern:**
```python
# GET /api/ledger/list (merchant sees only their ledgers)
# POST /api/ledger/create (creates ledger for merchant's shop)
# GET /api/dashboard/stats?ledger=2025-01 (sums transactions from Jan 2025 for shop)
```

**Acceptance Criteria:**
- Each merchant can create independent ledgers
- Ledger switching updates all dashboard charts
- Cross-shop ledger access blocked

---

### 2.2 — Inventory multi-tenancy (3 hours)
- [ ] Inventory CRUD already exists; add shop_id filter to all queries
- [ ] GET `/api/inventory` returns only current shop's items
- [ ] POST `/api/inventory/add` stores item with shop_id
- [ ] Inventory table already has columns; just need filter logic

**Acceptance Criteria:**
- Each merchant has independent inventory
- CSV import/export scoped to shop
- No cross-shop inventory visibility

---

### 2.3 — Contacts & Khata (credit tracking) (3 hours)
- [ ] Contacts table already has structure; add shop_id column (ALTER TABLE)
- [ ] GET `/api/contacts` returns only current shop's contacts
- [ ] GET `/api/contacts/{phone}/khata` shows outstanding dues for that contact
- [ ] POST `/api/contacts/{phone}/khata/settle` records payment

**Acceptance Criteria:**
- Each merchant tracks contacts independently
- Khata UI shows dues, payment history per contact
- No cross-shop contact visibility

---

### 2.4 — CSV import/export scoped to shop (3 hours)
- [ ] POST `/api/csv/import` — parse CSV, add shop_id to each row, store to DB
- [ ] GET `/api/csv/export?type=messages` — export only messages for current shop as CSV
- [ ] GET `/api/csv/export?type=inventory` — export only inventory for current shop
- [ ] Test with sample CSVs from both merchants

**Acceptance Criteria:**
- Import associates items with current shop
- Export includes only shop data
- Download filename includes shop name + date

---

### 2.5 — Checkpoint: All features multi-tenant (2 hours)
- [ ] Both merchants can manage inventory, ledgers, contacts independently
- [ ] Import/export works correctly for each merchant
- [ ] No data leakage in any feature

---

## Phase 3: Frontend & Polish (Day 6–7)

**Objective**: UI works on mobile, no console errors, clear demo script

### 3.1 — Responsive UI improvements (3 hours)
- [ ] Fix frontend HTML for mobile: flexbox layout, touch-friendly buttons
- [ ] Test on desktop (Chrome) + mobile (Chrome mobile emulator)
- [ ] Ensure forms, charts, tables are readable on small screens

**Priority fixes:**
- Dashboard chart sizing (should fit phone width)
- Form inputs should be large enough to tap
- Navigation menu collapses on mobile (hamburger menu if needed)

---

### 3.2 — Error handling & UX polish (2 hours)
- [ ] Ensure all errors return proper HTTP status (400, 403, 404, 500)
- [ ] Frontend catches 403 (Unauthorized) and 401 (Unauthenticated) → redirect to login
- [ ] Catch API failures, show toast/alert to user (not raw errors)
- [ ] Add loading spinners while fetching data

**Pattern:**
```javascript
fetch('/api/dashboard/stats')
  .then(r => {
    if (r.status === 401) window.location = '/login';
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  })
  .then(data => updateUI(data))
  .catch(err => showToast('Error: ' + err.message));
```

---

### 3.3 — Demo script & walkthrough (2 hours)
- [ ] Document exact steps to run demo:
  1. Start server: `python api.py`
  2. Open browser: `http://localhost:8000`
  3. Login as demo@merchant.local / Demo123!
  4. Send WhatsApp message: "Your SBI KYC is pending"
  5. Verify message appears in dashboard
  6. Confirm/reject message
  7. Check ledger updated
  8. Switch to merchant 2, verify isolation
- [ ] Record short video (~2 min) or write step-by-step walkthrough
- [ ] Include expected results for each step

**Files Created:**
- `DEMO_SCRIPT.md` (new)

---

### 3.4 — Checkpoint: UI production-ready (1 hour)
- [ ] No console errors in browser
- [ ] Responsive on mobile
- [ ] All UX flows smooth

---

## Phase 4: Deploy & Documentation (Day 7)

**Objective**: Ship to staging; document setup; hand off to stakeholders

### 4.1 — Docker setup (2 hours)
- [ ] Create `Dockerfile` for FastAPI app
- [ ] Create `docker-compose.yml` (FastAPI + SQLite volume)
- [ ] Test locally: `docker-compose up` → app starts on `:8000`

**Dockerfile (minimal):**
```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "api.py"]
```

**docker-compose.yml:**
```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./pramaan.db:/app/pramaan.db
    environment:
      - JWT_SECRET=your-secret-key-here
```

---

### 4.2 — Environment & secrets (1 hour)
- [ ] Create `.env.example` with all required vars:
  ```
  JWT_SECRET=...
  TELEGRAM_TOKEN=...
  GOOGLE_SAFE_BROWSING_API_KEY=...
  VIRUSTOTAL_API_KEY=...
  GROQ_API_KEY=...
  GEMINI_API_KEY=...
  ```
- [ ] Document which are optional (API keys) vs critical (JWT_SECRET)
- [ ] Add startup check: if JWT_SECRET not set, generate random one and warn

---

### 4.3 — Deployment to staging (1 hour)
- [ ] Deploy to AWS EC2, Heroku, or cloud hosting of choice
- [ ] Set environment variables in deployment platform
- [ ] Test: `curl https://staging-satark.app/api/dashboard/stats` with demo JWT
- [ ] Set up HTTPS (use Let's Encrypt or platform cert)

---

### 4.4 — Documentation (2 hours)
- [ ] **README.md** — What is this? How to run locally?
- [ ] **API.md** — List all endpoints, required auth, example payloads
- [ ] **DEPLOYMENT.md** — How to deploy to staging/prod
- [ ] **ARCHITECTURE.md** — JWT auth, tenant context middleware, shop isolation design
- [ ] **TROUBLESHOOTING.md** — Common issues + fixes

**README.md skeleton:**
```markdown
# Satark Setu Merchant OS

Multi-tenant scam-detection + merchant dashboard for small businesses.

## Quick Start

1. Install: `pip install -r requirements.txt`
2. Run: `python api.py`
3. Open: http://localhost:8000
4. Login: demo@merchant.local / Demo123!

## Features

- Multi-merchant shop isolation
- Scam detection (text, image, voice)
- Inventory + ledger management
- Telegram bot integration
- Multi-language support

## Architecture

- FastAPI backend (Python)
- SQLite database
- Static HTML + Vanilla JS frontend
- JWT authentication
```

---

### 4.5 — Checkpoint: Production ready (1 hour)
- [ ] Staging deployment working
- [ ] Demo walkthrough succeeds
- [ ] Docs are clear and complete

---

## Timeline & Resource Allocation

| Phase | Est. Hours | Dev Days | Dates (assuming Day 1 = Mon) | Status |
|-------|-----------|----------|------------------------------|--------|
| **0: Foundation** | 22h | 3d | Mon–Tue | ← **START HERE** |
| **1: Multi-Tenant** | 21h | 3d | Wed–Thu | |
| **2: Features** | 20h | 2.5d | Fri | |
| **3: Polish** | 10h | 1.5d | Sat morning | |
| **4: Deploy** | 6h | 1d | Sat afternoon | |
| **Total** | **79 hours** | **~10 dev days** | **Mon–Sat** | ✅ |

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Staging / Production Environment (AWS / Heroku / DigitalOcean)
│
│  ┌───────────────────────────────────────────────────────┐
│  │ FastAPI App (Docker container)                        │
│  │  - Port 8000                                          │
│  │  - SQLite → (post-hackathon: migrate to PostgreSQL)  │
│  │  - JWT auth middleware                               │
│  │  - Tenant context extraction                         │
│  └───────────────────────────────────────────────────────┘
│
│  ┌───────────────────────────────────────────────────────┐
│  │ Reverse Proxy (Nginx / ELB)                           │
│  │  - HTTPS termination                                  │
│  │  - Load balancing (if multiple replicas)             │
│  │  - Static file caching                               │
│  └───────────────────────────────────────────────────────┘
│
│  ┌───────────────────────────────────────────────────────┐
│  │ SQLite Database (persistent volume)                   │
│  │  - pramaan.db (auto-backed up daily)                 │
│  │  - NOTE: Post-hackathon, migrate to PostgreSQL       │
│  └───────────────────────────────────────────────────────┘
│
│  ┌───────────────────────────────────────────────────────┐
│  │ Environment & Secrets (AWS Secrets Manager / Heroku)  │
│  │  - JWT_SECRET (rotated quarterly)                    │
│  │  - API keys (Telegram, Google, Groq, Gemini)         │
│  └───────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────┘

External Services (Webhook ingestion):
  ├─ Telegram Bot → POST /webhook/telegram?shop_id=...
  ├─ WhatsApp Cloud API → POST /webhook/whatsapp?shop_id=...
  └─ Android SMS Gateway → POST /webhook/sms?shop_id=...
```

---

## Success Criteria Checklist

### End of Phase 0 (48h) ✓
- [ ] User can signup with email + password
- [ ] User can login and receive JWT token
- [ ] Demo merchant account exists (demo@merchant.local)
- [ ] `/api/dashboard/stats` returns scoped data
- [ ] Scam pipeline still works (verify-text, Telegram bot)

### End of Phase 1 (72h) ✓
- [ ] Two independent merchants can login
- [ ] Each merchant sees only their data
- [ ] Cross-shop data access is impossible
- [ ] All 30+ endpoints enforce shop isolation

### End of Phase 2 (Day 5) ✓
- [ ] Ledger + inventory scoped to shop
- [ ] Contacts + Khata tracking works
- [ ] CSV import/export scoped to shop
- [ ] Both merchants can use all features independently

### End of Phase 3 (Day 7) ✓
- [ ] Frontend responsive on mobile
- [ ] No console errors
- [ ] Demo script works end-to-end
- [ ] Error handling is user-friendly

### End of Phase 4 (Day 7) ✓
- [ ] Deployed to staging
- [ ] HTTPS working
- [ ] Documentation complete
- [ ] Ready for demo to stakeholders

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| JWT secret key compromise | Critical | Rotate weekly; use strong random key (use `secrets.token_urlsafe(32)`) |
| Shop isolation SQL injection | Critical | Use parameterized queries everywhere; never string-interpolate shop_id |
| Tenant context not extracted | High | Add middleware test: verify `request.scope["shop_id"]` is set before reaching endpoint |
| Telegram webhook loses messages | Medium | Add queue (task list in comments if it fails); retry on 5xx |
| Database file corruption | High | Back up SQLite daily; provide rollback script |
| Performance degrades | Medium | Profile queries early; add indexes on (shop_id, received_at) if needed |

---

## Post-Hackathon Roadmap (Skip for Now)

Once the hackathon demo is complete and approved:

1. **PostgreSQL migration** (1 week) — Move data from SQLite; set up connection pooling
2. **Next.js frontend rewrite** (2 weeks) — Modern UI, real-time updates, better mobile UX
3. **Admin console** (1 week) — Shop management, user management, billing dashboard
4. **Advanced features** (2 weeks) — Role-based access (staff vs owner), AI chat improvements, advanced analytics
5. **Testing suite** (1 week) — Unit + integration + E2E tests
6. **Observability** (1 week) — Logging, monitoring, error tracking (Sentry)

---

## Demo Script (Exact Steps)

### Setup
```bash
# Terminal 1: Start the server
cd /path/to/satark_setu
python api.py
# Expected: "Uvicorn running on 0.0.0.0:8000"
```

### Demo Steps (in browser, ~5 min)
1. **Login as Merchant 1**
   - Open http://localhost:8000
   - Email: `demo@merchant.local`, Password: `Demo123!`
   - Expected: Dashboard appears with sample data

2. **Verify a scam message**
   - Go to "Verify" tab
   - Paste: `"Your SBI KYC is pending, update immediately to avoid account closure"`
   - Click "Verify"
   - Expected: System flags it as a scam (fake_kyc typology, high risk)

3. **Confirm the message** (add to ledger)
   - Click "Confirm" on the scam verdict
   - Amount: `₹0` (no transaction amount in the message)
   - Contact: "SBI Phishing Attempt"
   - Ledger: "January 2025"
   - Click "Confirm to Ledger"
   - Expected: Message added to ledger, dashboard stats updated

4. **Check dashboard**
   - Dashboard shows new confirmed scam attempt
   - Ledger shows the transaction
   - Contact directory now includes "SBI Phishing Attempt"

5. **Switch to Merchant 2**
   - Click "Switch Merchant" dropdown (or logout/login as demo2@merchant.local)
   - Email: `demo2@merchant.local`, Password: `Demo123!`
   - Expected: Dashboard is completely empty (different shop_id, no shared data)

6. **Verify isolation**
   - In Merchant 2, go to Contacts
   - "SBI Phishing Attempt" should NOT appear (it's in Merchant 1's data)
   - Go to Ledger
   - January 2025 is empty (no confirmed messages for Merchant 2)
   - Expected: Complete isolation confirmed

### Expected Timing
- Setup: 2 min
- Demo steps: 5 min
- Q&A: 3 min
- **Total: ~10 minutes**

---

## Questions Before Starting?

- **Database**: Should we stick with SQLite for the hackathon, or do you want PostgreSQL now? (SQLite is faster to ship)
- **Frontend**: Enhance the existing HTML + Vanilla JS, or build a minimal React app? (HTML is faster)
- **Deployment**: Do you have a staging server/domain ready, or should we deploy to a free tier (Heroku, Replit)?
- **Team**: Will the same developer handle both backend + frontend, or separate teams? (This plan assumes one dev)

---

## Final Notes

This hackathon sprint:
- ✅ **Reuses 90% of existing code** — no rewrites, only additions
- ✅ **Ships MVP in 10 dev days** — aggressive but achievable
- ✅ **Demonstrates core value** — multi-tenancy + scam detection working together
- ✅ **Production-ready enough for demo** — not production-grade (that's post-hackathon)
- ✅ **Clear migration path** — documented what to do next

**You've got this.** Start with Phase 0 today. In 48 hours, you should have a working auth layer + demo merchant account. By Saturday, you should be demoing a fully isolated multi-tenant system.

Good luck! 🚀

