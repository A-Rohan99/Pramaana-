# Satark Setu Merchant MVP — Spec Overview

**Date Created**: 2025-01-20  
**Status**: READY FOR TASK GENERATION  
**Timeline**: 7 days (48h auth → 72h isolation → completion)  
**Team**: 1 developer (full-stack)

---

## What We're Building

A **multi-tenant merchant dashboard** that combines:
1. **Scam Detection** — Existing FastAPI pipeline (text/image/voice classification)
2. **Multi-User Auth** — New JWT-based login/signup
3. **Shop Isolation** — Each merchant sees only their data (ledger, inventory, contacts)
4. **Dashboard** — Stats, ledger, inventory management, expense tracking

**MVP Success**: Two merchants can log in independently; complete data isolation; zero cross-shop leakage.

---

## The Two Spec Files (Single Source of Truth)

### 1. HACKATHON_MVP_REQUIREMENTS.md
**What**: Defines what we're building  
**Contains**:
- Feature matrix (MVP scope vs out-of-scope)
- Three user flows (signup, verify message, isolation test)
- Data security principles (all queries must filter by shop_id)
- Database schema additions (users, shops tables + shop_id columns)
- API surface (new auth endpoints + modifications to existing endpoints)
- 20 acceptance criteria grouped by feature
- Testing strategy
- Demo merchant setup

**Read this for**: Understanding what the feature should do

### 2. HACKATHON_MVP_DESIGN.md
**What**: Defines how we're building it  
**Contains**:
- Architecture overview (layers: HTTP → middleware → business logic → DB)
- JWT token structure (user_id, shop_id, exp, role)
- Token generation/validation/refresh
- Tenant context middleware (shop_id extraction from JWT → injection into request scope)
- Database schema changes (exact SQL for new tables + ALTER statements)
- Endpoint implementation details (code snippets)
- Frontend auth flow (JavaScript)
- Error handling (HTTP codes + error messages)
- Data flow diagram (message verification → storage → ledger)
- Security considerations (defense in depth)
- Deployment checklist

**Read this for**: Understanding how to implement the feature

---

## How These Files Guide Task Generation

### 1. Requirements → Scope
Requirements document defines:
- What features are in/out of scope
- What acceptance criteria must pass
- What acceptance criteria should NOT be in MVP

This ensures tasks don't creep into post-hackathon features.

### 2. Design → Implementation Tasks
Design document provides:
- Exact database schema (copy-paste SQL)
- JWT middleware implementation (copy-paste code)
- API endpoint modifications (exact code patterns)
- Frontend JavaScript (copy-paste templates)

This enables tasks like:
- "Add JWT middleware following the code pattern in DESIGN.md section 'JWT Middleware'"
- "Implement db.py queries following the pattern: `SELECT ... WHERE shop_id = :shop_id`"

### 3. Acceptance Criteria → Validation
Requirements document specifies how to verify each task:
- "[ ] Message stored with shop_id"
- "[ ] API endpoint rejects attempts to access other shop's messages"
- "[ ] Manual test: User A's messages invisible to User B"

Tasks reference these criteria to validate completion.

---

## Key Design Decisions

### 1. JWT over Sessions
- **Why**: Stateless; each token self-contained; no session table needed
- **Trade-off**: Token expiry logic in code (not DB); refresh flow post-hackathon

### 2. Shop ID in JWT (not request param)
- **Why**: Prevents user from spoofing other shops (shop_id=2 in request body)
- **How**: Middleware extracts shop_id from JWT; passes via request.scope
- **Pattern**: All endpoint code reads `request.scope["shop_id"]`; never from request.body

### 3. Middleware injection vs method parameter
- **Why**: Simpler code; can't accidentally forget shop_id
- **How**: Middleware adds shop_id to request.scope before endpoint runs
- **Trade-off**: Requires understanding request.scope pattern

### 4. Stay on SQLite (don't migrate to PostgreSQL)
- **Why**: Faster to ship; zero setup required
- **Trade-off**: Less concurrent access; plan PostgreSQL migration post-hackathon

### 5. Enhance HTML + Vanilla JS (don't rewrite in Next.js)
- **Why**: Reuses existing frontend; ships faster
- **Trade-off**: Limited to vanilla JS; post-hackathon rewrite to Next.js

---

## Critical Success Factors

### 1. 100% Shop ID Filtering
**Every query must include `WHERE shop_id = :shop_id`**

This is not optional. A single missed filter = data leak = critical bug.

**Code review checklist**:
- [ ] Scan db.py for all SELECT/UPDATE/DELETE statements
- [ ] Verify each includes shop_id filter
- [ ] Cross-check against requirements "Shop Isolation" section

### 2. JWT Middleware Runs First
**Middleware must extract shop_id before endpoint handler runs**

Otherwise endpoints don't know which shop to query.

**Test**:
- [ ] Middleware test: verify shop_id injected into request.scope
- [ ] Endpoint test: verify endpoint reads request.scope["shop_id"]

### 3. Demo Merchant Accounts Work
**Two merchants must exist at startup with independent data**

This is how stakeholders will demo/validate the system.

**Setup**:
- [ ] fixtures/seed_demo_data.py creates demo users + shops
- [ ] Each merchant has 5–10 sample messages, contacts, inventory items
- [ ] Running `python api.py` triggers setup on first run

### 4. No Cross-Shop API Access
**Even with valid JWT, if shop_id in request != shop_id in JWT, reject (403)**

This catches bugs where code accidentally trusts request params.

**Test**:
- [ ] Manual: Login as Merchant A, try to access Merchant B's messages (should get 403 or empty)
- [ ] Automated: Unit test for tenant context extraction

---

## File Map

```
satark_setu/
├── HACKATHON_MVP_REQUIREMENTS.md    ← Read first
├── HACKATHON_MVP_DESIGN.md          ← Read second
├── SPEC_OVERVIEW.md                 ← You are here
├── HACKATHON_SPRINT.md              ← Phase timeline
└── (code files will be modified per design)
```

---

## Next Steps (Task Generation)

Once these specs are approved:

1. **Create tasks.md**
   - Task 1: Add JWT auth infrastructure (users, shops tables, token generation)
   - Task 2: Add tenant middleware (shop_id extraction)
   - Task 3: Modify db.py to filter all queries by shop_id
   - Task 4: Update 30+ API endpoints to respect shop isolation
   - Task 5: Create demo merchant fixture
   - Task 6: Frontend auth UI (login/signup forms)
   - Task 7: Webhook multi-tenancy (route by shop_id param)
   - Task 8: Docker setup + deployment
   - Task 9: Testing + QA
   - Task 10: Demo walkthrough + docs

2. **Start implementation**
   - Follow exact code patterns in DESIGN.md
   - Reference acceptance criteria in REQUIREMENTS.md
   - Test each task before moving to next

3. **Validate completion**
   - Two merchants can login independently
   - Each merchant sees only their data
   - Cross-shop access attempts fail
   - No console errors
   - Demo script works end-to-end

---

## Sign-Off Checklist

**Stakeholders**: Approve these specs before task generation

- [ ] Requirements are clear and achievable in 7 days
- [ ] Design is technically sound and feasible
- [ ] Feature matrix matches business expectations
- [ ] Acceptance criteria are measurable and testable
- [ ] Out-of-scope items understood and documented
- [ ] Demo merchant setup acceptable

**Once approved**, proceed to task.md generation → implementation → deploy.

---

**Questions?** Refer to specific sections:
- Requirements questions → HACKATHON_MVP_REQUIREMENTS.md
- Implementation questions → HACKATHON_MVP_DESIGN.md
- Timeline questions → HACKATHON_SPRINT.md
