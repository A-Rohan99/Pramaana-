# Satark Setu Merchant OS — Implementation Roadmap

**Last Updated**: 2025-01-15  
**Target**: Transform scam-detection web app → B2B merchant OS with multi-user, multi-shop support  
**Effort**: ~12-16 weeks (1 developer) across 10 phases

---

## 📋 Executive Summary

Satark Setu currently is a **single-user, single-tenant web app** with no authentication, persistent user state, or shop isolation. The roadmap below breaks the transformation into **10 sequential and parallel phases**, each with discrete, testable tasks.

### Current State
- ✅ FastAPI backend (30+ endpoints), SQLite DB (8 tables), full scam detection pipeline
- ✅ Telegram bot, WhatsApp/SMS webhooks, Whisper transcription, IndicTrans2 offline translation
- ✅ Gemini 2.5 Flash Lite AI chat, OCR pipeline
- ❌ NO authentication, NO multiuser, NO shop/merchant isolation
- ❌ Frontend is static HTML (needs Next.js rewrite)
- ❌ NO PostgreSQL (SQLite only), NO ORM layer
- ❌ NO real-time sync, NO API versioning, NO request logging

### Target State
- ✅ Multi-tenant B2B OS for merchants
- ✅ OAuth2 / JWT authentication
- ✅ Shop-isolated inventory, ledger, contacts, dashboards
- ✅ Next.js frontend with real-time updates
- ✅ PostgreSQL + SQLAlchemy ORM
- ✅ Admin console, shop management, role-based access control
- ✅ Webhook audit logs, rate limiting per shop, API versioning

---

## 🗺️ Phase Overview & Sequencing

```
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: Auth & Multi-User Foundation (2 weeks)             │
│  → JWT auth, user roles, session management                  │
│  Tasks: 1.1–1.6 (sequential dependency on JWT module)        │
└────────────────────────────────────────────────────────────┬─┘
                                                               │
                          ┌────────────────────────────────────┴───────────┐
                          │ PHASE 2: DB Migration & ORM (2.5 weeks)       │
                          │  ┌─→ Task 2.1 (SQLite → PostgreSQL)           │
                          │  ├─→ Task 2.2 (SQLAlchemy models)             │
                          │  ├─→ Task 2.3 (Data migration script)         │
                          │  └─→ Task 2.4 (ORM integration)               │
                          └────────────────┬──────────────────────────────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │ PHASE 3: Frontend    │ PHASE 4: API Layer   │
                    │ Rewrite (2 weeks)    │ & Isolation (1.5 wks)│
                    │ 3.1–3.6 (parallel)   │ 4.1–4.5 (parallel)   │
                    └──────────┬───────────┼──────────┬───────────┘
                               │           │          │
                    ┌──────────┴───────────┴──────────┴──────────┐
                    │ PHASE 5: Dashboard & Ledger (1.5 weeks)   │
                    │ 5.1–5.4 (depends on 3 & 4)                │
                    └──────────┬─────────────────────────────────┘
                               │
                    ┌──────────┴───────────────────────────────┐
                    │ PHASE 6: Features & Polish (1 week)      │
                    │ 6.1–6.5 (final touches, optimization)    │
                    └──────────┬───────────────────────────────┘
                               │
                    ┌──────────┴───────────────────────────────┐
                    │ PHASE 7: Admin Console (1.5 weeks)       │
                    │ 7.1–7.4 (optional: shop mgmt, billing)   │
                    └──────────┬───────────────────────────────┘
                               │
                    ┌──────────┴───────────────────────────────┐
                    │ PHASE 8: Observability (1 week)          │
                    │ 8.1–8.4 (logging, monitoring, metrics)   │
                    └──────────┬───────────────────────────────┘
                               │
                    ┌──────────┴───────────────────────────────┐
                    │ PHASE 9: Testing & QA (1.5 weeks)        │
                    │ 9.1–9.4 (unit, integration, e2e tests)   │
                    └──────────┬───────────────────────────────┘
                               │
                    ┌──────────┴───────────────────────────────┐
                    │ PHASE 10: Deployment & Docs (1 week)     │
                    │ 10.1–10.4 (deploy, docs, handoff)        │
                    └────────────────────────────────────────┘
```

---

## 📊 Task Breakdown by Phase


### PHASE 1: Authentication & Multi-User Foundation (2 weeks, 10 dev days)

**Objective**: Establish secure user authentication, session management, and role-based access control (RBAC).

**Prerequisites**: None (Phase 1 is initial)

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 1.1 | **Auth module setup** — Create `auth/` package with JWT token generation/validation, password hashing (bcrypt) | 1 | — | JWT tokens encode user_id, shop_id, roles; can be validated and decoded |
| 1.2 | **User model & database** — Create User table (email, password_hash, name, is_active, created_at); user CRUD ops | 1 | 1.1 | User signup/login endpoints tested, password verified correctly |
| 1.3 | **OAuth2 flow** — Implement `OAuth2PasswordBearer` in FastAPI, add `/auth/login` POST endpoint, return access token | 0.5 | 1.1, 1.2 | Login endpoint returns JWT token; token includes exp, user_id, shop_id |
| 1.4 | **Session & middleware** — Add middleware to check JWT on all protected routes, extract user context (user_id, shop_id) | 0.5 | 1.3 | Middleware rejects requests without valid token; extracts user context correctly |
| 1.5 | **Role-based access control (RBAC)** — Define role enum (admin, shop_owner, staff, analyst), decorator for role checks | 1 | 1.4 | Decorator enforces roles; staff cannot access admin routes |
| 1.6 | **Password reset & token refresh** — `/auth/refresh` endpoint, password reset request/confirm flow | 1 | 1.2, 1.3 | Refresh token extends session; password reset email/link flow works |
| **Checkpoint** | All auth tests passing (unit + integration) | 0.5 | 1.1–1.6 | Auth module is production-ready, no security gaps |

**Effort Total**: ~5 dev days

---

### PHASE 2: Database Migration & ORM Layer (2.5 weeks, 12–15 dev days)

**Objective**: Migrate from SQLite to PostgreSQL; establish SQLAlchemy ORM layer; preserve all data.

**Prerequisites**: Phase 1 (optional but recommended for field-level access control in ORM)

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 2.1 | **PostgreSQL setup** — Docker compose file or cloud DB provisioning; run migrations (create tables, indexes) | 1 | — | PostgreSQL instance running locally or remote; can connect via psycopg2 |
| 2.2 | **SQLAlchemy models** — Rewrite all 8 SQLite tables as SQLAlchemy ORM models (Message, Contact, Ledger, etc.) | 2 | 2.1 | All models have correct fields, relationships, constraints; schema matches original |
| 2.3 | **ORM queries** — Rewrite all `conn.execute()` calls in `db.py` as SQLAlchemy queries; test query correctness | 2 | 2.2 | All CRUD ops work; performance acceptable (< 200ms for dashboard queries) |
| 2.4 | **Data migration script** — Export SQLite data; transform & load into PostgreSQL; validate counts, integrity | 1.5 | 2.1, 2.2, 2.3 | All data preserved; checksums match; no orphaned foreign keys |
| 2.5 | **Alembic migrations** — Set up schema versioning; create baseline migration; test rollback/forward | 1 | 2.2, 2.3 | Alembic can generate new migrations; `alembic upgrade/downgrade` works |
| 2.6 | **Connection pooling & performance** — SQLAlchemy engine with pool config, test concurrent access | 0.5 | 2.1, 2.2 | Connection pool prevents exhaustion; queries complete < 500ms under load |
| **Checkpoint** | All DB tests passing; dashboard queries still fast | 1 | 2.1–2.6 | ORM is fully integrated; SQLite no longer used |

**Effort Total**: ~9 dev days

---

### PHASE 3: Frontend Rewrite (Next.js) (2 weeks, 10 dev days)

**Objective**: Replace static HTML frontend with modern Next.js SPA; implement responsive UI for multi-user access.

**Prerequisites**: Phase 1 (auth), Phase 2 (DB ready)

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 3.1 | **Next.js project setup** — Create Next.js app (TypeScript, Tailwind CSS, ESLint); import UI library (shadcn/ui or MUI) | 1 | 1.1–1.6 | Next.js app runs on localhost:3000; can connect to FastAPI on 8000 |
| 3.2 | **Auth UI & flows** — Login/signup pages, JWT token storage (localStorage or cookies), protected routes (ProtectedRoute wrapper) | 1.5 | 1.3, 3.1 | Login page works; redirects to dashboard on success; logout clears token |
| 3.3 | **Dashboard & stats** — Home page with P&L summary, charts (React Chart.js or Recharts), real-time stats refresh | 1.5 | 2.1–2.6, 3.1 | Dashboard fetches stats from `/api/dashboard/stats` and renders correctly |
| 3.4 | **Message verification & ledger** — Input forms (text/image/voice), verification results card, confirm/reject buttons | 1.5 | 3.1, 3.2 | File upload works; verification endpoint returns results; UI renders verdicts |
| 3.5 | **Contacts & scheme search** — Contact directory table, scheme search bar, display scheme details in modal | 1 | 3.1 | Contacts load and display; search returns scheme results; modal shows full details |
| 3.6 | **Settings & inventory** — Settings page (shop name, auto-sync toggle), inventory table (add/edit/delete items) | 1 | 3.1, 3.2 | Settings persist; inventory CRUD works; UI updates on changes |
| **Checkpoint** | All UI pages render; all forms submit correctly | 0.5 | 3.1–3.6 | Frontend fully functional, no console errors |

**Effort Total**: ~7 dev days

---

### PHASE 4: API Layer & Shop Isolation (1.5 weeks, 7–8 dev days)

**Objective**: Refactor API endpoints to enforce shop isolation; add middleware for tenant context.

**Prerequisites**: Phase 1 (auth), Phase 2 (DB ready)

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 4.1 | **Tenant context middleware** — Middleware extracts shop_id from JWT; adds to request scope; all queries filtered by shop_id | 1 | 1.4, 2.2 | All API endpoints receive tenant context; queries correctly filter by shop_id |
| 4.2 | **Endpoint refactoring** — Update 30+ endpoints to respect shop isolation; e.g., `/api/messages` → `WHERE shop_id = current_shop` | 2.5 | 4.1, 2.3 | All endpoints return shop-specific data only; cross-shop access blocked |
| 4.3 | **Webhook multi-tenancy** — Whitelist webhook IPs per shop; sign webhooks with shop-specific secret; validate on receive | 1 | 1.1, 4.2 | Webhooks routed to correct shop; signature validation prevents spoofing |
| 4.4 | **API versioning** — Add `/api/v2/` prefix; deprecate old endpoints; version support matrix in docs | 1 | 4.2 | v2 endpoints work; v1 endpoints show deprecation notice; version headers included |
| 4.5 | **Request audit logging** — Log all API calls (user, endpoint, method, status, shop_id, timestamp) to audit table | 0.5 | 4.1, 2.2 | Audit table populated; queries return paginated logs; no sensitive data logged |
| **Checkpoint** | All API tests passing with shop isolation | 1 | 4.1–4.5 | Cross-shop data leakage impossible; webhooks routed correctly |

**Effort Total**: ~6.5 dev days

---

### PHASE 5: Dashboard & Ledger Enhancements (1.5 weeks, 7–8 dev days)

**Objective**: Build multi-ledger support, advanced dashboards, and cashflow reporting with shop context.

**Prerequisites**: Phase 2 (DB), Phase 3 (Frontend), Phase 4 (Isolation)

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 5.1 | **Multi-ledger management** — Create ledger CRUD endpoints; support multiple active ledgers per shop; UI to switch ledgers | 1.5 | 2.2, 3.1, 4.2 | Ledger dropdown in UI; can create/close/inherit ledgers; stats scope correctly |
| 5.2 | **Cashflow analytics** — Daily inflow/outflow charts; category breakdown; P&L summary; export as CSV/PDF | 1.5 | 3.3, 5.1 | Charts render correctly; data updates on message confirm; exports include all data |
| 5.3 | **Khata (credit tracking)** — Dashboard section showing outstanding dues per contact; days outstanding; reminder notifications | 1 | 2.3, 5.1 | Khata list updates on transactions; due amounts calculated correctly |
| 5.4 | **Daily snapshots & reconciliation** — End-of-day closing form (cash, inventory value, khata total); compare to previous day | 1.5 | 2.2, 3.6, 5.1 | Snapshots save correctly; history view shows daily trend; reconciliation alerts on mismatch |
| **Checkpoint** | Dashboard fully functional with multi-ledger & analytics | 0.5 | 5.1–5.4 | All dashboards load < 2 seconds; exports work; no data accuracy issues |

**Effort Total**: ~5.5 dev days

---

### PHASE 6: Core Features & Polish (1 week, 5 dev days)

**Objective**: Optimize existing features, fix edge cases, and improve UX.

**Prerequisites**: Phase 1–5

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 6.1 | **Rate limiting per shop** — Implement per-shop request limits (e.g., 300 req/min); return 429 on limit; show reset time | 1 | 4.1 | Rate limiter returns 429 correctly; limits are enforced per shop; resets on schedule |
| 6.2 | **Caching strategy** — Cache scheme DB, translation models, classifier; invalidate on updates; measure hit rates | 1 | 2.3 | Cache reduces query latency by >50%; invalidation works correctly |
| 6.3 | **Error handling & user feedback** — Standardize error responses; add toast notifications for all API errors; retry logic | 1 | 3.2, 4.2 | Users see friendly error messages; retry logic handles transient errors; no raw exceptions shown |
| 6.4 | **Performance profiling** — Measure endpoint latency; identify bottlenecks (OCR, Whisper, classifier); optimize queries | 1 | 4.2 | Dashboard queries < 200ms; classification < 3s; OCR < 5s (or acceptable for image size) |
| 6.5 | **Accessibility (WCAG 2.1 AA)** — Add alt text, ARIA labels, keyboard navigation; test with screen reader | 1 | 3.1–3.6 | Screen reader can navigate all pages; keyboard shortcuts work; color contrast passes |

**Effort Total**: ~5 dev days

---

### PHASE 7: Admin Console & Shop Management (1.5 weeks, 7–8 dev days) — *OPTIONAL*

**Objective**: Build admin interface for managing shops, users, billing, and platform-level settings.

**Prerequisites**: Phase 1–6

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 7.1 | **Admin role & access control** — Restrict admin pages to admins only; create `/admin` routes in Next.js | 1 | 1.5, 3.2 | Only admins can access admin pages; non-admins redirected; role checks work |
| 7.2 | **Shop management dashboard** — List all shops; create/edit/deactivate shops; view shop stats, api keys, webhooks | 1.5 | 2.2, 4.3, 5.2 | Admin can CRUD shops; shop stats displayed; API keys regeneratable |
| 7.3 | **User management** — List users per shop; assign roles; deactivate users; reset passwords via admin | 1.5 | 1.2, 1.5, 2.2 | Admin can manage all users; role assignment works; deactivation prevents login |
| 7.4 | **Billing & usage reporting** — Track requests per shop; show API usage, monthly bills, payment history | 1 | 2.2, 4.5 | Usage data accurate; billing dashboard shows correct totals; CSV export includes all fields |
| **Checkpoint** | Admin console fully operational | 0.5 | 7.1–7.4 | Admins can manage entire platform; no data leakage between shops |

**Effort Total**: ~5.5 dev days (OPTIONAL — skip if time-constrained)

---

### PHASE 8: Observability & Monitoring (1 week, 5 dev days) — *OPTIONAL*

**Objective**: Add logging, monitoring, alerting, and performance metrics.

**Prerequisites**: Phase 1–5

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 8.1 | **Structured logging** — Add Python logging config; log all API requests, errors, background jobs; include context (user, shop, request_id) | 1 | 4.5 | All important events logged; logs include context; can filter by shop_id or user |
| 8.2 | **Metrics & instrumentation** — Prometheus metrics (request count, latency, errors); Grafana dashboard | 1.5 | 8.1 | Prometheus scrapes FastAPI metrics endpoint; Grafana dashboard shows request rate, latency, errors |
| 8.3 | **Error tracking** — Integrate Sentry or similar; capture exceptions with context; alert on critical errors | 1 | 8.1 | Sentry captures all exceptions; alerts sent for critical errors; can see stack traces |
| 8.4 | **Health checks & uptime monitoring** — `/health` endpoint (DB, cache, external services); monitoring dashboard | 1.5 | 2.1 | Health check endpoint returns component status; monitoring tool tracks uptime |
| **Checkpoint** | Full observability in place; can debug issues quickly | 0.5 | 8.1–8.4 | Logging/monitoring working end-to-end; no performance impact |

**Effort Total**: ~5.5 dev days (OPTIONAL)

---

### PHASE 9: Testing & QA (1.5 weeks, 7–8 dev days)

**Objective**: Build comprehensive test suite; conduct full system QA.

**Prerequisites**: Phase 1–6 (optional: 7–8)

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 9.1 | **Unit tests** — Test auth module, ORM models, business logic; aim for >80% coverage | 2 | All phases | Unit tests run; coverage >80%; all tests pass in CI/CD |
| 9.2 | **Integration tests** — Test auth → DB → API flows; test webhook ingestion; test shop isolation | 2 | 1.1–1.6, 4.2, 4.3 | Integration tests cover happy path & edge cases; all pass |
| 9.3 | **E2E tests** — Test full user journeys (login → verify → confirm → ledger → export) using Playwright or Cypress | 1.5 | 3.1–3.6, 9.1, 9.2 | E2E tests run in headless mode; all user flows pass; screenshots on failure |
| 9.4 | **Manual QA & security review** — Test edge cases, UI/UX, security (auth, SQL injection, XSS, CSRF) | 1.5 | All phases | Security review checklist passed; no OWASP Top 10 issues found; QA sign-off |
| **Checkpoint** | All tests passing; system ready for production | 0.5 | 9.1–9.4 | Test coverage >80%; zero critical/high-severity bugs; CI/CD pipeline green |

**Effort Total**: ~7 dev days

---

### PHASE 10: Deployment & Handoff (1 week, 5 dev days)

**Objective**: Deploy to production; document for handoff.

**Prerequisites**: Phase 1–9

| Task | Description | Est. (days) | Dependencies | Success Criteria |
|------|-------------|-------------|--------------|-----------------|
| 10.1 | **Docker & containerization** — Dockerfile for FastAPI, Next.js; docker-compose for local dev; publish to registry | 1.5 | 1.1–9.4 | Containers build and run; docker-compose starts entire stack locally |
| 10.2 | **Deployment automation** — GitHub Actions/GitLab CI workflow; run tests, build images, deploy to staging/prod | 1.5 | 10.1 | CI/CD pipeline runs on push; deploys to staging on PR, prod on merge to main |
| 10.3 | **Environment & secrets management** — .env template, secrets in CI/CD, config validation at startup | 1 | 10.1, 10.2 | Secrets never logged; config validated on startup; supports multiple environments |
| 10.4 | **Documentation & handoff** — API docs (Swagger), deployment guide, troubleshooting guide, architecture diagram | 1 | All phases | Swagger docs complete and accurate; deployment guide has step-by-step instructions; team trained |

**Effort Total**: ~5 dev days

---

## 📈 Effort Summary & Timeline

| Phase | Tasks | Est. Days | Start | End | Critical Path |
|-------|-------|-----------|-------|-----|---|
| 1 | Auth & Multi-User | 5 | Wk1 | Wk2 | ✅ YES (blocks all) |
| 2 | DB Migration | 9 | Wk1* | Wk3 | ✅ YES (blocks API/UI) |
| 3 | Frontend (Next.js) | 7 | Wk2 | Wk3.5 | ✅ YES |
| 4 | API Isolation | 6.5 | Wk2* | Wk3.5 | ✅ YES |
| 5 | Dashboard & Ledger | 5.5 | Wk3.5 | Wk4.5 | ⚠️ Depends on 2–4 |
| 6 | Features & Polish | 5 | Wk4 | Wk5 | ⚠️ Depends on 1–5 |
| 7 | Admin Console | 5.5 | Wk5 | Wk6 | ⬜ OPTIONAL |
| 8 | Observability | 5.5 | Wk5 | Wk6 | ⬜ OPTIONAL |
| 9 | Testing & QA | 7 | Wk6 | Wk7.5 | ⚠️ Depends on all |
| 10 | Deployment | 5 | Wk7.5 | Wk8 | ✅ FINAL |

**Critical Path** (minimum sequence for MVP):
- Phase 1 (5d) → Phase 2 (9d, parallel with 3/4) → Phase 3 (7d) + Phase 4 (6.5d) → Phase 5 (5.5d) → Phase 6 (5d) → Phase 9 (7d) → Phase 10 (5d)
- **Minimum Timeline**: ~49 dev days → **~10 weeks** (with 5d/wk capacity)

**With Optionals** (7–8):
- Add 11 days → **~12 weeks**

---

## 🔗 Dependency Graph

```
Phase 1 (Auth)
    ↓
    ├→ Phase 2 (DB) ───────────┐
    │    ↓                       │
    │    ├→ Phase 3 (Frontend)  │
    │    ├→ Phase 4 (API)       │
    │    └→ Phase 5 (Dashboard) │
    │                           │
    └───────────→ Phase 6 (Polish)
                       ↓
                  Phase 9 (Testing)
                       ↓
                  Phase 10 (Deploy)

Parallel paths (can start after dependencies met):
- Phase 3 & 4 can run in parallel (both depend on 1 & 2)
- Phase 7 & 8 can run in parallel (optional, after 1–6)
- Phase 5 waits for 3 & 4 to start data flows

Blocking dependencies:
- ❌ Cannot start Phase 3/4 until Phase 2 DB ready
- ❌ Cannot start Phase 5 until Phase 3 & 4 endpoints exist
- ❌ Cannot start Phase 9 until Phase 1–6 complete
```

---

## 🛠️ Technical Decisions

### Database
- **SQLite → PostgreSQL**: Better concurrency, multi-tenant support, JSONB features
- **ORM**: SQLAlchemy (industry standard, works with Alembic for migrations)
- **Connection pooling**: SQLAlchemy's `QueuePool` (default, tuned for FastAPI)

### Frontend
- **Next.js + TypeScript + Tailwind + shadcn/ui**: Modern, scalable, accessible
- **State Management**: React Context + Zustand (lightweight, no heavy Redux)
- **API client**: TanStack Query (React Query) for data fetching & caching

### Auth
- **JWT + OAuth2PasswordBearer**: Industry standard, stateless, scalable
- **Password hashing**: bcrypt (slow hash, resistant to brute-force)
- **Token expiry**: 15min access + 7d refresh (standard patterns)

### Deployment
- **Docker + Docker Compose**: Easy local dev, reproducible prod
- **CI/CD**: GitHub Actions (free, integrates well with repo)
- **Hosting**: AWS/GCP/Azure (Dockerfile works on any platform)

---

## ✅ Success Criteria (Per Phase)

### Phase 1
- [ ] User can signup/login with email/password
- [ ] JWT token valid for 15 minutes; refresh extends session
- [ ] Middleware enforces auth on protected routes
- [ ] Role checks prevent unauthorized access (staff cannot access admin)

### Phase 2
- [ ] PostgreSQL running locally or remote
- [ ] All 8 tables exist with correct schema
- [ ] All SQLite data migrated; checksums match
- [ ] ORM queries perform < 500ms under load

### Phase 3
- [ ] Next.js frontend loads on localhost:3000
- [ ] Login page works; dashboard renders after auth
- [ ] All forms submit and send correct API payloads
- [ ] No console errors; responsive on mobile

### Phase 4
- [ ] API endpoints filter results by shop_id
- [ ] Webhook validation prevents cross-shop spoofing
- [ ] Rate limiting enforces per-shop limits
- [ ] Audit logs record all API calls

### Phase 5
- [ ] Users can create/close/inherit ledgers
- [ ] Dashboard displays correct P&L per ledger
- [ ] Khata tracking shows outstanding dues
- [ ] Exports include all ledger transactions

### Phase 6
- [ ] Dashboard loads < 2 seconds
- [ ] Rate limiter rejects requests > limit
- [ ] Cache hits > 50% on repeated queries
- [ ] WCAG 2.1 AA accessibility score

### Phase 7 (Optional)
- [ ] Admin can create/deactivate shops
- [ ] Admin can view shop-specific usage
- [ ] Billing dashboard accurate to within 1%

### Phase 8 (Optional)
- [ ] Logs capture all important events
- [ ] Prometheus metrics populated
- [ ] Sentry captures exceptions
- [ ] Health check endpoint responsive

### Phase 9
- [ ] Unit test coverage > 80%
- [ ] Integration tests cover auth, DB, API flows
- [ ] E2E tests cover all user journeys
- [ ] Zero OWASP Top 10 findings

### Phase 10
- [ ] Containers build and run
- [ ] CI/CD pipeline green on all commits
- [ ] Deployment guide step-by-step
- [ ] API docs complete in Swagger

---

## 📝 Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Data loss during SQLite → PG migration | Critical | (1) Backup SQLite before migration (2) Validate checksums (3) Test rollback plan |
| Authentication bypass due to JWT misconfiguration | Critical | (1) Security review by external expert (2) Pentest before launch (3) Rate-limit login attempts |
| Performance degradation after ORM migration | High | (1) Benchmark before/after (2) Add indexes on foreign keys (3) Profile slow queries early |
| Frontend/backend version mismatch in API contracts | Medium | (1) API versioning from Phase 4 (2) OpenAPI/Swagger docs (3) Automated contract tests |
| Shop isolation data leak | Critical | (1) Code review all queries for shop_id filters (2) Penetration test tenant isolation (3) Audit logging |
| Deployment fails in production | High | (1) Dry-run deployment on staging first (2) Blue-green deployment (3) Rollback plan tested |

---

## 🚀 Quick Start for Developers

1. **Clone & setup**:
   ```bash
   git clone <repo>
   cd satark_setu
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Follow phases in order**:
   - Check each phase's prerequisites before starting
   - Run tests after each task
   - Commit after each successful task

3. **Parallel tasks**:
   - After Phase 2 is 80% done, Phase 3 & 4 can start
   - Phase 7 & 8 can start after Phase 6 if time permits

4. **Testing**:
   - Unit tests: `pytest tests/unit/`
   - Integration tests: `pytest tests/integration/`
   - E2E tests: `npx playwright test` (after Phase 3)
   - Coverage report: `pytest --cov=satark_setu`

---

## 📚 Appendix: File Structure After Completion

```
satark_setu/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 (FastAPI app)
│   │   ├── auth/                   (Phase 1)
│   │   │   ├── models.py
│   │   │   ├── schemas.py
│   │   │   ├── router.py
│   │   │   └── dependencies.py
│   │   ├── db/                     (Phase 2)
│   │   │   ├── models.py           (SQLAlchemy ORM)
│   │   │   ├── session.py
│   │   │   ├── crud.py
│   │   │   └── migrations/         (Alembic)
│   │   ├── api/                    (Phase 4)
│   │   │   ├── v1/
│   │   │   ├── v2/
│   │   │   ├── middleware.py
│   │   │   └── audit.py
│   │   ├── pipeline/               (existing scam detection)
│   │   ├── tests/
│   │   │   ├── unit/
│   │   │   ├── integration/
│   │   │   └── conftest.py
│   │   └── config.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── pyproject.toml              (Poetry/setuptools)
├── frontend/                       (Phase 3)
│   ├── app/
│   │   ├── page.tsx               (home)
│   │   ├── dashboard/
│   │   ├── verify/
│   │   ├── admin/                 (Phase 7)
│   │   └── layout.tsx
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   ├── tests/                     (Phase 9)
│   ├── package.json
│   ├── next.config.js
│   └── Dockerfile
├── docker-compose.yml
├── .github/
│   └── workflows/
│       └── ci-cd.yml              (Phase 10)
├── IMPLEMENTATION_ROADMAP.md      (this file)
└── DEPLOYMENT_GUIDE.md            (Phase 10)
```

---

## 📞 Support & Questions

- **Architecture questions**: See Phase overviews and dependency graph
- **Task estimation**: Estimates assume 1 developer; may vary by experience level
- **Blockers**: File issue with context (phase, task, error message) for quick resolution
- **Parallel work**: Only Phase 3 & 4 can safely run in parallel; all others are sequential

---

**Last updated**: 2025-01-15 | **Status**: DRAFT | **Approval**: Pending
