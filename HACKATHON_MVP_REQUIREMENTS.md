# Satark Setu Merchant MVP — Requirements Document

**Timeline**: 7 days (Phase 0–4 from HACKATHON_SPRINT.md)  
**Scope**: Multi-tenant auth + multi-merchant isolation + scam detection  
**Language**: Python (FastAPI), HTML/Vanilla JS  
**Database**: SQLite (local) → PostgreSQL (post-hackathon)

---

## Glossary

- **Shop**: Merchant business entity; one Shop = one independent merchant account
- **User**: Individual person logged in; each User belongs to one Shop
- **JWT Token**: Stateless bearer token containing user_id, shop_id, expiry; used to authenticate all API requests
- **Tenant Context**: Request scope containing shop_id extracted from JWT; injected into middleware; used to filter all queries
- **Ledger**: Monthly bookkeeping period (e.g., "2025-01"); transactions scoped to specific ledger + shop
- **Scam Detection Pipeline**: Full chain of message processing (OCR/Whisper → classification → risk scoring → storage)
- **Merchant Dashboard**: Web UI showing stats, ledger, inventory, contacts, scoped to current user's shop

---

## Feature Matrix (MVP Scope)

| Feature | Status | Notes |
|---------|--------|-------|
| **User Auth** | ✅ NEW | Signup/login with JWT; email+password required |
| **Multi-Tenancy** | ✅ NEW | Each merchant completely isolated; cross-shop data access impossible |
| **Scam Detection Pipeline** | ✅ EXISTING | Reuse FastAPI endpoints; add shop context to stored messages |
| **Dashboard Stats** | ✅ EXISTING | Query existing; add shop_id filter; refactor existing stats endpoint |
| **Ledger Management** | ✅ EXISTING | Existing monthly ledgers; add shop association; UI to switch ledgers |
| **Inventory** | ✅ EXISTING | Existing CRUD; add shop_id filter; no schema changes needed |
| **Contacts & Khata** | ✅ EXISTING | Existing contact tracking + dues; add shop_id filter |
| **CSV Import/Export** | ✅ EXISTING | Existing endpoints; add shop_id association |
| **Telegram Bot** | ✅ EXISTING | Existing bot; route messages to correct shop via webhook param |
| **Mobile Responsiveness** | ✅ NEW | Enhance existing HTML frontend with mobile CSS |
| **Admin Console** | ❌ SKIP | Not needed for MVP; post-hackathon |
| **PostgreSQL** | ❌ SKIP | Stay on SQLite for hackathon; migrate after |
| **Next.js Rewrite** | ❌ SKIP | Too slow; enhance existing HTML + Vanilla JS |
| **Role-Based Access** | ⚠️ PARTIAL | Staff/owner roles (basic); full RBAC post-hackathon |

---

## User Flows

### Flow 1: Signup & First Login

**Actors**: New merchant (e.g., Rohan)

1. User opens http://localhost:8000 (or production URL)
2. Clicks "Sign Up" button → signup form appears
3. Enters email (`rohan@merchant.local`), password (`SecurePass123!`), shop name (`Rohan's General Store`)
4. System validates: email unique, password >8 chars, shop name not empty
5. Creates User + Shop record in SQLite
6. Returns JWT token (valid 15 min); redirects to dashboard
7. **User is now authenticated and isolated from all other merchants**

**Acceptance Criteria**:
- Email validation (no duplicates)
- Password stored as bcrypt hash (not plaintext)
- JWT token includes user_id, shop_id, exp
- Shop created with shop_id linked to user
- Dashboard accessible immediately after signup

---

### Flow 2: Submit Scam Message & Confirm to Ledger

**Actors**: Authenticated merchant viewing dashboard

1. User logs in with email/password
2. Dashboard loads; JWT token verified by middleware; shop_id extracted
3. User navigates to "Verify" tab
4. Pastes/uploads scam message (text/image/voice)
5. System runs through scam detection pipeline:
   - OCR/Whisper extraction (if image/voice)
   - Classification (legitimate/suspicious/scam)
   - Risk scoring (0–100)
   - Extraction of transaction details (amount, counterparty, etc.)
6. Result displayed: "🔴 SCAM — Risk 95/100 — Fake KYC Update"
7. User clicks "Confirm to Ledger"
8. System stores message with shop_id + current ledger_month
9. Dashboard stats updated (scam count incremented)
10. Ledger shows new confirmed transaction
11. **Message is now in user's ledger; NOT visible to other merchants**

**Acceptance Criteria**:
- Messages stored with shop_id column
- All queries filter by shop_id (no cross-shop message leakage)
- Ledger filtering works (shows only messages in selected ledger_month)
- Dashboard stats updated in real-time
- Rejected messages also filtered by shop_id (draft status)

---

### Flow 3: Switch Merchants & Verify Isolation

**Actors**: Two independent merchants (Merchant A & Merchant B)

1. **Merchant A** logs in: email `demo@merchant.local`, password `Demo123!`
   - JWT returned with shop_id=1
   - Middleware extracts shop_id=1
   - All queries filter by shop_id=1
   - Dashboard shows Merchant A's data only

2. **Merchant A** confirms a message → appears in Merchant A's ledger

3. **Merchant A** logs out (or JWT expires)

4. **Merchant B** logs in: email `demo2@merchant.local`, password `Demo123!`
   - JWT returned with shop_id=2
   - Middleware extracts shop_id=2
   - Dashboard is EMPTY (no messages for shop_id=2)
   - Contacts list is EMPTY (no contacts for shop_id=2)
   - Ledger shows no transactions (no entries for shop_id=2)

5. **Merchant B** submits a message
   - Stored with shop_id=2
   - Not visible to Merchant A
   - Dashboard stats for B updated only

6. **Merchant A** logs back in
   - Sees original message from step 2
   - Does NOT see Merchant B's message
   - **Complete isolation confirmed**

**Acceptance Criteria**:
- JWT token contains shop_id
- Middleware injects shop_id into request scope
- ALL database queries filter by WHERE shop_id = ?
- API endpoint validation: attempt cross-shop access (e.g., try to access shop_id=2's messages as user with shop_id=1) returns 403 or empty results
- No shared data between any two merchants

---

## Data Security & Shop Isolation

### Principles

1. **All queries must filter by shop_id**
   - Pattern: `SELECT * FROM messages WHERE shop_id = :shop_id AND ...`
   - No exceptions for "admin" views (MVP has no admin)
   - Missing shop_id filter = critical bug

2. **Shop context always from JWT**
   - Never trust `shop_id` from request body/params
   - Always extract from JWT token in middleware
   - Middleware failure = 401 Unauthorized, never continue

3. **Shop isolation is not optional**
   - Every table (messages, contacts, inventory, ledgers, etc.) must have shop_id column
   - Every INSERT must include shop_id
   - Every SELECT/UPDATE/DELETE must filter by shop_id
   - Code review must verify 100% compliance before merge

4. **Webhook safety**
   - Telegram webhook must accept shop_id parameter: `/webhook/telegram?shop_id=<ID>`
   - Message routed to correct shop based on parameter
   - Signature validation prevents spoofing (future enhancement)

---

## Database Schema (SQLite)

### New Tables

**users**
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id INTEGER NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY (shop_id) REFERENCES shops(id)
);
```

**shops**
```sql
CREATE TABLE shops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

### Modified Tables

All existing tables (messages, contacts, inventory, ledgers, etc.) must have shop_id column added:

```sql
ALTER TABLE messages ADD COLUMN shop_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE messages ADD FOREIGN KEY (shop_id) REFERENCES shops(id);

-- Apply same pattern to:
-- - contacts
-- - community_scam_reports
-- - ledgers
-- - settings (per-shop settings)
-- - inventory
-- - daily_snapshots
```

**Index for performance**:
```sql
CREATE INDEX idx_messages_shop ON messages(shop_id, received_at DESC);
CREATE INDEX idx_contacts_shop ON contacts(shop_id, trust_score DESC);
-- (apply to all tables for query performance)
```

---

## API Surface (MVP Endpoints)

### New Auth Endpoints

| Method | Path | Auth? | Shop Filter | Purpose |
|--------|------|-------|-------------|---------|
| POST | `/auth/signup` | ❌ | N/A | Create user + shop; return JWT |
| POST | `/auth/login` | ❌ | N/A | Validate email/password; return JWT |
| POST | `/auth/refresh` | ✅ JWT | N/A | Extend session (return new JWT) |
| POST | `/auth/logout` | ✅ JWT | N/A | Invalidate token (optional; JWT stateless) |

### Existing Verification Endpoints (Unchanged)

| Method | Path | Auth? | Shop Filter | Purpose |
|--------|------|-------|-------------|---------|
| POST | `/api/verify-text` | ✅ | ✅ shop_id | Classify text → verdict |
| POST | `/api/verify-image` | ✅ | ✅ shop_id | OCR + classify → verdict |
| POST | `/api/verify-voice` | ✅ | ✅ shop_id | Whisper + classify → verdict |
| GET | `/api/search` | ✅ | N/A (global) | Search scheme DB (no shop filter; schemes are global) |

### Existing Dashboard Endpoints (Add Shop Filter)

| Method | Path | Auth? | Shop Filter | Purpose |
|--------|------|-------|-------------|---------|
| GET | `/api/dashboard/stats` | ✅ | ✅ shop_id | P&L, confirmed txns, scam count |
| GET | `/api/dashboard/messages` | ✅ | ✅ shop_id | Recent messages for shop |
| GET | `/api/dashboard/contacts` | ✅ | ✅ shop_id | Contact directory for shop |
| POST | `/api/dashboard/confirm/{id}` | ✅ | ✅ shop_id (validate message belongs to shop) | Confirm message → ledger |
| POST | `/api/dashboard/reject/{id}` | ✅ | ✅ shop_id | Reject message (keep in DB, mark rejected) |
| GET | `/api/dashboard/export` | ✅ | ✅ shop_id | Export confirmed txns as JSON |

### Existing Ledger Endpoints (Add Shop Association)

| Method | Path | Auth? | Shop Filter | Purpose |
|--------|------|-------|-------------|---------|
| GET | `/api/ledgers` | ✅ | ✅ shop_id | List ledgers for shop |
| POST | `/api/ledgers/create` | ✅ | ✅ shop_id | Create new ledger for shop |
| GET | `/api/ledgers/check` | ✅ | ✅ shop_id | Check if ledger exists for month |

### Existing Inventory Endpoints (Add Shop Filter)

| Method | Path | Auth? | Shop Filter | Purpose |
|--------|------|-------|-------------|---------|
| GET | `/api/inventory` | ✅ | ✅ shop_id | List inventory for shop |
| POST | `/api/inventory` | ✅ | ✅ shop_id | Add/update inventory item |
| DELETE | `/api/inventory/{id}` | ✅ | ✅ shop_id | Delete inventory item |
| POST | `/api/inventory/manual-cash` | ✅ | ✅ shop_id | Record cash txn + update stock |

### Webhook Endpoints (Multi-Tenant)

| Method | Path | Auth? | Parameter | Purpose |
|--------|------|-------|-----------|---------|
| POST | `/api/webhook/telegram?shop_id=<ID>` | ⚠️ Signature | shop_id (URL param) | Telegram bot message ingestion |
| POST | `/api/webhook/whatsapp?shop_id=<ID>` | ⚠️ Signature | shop_id (URL param) | WhatsApp message ingestion |
| POST | `/api/webhook/sms?shop_id=<ID>` | ⚠️ Signature | shop_id (URL param) | SMS message ingestion |

**Note**: Webhook validation by signature (shared secret per shop) is post-hackathon; for MVP, trust shop_id parameter from trusted channels (Telegram/WhatsApp Cloud API, Android SMS app).

---

## Acceptance Criteria (MVP)

### Authentication (Must-Have)

1. **User Signup**
   - [ ] Email + password accepted; shop_name provided
   - [ ] Email must be unique; password must be >= 8 chars
   - [ ] User + Shop created; User linked to Shop
   - [ ] JWT token returned (valid for 15 min)
   - [ ] Redirect to dashboard on success
   - [ ] Error handling: duplicate email → 400, weak password → 400

2. **User Login**
   - [ ] Email + password validated
   - [ ] JWT token returned (user_id, shop_id, exp)
   - [ ] Token valid for 15 minutes
   - [ ] Incorrect password → 401
   - [ ] Non-existent email → 404 or 401 (security: don't leak email existence)

3. **JWT Middleware**
   - [ ] All protected endpoints require valid JWT
   - [ ] Missing token → 401
   - [ ] Expired token → 401
   - [ ] Invalid signature → 401
   - [ ] shop_id extracted from token and injected into request scope

### Multi-Tenancy (Must-Have)

4. **Shop Isolation — Messages**
   - [ ] Message stored with shop_id
   - [ ] `/api/dashboard/messages` returns only messages for user's shop
   - [ ] Manual test: User A's messages invisible to User B
   - [ ] API endpoint rejects attempts to access other shop's messages

5. **Shop Isolation — Contacts**
   - [ ] Contact (counterparty phone) associated with shop_id
   - [ ] `/api/dashboard/contacts` returns only contacts for user's shop
   - [ ] Trust score calculated per-shop (not cross-shop)
   - [ ] Manual test: User A's contacts invisible to User B

6. **Shop Isolation — Inventory**
   - [ ] Inventory item associated with shop_id
   - [ ] `/api/inventory` returns only items for user's shop
   - [ ] Add/delete operations scoped to shop
   - [ ] Manual test: User A's items invisible to User B

7. **Shop Isolation — Ledgers**
   - [ ] Ledger (month) associated with shop_id
   - [ ] `/api/ledgers` returns only ledgers for user's shop
   - [ ] Create ledger operation creates ledger for current shop only
   - [ ] Manual test: User A's ledgers invisible to User B

8. **No Cross-Shop Data Leakage**
   - [ ] Authenticated endpoint accessed with valid JWT returns only user's shop data
   - [ ] Even if shop_id provided in request body, system uses shop_id from JWT (not request)
   - [ ] Attempted cross-shop access (e.g., `/api/dashboard/messages?shop_id=999`) returns 403 or empty
   - [ ] ALL queries verified to include WHERE shop_id = ? filter

### Scam Detection Pipeline (Must-Have)

9. **Classification Accuracy**
   - [ ] Scam messages flagged correctly (existing pipeline; no changes)
   - [ ] Legitimate messages classified correctly
   - [ ] Risk score ranges 0–100
   - [ ] Explanation text provided for all verdicts

10. **Message Storage with Shop Context**
    - [ ] Verified message stored with shop_id
    - [ ] Message linked to correct user's shop
    - [ ] Ledger status set correctly (draft/confirmed/rejected)
    - [ ] Transaction details extracted (amount, counterparty, direction, etc.)

### Dashboard (Must-Have)

11. **Stats Display**
    - [ ] `/api/dashboard/stats` returns correct totals for shop
    - [ ] Total inflow (sum of confirmed inflows for shop)
    - [ ] Total outflow (sum of confirmed outflows for shop)
    - [ ] Net P&L calculated correctly
    - [ ] Scam count shows scams for shop only
    - [ ] Confirmed txn count matches ledger entries

12. **Ledger Filtering**
    - [ ] User can select active ledger month (dropdown)
    - [ ] Dashboard stats update when ledger switched
    - [ ] Stats reflect only transactions in selected ledger + shop
    - [ ] Charts (cashflow, category breakdown) update accordingly

13. **Message Confirmation Workflow**
    - [ ] User sees unconfirmed (draft) messages
    - [ ] User clicks "Confirm" on a message
    - [ ] Status changes from draft → confirmed
    - [ ] Ledger stats updated immediately
    - [ ] Message now visible in "Confirmed Transactions" list

### Frontend UX (Must-Have)

14. **Mobile Responsiveness**
    - [ ] Dashboard accessible on mobile (< 768px width)
    - [ ] Charts, tables, forms readable on small screens
    - [ ] Buttons touch-friendly (>44px height)
    - [ ] No horizontal scrolling required

15. **Error Handling**
    - [ ] API errors (4xx, 5xx) shown to user (toast/alert)
    - [ ] Login errors clear and actionable ("Wrong password", "User not found")
    - [ ] Network errors handled gracefully (retry option)
    - [ ] No raw error messages in UI (no stack traces)

16. **Session Management**
    - [ ] JWT stored in localStorage (or sessionStorage)
    - [ ] Page reload restores user session (if token still valid)
    - [ ] Logout clears token and redirects to login
    - [ ] Expired token redirects to login with message

### Demo Merchant Accounts (Must-Have)

17. **Demo Data**
    - [ ] Two demo users created at startup:
      - Merchant 1: `demo@merchant.local` / `Demo123!`
      - Merchant 2: `demo2@merchant.local` / `Demo123!`
    - [ ] Each demo user has own shop
    - [ ] Demo data (5–10 messages, contacts) seeded per merchant
    - [ ] Dashboard shows data only for logged-in merchant

### CSV Import/Export (Nice-to-Have)

18. **CSV Export**
    - [ ] GET `/api/dashboard/export` returns confirmed txns for shop
    - [ ] File downloadable as JSON/CSV with shop name + date in filename
    - [ ] Export includes: amount, date, counterparty, direction, status

19. **CSV Import**
    - [ ] POST `/api/import/csv` accepts CSV (PhonePe/GPay/Paytm format)
    - [ ] Rows parsed and added to shop's ledger
    - [ ] Duplicate detection prevents re-imports
    - [ ] Error report shows rows that failed

### Telegram Bot (Nice-to-Have)

20. **Multi-Shop Telegram Integration**
    - [ ] Each merchant's shop can have own Telegram bot token
    - [ ] Webhook endpoint accepts `shop_id` parameter
    - [ ] Messages routed to correct merchant's shop
    - [ ] Bot replies visible only to merchant's shop

---

## Testing Strategy

### Unit Tests
- Auth module: token generation, validation, expiry
- Shop filtering: verify WHERE clauses added to queries
- Password hashing: bcrypt operations

### Integration Tests
- Full auth flow: signup → login → JWT validation
- Multi-merchant isolation: User A cannot access User B's data
- Message storage: verified message stored with correct shop_id
- Ledger filtering: dashboard stats correct per ledger + shop

### Manual Tests (Demo Script)
- Merchant 1 login → submit scam message → confirm to ledger → verify in dashboard
- Merchant 2 login → verify Merchant 1's data not visible
- Cross-shop access attempt → 403 or empty (no data leakage)

---

## Deployment

### Environment Variables
```
JWT_SECRET=<random-secret-key>  # Generate with: secrets.token_urlsafe(32)
TELEGRAM_BOT_TOKEN=<your-bot-token>
GOOGLE_SAFE_BROWSING_API_KEY=<key>
VIRUSTOTAL_API_KEY=<key>
GROQ_API_KEY=<key>
GEMINI_API_KEY=<key>
```

### Local Running
```bash
python api.py
# Open http://localhost:8000
# Login: demo@merchant.local / Demo123!
```

### Docker
```bash
docker-compose up
# App on http://localhost:8000
```

---

## Out of Scope (Post-Hackathon)

- PostgreSQL migration
- Next.js frontend rewrite
- Admin console
- Role-based access control (RBAC beyond basic staff/owner)
- API versioning (`/api/v2/`)
- Real-time WebSocket updates
- Advanced analytics & AI chat
- Comprehensive test suite
- Observability (logging, monitoring, APM)
