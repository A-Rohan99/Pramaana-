# Satark Setu Merchant MVP — Design Document

**Target**: 7-day hackathon; produce multi-tenant scam detection + merchant dashboard  
**Tech Stack**: FastAPI (Python), SQLite, HTML/Vanilla JS, Docker  
**Design Patterns**: JWT + Middleware tenant context, repo pattern for data access

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ Frontend (Static HTML + Vanilla JS)                             │
│ - Login/Signup page                                             │
│ - Dashboard (stats, charts)                                     │
│ - Verify page (text/image/voice input)                          │
│ - Ledger & Inventory views                                      │
│ - Shop selector (for demo)                                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │ HTTP/JSON
┌─────────────────────────▼───────────────────────────────────────┐
│ FastAPI Backend (Port 8000)                                     │
├─────────────────────────────────────────────────────────────────┤
│ Layer 1: HTTP Handlers (api.py)                                 │
│  ├─ /auth/signup, /auth/login (new)                             │
│  ├─ /api/verify-* (existing, add shop context)                  │
│  ├─ /api/dashboard/* (existing, add shop filter)                │
│  └─ /api/webhook/* (existing, route by shop_id)                 │
├─────────────────────────────────────────────────────────────────┤
│ Layer 2: Middleware                                             │
│  └─ JWT extraction → shop_id injection into request.scope       │
├─────────────────────────────────────────────────────────────────┤
│ Layer 3: Business Logic (pipeline.py, classifier.py, etc.)     │
│  └─ Scam detection (unchanged; receives shop context)           │
├─────────────────────────────────────────────────────────────────┤
│ Layer 4: Data Access (db.py + auth module)                      │
│  └─ All queries filter by shop_id from request.scope            │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│ SQLite Database (pramaan.db)                                    │
│  ├─ users, shops (new tables)                                   │
│  ├─ messages, contacts, inventory, ledgers, ... (add shop_id)  │
│  └─ All indexed by (shop_id, ...)                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## JWT Authentication Scheme

### Token Structure

```json
{
  "sub": "user_id",
  "user_id": 1,
  "email": "rohan@merchant.local",
  "shop_id": 1,
  "role": "owner",
  "exp": 1704067200,
  "iat": 1704067200
}
```

**Fields**:
- `sub` (subject): User ID (JWT standard)
- `user_id`: Numeric user ID (duplicate of sub, for clarity)
- `email`: User email (for logging/debugging)
- `shop_id`: **Critical** — Merchant's shop ID; used in all queries
- `role`: User's role ("owner", "staff", "analyst"); MVP uses "owner" only
- `exp` (expiry): Token expires in 15 minutes (epoch seconds)
- `iat` (issued at): Token creation time

### Token Generation (Login/Signup)

```python
import jwt
from datetime import datetime, timedelta

def create_jwt_token(user_id: int, email: str, shop_id: int, role: str = "owner") -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "email": email,
        "shop_id": shop_id,
        "role": role,
        "exp": now + timedelta(minutes=15),
        "iat": now,
    }
    token = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    return token
```

### Token Validation (Middleware)

```python
from fastapi import Request, HTTPException
import jwt

async def jwt_middleware(request: Request, call_next):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return HTTPException(status_code=401, detail="Missing token")
    
    token = auth_header[7:]  # Remove "Bearer "
    try:
        payload = jwt.decode(token, os.environ["JWT_SECRET"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidSignatureError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # ✅ Inject shop_id into request scope (not request body)
    request.scope["shop_id"] = payload["shop_id"]
    request.scope["user_id"] = payload["user_id"]
    
    response = await call_next(request)
    return response
```

### Token Refresh (Future)

Post-hackathon: add `/auth/refresh` endpoint that returns a new 15-min token using refresh tokens (stored in DB).

---

## Tenant Context Middleware

### Design Pattern: Shop ID from JWT → Injected into Request Scope

**Goal**: Every database query must know which shop it's querying for.  
**Pattern**: Extract shop_id from JWT token in middleware; pass as implicit context (not method parameter).

### Implementation

```python
# middleware/tenant_context.py
async def tenant_middleware(request: Request, call_next):
    """Extract shop_id from JWT token and inject into request.scope."""
    
    # Skip middleware for public endpoints (auth, health, etc.)
    if request.url.path.startswith("/auth/"):
        return await call_next(request)
    
    # Get JWT from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="No token")
    
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # ✅ CRITICAL: Inject shop_id from JWT (never from request body)
    request.scope["shop_id"] = payload["shop_id"]
    request.scope["user_id"] = payload["user_id"]
    
    response = await call_next(request)
    return response
```

### Usage in Database Queries

```python
# OLD (no shop isolation):
def get_messages(limit=60):
    messages = conn.execute("SELECT * FROM messages LIMIT ?", (limit,)).fetchall()
    return messages

# NEW (with shop isolation):
def get_messages(limit=60, shop_id: int = None):
    # shop_id passed from middleware/request context
    messages = conn.execute(
        "SELECT * FROM messages WHERE shop_id = ? LIMIT ?",
        (shop_id, limit)
    ).fetchall()
    return messages

# USAGE in endpoint:
@app.get("/api/dashboard/messages")
async def dashboard_messages(request: Request, limit: int = 60):
    shop_id = request.scope["shop_id"]  # From middleware
    messages = db.get_messages(limit=limit, shop_id=shop_id)
    return {"messages": messages}
```

---

## Database Schema Changes

### New Tables

#### users

```sql
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id         INTEGER NOT NULL UNIQUE,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,  -- bcrypt hash, never plaintext
    full_name       TEXT,
    is_active       BOOLEAN DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT,
    FOREIGN KEY (shop_id) REFERENCES shops(id)
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_shop ON users(shop_id);
```

#### shops

```sql
CREATE TABLE shops (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT,
    address     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT
);
```

### Modified Tables

**Add shop_id to all existing tables:**

```sql
-- Messages table
ALTER TABLE messages ADD COLUMN shop_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE messages ADD FOREIGN KEY (shop_id) REFERENCES shops(id);
CREATE INDEX idx_messages_shop ON messages(shop_id, received_at DESC);

-- Contacts table
ALTER TABLE contacts ADD COLUMN shop_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE contacts ADD FOREIGN KEY (shop_id) REFERENCES shops(id);
CREATE INDEX idx_contacts_shop ON contacts(shop_id, trust_score DESC);

-- Inventory table
ALTER TABLE inventory ADD COLUMN shop_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE inventory ADD FOREIGN KEY (shop_id) REFERENCES shops(id);
CREATE INDEX idx_inventory_shop ON inventory(shop_id, item_name);

-- Ledgers table
ALTER TABLE ledgers ADD COLUMN shop_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE ledgers ADD FOREIGN KEY (shop_id) REFERENCES shops(id);
CREATE UNIQUE INDEX idx_ledgers_month_shop ON ledgers(month_key, shop_id);

-- Daily snapshots table
ALTER TABLE daily_snapshots ADD COLUMN shop_id INTEGER NOT NULL DEFAULT 1;
ALTER TABLE daily_snapshots ADD FOREIGN KEY (shop_id) REFERENCES shops(id);
CREATE INDEX idx_snapshots_shop ON daily_snapshots(shop_id, date DESC);

-- Community scam reports (global, no shop_id needed; not modified)
```

---

## API Endpoint Changes

### Authentication Endpoints (New)

#### POST /auth/signup

**Request**:
```json
{
  "email": "rohan@merchant.local",
  "password": "SecurePass123!",
  "shop_name": "Rohan's General Store"
}
```

**Response** (200 OK):
```json
{
  "user_id": 1,
  "email": "rohan@merchant.local",
  "shop_id": 1,
  "shop_name": "Rohan's General Store",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 900
}
```

**Errors**:
- 400: Email already exists, password too weak, shop_name empty
- 500: Database error

**Implementation**:
```python
@app.post("/auth/signup")
async def signup(payload: dict):
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password", "")
    shop_name = (payload.get("shop_name") or "").strip()
    
    # Validation
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be 8+ chars")
    if not shop_name:
        raise HTTPException(status_code=400, detail="Shop name required")
    
    # Check if email exists
    existing = db.find_user_by_email(email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already in use")
    
    # Create shop
    shop = db.create_shop(name=shop_name)
    
    # Create user
    user = db.create_user(
        shop_id=shop["id"],
        email=email,
        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
        full_name=payload.get("full_name", "")
    )
    
    # Generate JWT
    token = create_jwt_token(
        user_id=user["id"],
        email=user["email"],
        shop_id=shop["id"],
        role="owner"
    )
    
    return {
        "user_id": user["id"],
        "email": user["email"],
        "shop_id": shop["id"],
        "shop_name": shop["name"],
        "token": token,
        "expires_in": 900
    }
```

#### POST /auth/login

**Request**:
```json
{
  "email": "rohan@merchant.local",
  "password": "SecurePass123!"
}
```

**Response** (200 OK):
```json
{
  "user_id": 1,
  "email": "rohan@merchant.local",
  "shop_id": 1,
  "shop_name": "Rohan's General Store",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 900
}
```

**Errors**:
- 401: User not found or password incorrect (return same error for both to prevent email enumeration)
- 403: User is inactive

### Existing Endpoints (Add Shop Context)

#### POST /api/verify-text

**Changes**:
- Middleware adds shop_id to request.scope
- Message stored with shop_id in db.insert_message()

**Implementation**:
```python
@app.post("/api/verify-text")
async def verify_text(request: Request, payload: dict):
    shop_id = request.scope["shop_id"]  # From middleware
    text = payload.get("text", "").strip()
    language = validate_language(payload.get("language", "english"))
    
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    
    result = process_message(raw_text=text, language=language)
    
    # Store message with shop_id
    msg_id = db.insert_message({
        **result,
        "shop_id": shop_id,  # ✅ CRITICAL
        "channel": "web",
        "sender_id": request.scope["user_id"],
    })
    
    return {**result, "id": msg_id}
```

#### GET /api/dashboard/stats

**Changes**:
- Filter all queries by shop_id

**Implementation**:
```python
@app.get("/api/dashboard/stats")
async def dashboard_stats(request: Request, ledger_month: str | None = None):
    shop_id = request.scope["shop_id"]
    return db.get_stats(shop_id=shop_id, ledger_month=ledger_month)

# In db.py:
def get_stats(shop_id: int, ledger_month: str | None = None) -> dict:
    conn = get_conn()
    month = ledger_month or get_active_ledger_month(shop_id)
    
    month_filter = "AND ledger_month = :month AND shop_id = :shop_id"
    
    total_messages = conn.execute(
        f"SELECT COUNT(*) FROM messages WHERE shop_id = :shop_id {('AND ledger_month = :month' if month else '')}",
        {"shop_id": shop_id, "month": month}
    ).fetchone()[0]
    
    # ... (all queries add shop_id filter)
```

#### GET /api/dashboard/messages

**Changes**:
- Filter by shop_id

```python
@app.get("/api/dashboard/messages")
async def dashboard_messages(request: Request, limit: int = 60):
    shop_id = request.scope["shop_id"]
    messages = db.get_messages(limit=limit, shop_id=shop_id)
    return {"messages": messages}
```

### Webhook Endpoints (Multi-Tenant Routing)

#### POST /api/webhook/telegram?shop_id=<ID>

**Changes**:
- Accept shop_id as URL parameter
- Route message to correct shop

**Implementation**:
```python
@app.post("/api/webhook/telegram")
async def telegram_webhook(request: Request, shop_id: int):
    payload = await request.json()
    
    # Validate shop exists
    shop = db.get_shop(shop_id)
    if not shop:
        return {"status": "shop_not_found"}
    
    # Process message with shop context
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return {"status": "no_message"}
        
        msg = messages[0]
        text = (msg.get("text") or {}).get("body", "")
        sender = msg.get("from", "tg_user")
        
        result = process_message(raw_text=text, channel="telegram", sender_id=sender)
        
        # ✅ Store with shop_id from URL parameter
        msg_id = db.insert_message({
            **result,
            "shop_id": shop_id,  # From URL
            "channel": "telegram",
            "sender_id": sender,
        })
        
        return {"status": "processed", "id": msg_id}
    except Exception as e:
        logger.error("Telegram webhook error: %s", e)
        return {"status": "error"}
```

---

## Frontend Auth Flow

### Conceptual Flow

```
1. User opens http://localhost:8000
   ↓
   [Check localStorage for JWT token]
   ├─ Token exists & valid → Skip to Step 4
   └─ No token → Show login page

2. User fills login form
   [email, password] → POST /auth/login
   ↓
   [Receive JWT token]
   ↓
   [Save JWT to localStorage]
   ↓
3. Redirect to /dashboard

4. Dashboard page loads
   [Fetch JWT from localStorage]
   [Add to Authorization header: "Bearer {token}"]
   [Fetch /api/dashboard/stats]
   ↓
   [Middleware validates JWT; extracts shop_id]
   [Return stats for shop_id]
   ↓
   [Render dashboard]

5. User clicks "Logout"
   [Clear JWT from localStorage]
   [Redirect to login page]
```

### JavaScript Implementation

**Login Form** (HTML):
```html
<form id="login-form">
  <input type="email" id="email" placeholder="Email" required>
  <input type="password" id="password" placeholder="Password" required>
  <button type="submit">Log In</button>
</form>

<script>
document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;
  
  const response = await fetch("/auth/login", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({email, password})
  });
  
  if (response.ok) {
    const data = await response.json();
    localStorage.setItem("jwt_token", data.token);
    localStorage.setItem("shop_id", data.shop_id);
    window.location = "/dashboard";
  } else {
    alert("Login failed: " + (await response.text()));
  }
});
</script>
```

**Protected Page** (Dashboard):
```html
<script>
function getAuthHeader() {
  const token = localStorage.getItem("jwt_token");
  if (!token) {
    window.location = "/login";
    return null;
  }
  return {"Authorization": `Bearer ${token}`};
}

async function fetchDashboard() {
  const headers = getAuthHeader();
  if (!headers) return;
  
  const response = await fetch("/api/dashboard/stats", {headers});
  
  if (response.status === 401) {
    localStorage.removeItem("jwt_token");
    window.location = "/login";
    return;
  }
  
  if (response.ok) {
    const data = await response.json();
    renderDashboard(data);
  } else {
    alert("Error loading dashboard");
  }
}

function logout() {
  localStorage.removeItem("jwt_token");
  localStorage.removeItem("shop_id");
  window.location = "/login";
}

// On page load
document.addEventListener("DOMContentLoaded", fetchDashboard);
</script>
```

---

## Error Handling

### HTTP Status Codes

| Code | Reason | Example |
|------|--------|---------|
| 200 | Success | Verification result returned |
| 400 | Bad request | Missing required field, invalid format |
| 401 | Unauthorized | Missing JWT or invalid token |
| 403 | Forbidden | Authenticated but accessing another shop's data |
| 404 | Not found | Message ID doesn't exist for shop |
| 429 | Rate limited | Too many requests (per-shop limit) |
| 500 | Server error | Database error, OCR failure |

### Example Error Responses

```json
{
  "status": "error",
  "detail": "Invalid token",
  "code": "AUTH_INVALID_TOKEN"
}
```

```json
{
  "status": "error",
  "detail": "Message not found for your shop",
  "code": "NOT_FOUND"
}
```

### Frontend Error Handling

```javascript
async function apiCall(endpoint, options = {}) {
  try {
    const response = await fetch(endpoint, options);
    
    if (response.status === 401) {
      localStorage.removeItem("jwt_token");
      window.location = "/login";
      return;
    }
    
    if (response.status === 403) {
      showToast("You don't have permission to access this resource");
      return;
    }
    
    if (!response.ok) {
      const error = await response.json();
      showToast(`Error: ${error.detail}`);
      return null;
    }
    
    return await response.json();
  } catch (err) {
    showToast(`Network error: ${err.message}`);
    return null;
  }
}

function showToast(message) {
  // Display notification to user
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}
```

---

## Data Flow: Message Verification → Ledger

```
User submits scam message (text/image/voice)
        ↓
POST /api/verify-text
├─ Middleware extracts shop_id=1 from JWT
└─ Request scope now contains {user_id, shop_id}
        ↓
process_message(raw_text) → Classification + Risk Score
        ↓
db.insert_message({
  shop_id: 1,              ← ✅ From middleware
  channel: "web",
  sender_id: 1,            ← ✅ From JWT
  raw_text: "...",
  classification: "scam",
  risk_score: 95,
  ledger_status: "draft",  ← Initially draft (not in ledger)
  ...
})
        ↓
Response sent to frontend
        ↓
User clicks "Confirm to Ledger"
        ↓
POST /api/dashboard/confirm/{msg_id}
├─ Middleware extracts shop_id=1
├─ Validate: message exists AND message.shop_id == current shop_id
└─ If validation fails → 403/404
        ↓
db.update_ledger_status(msg_id, "confirmed")
├─ Verify message.shop_id matches current shop_id
└─ Update ledger_status, confirmed_at timestamp
        ↓
Dashboard stats fetched:
        ↓
GET /api/dashboard/stats?ledger_month=2025-01
├─ Filter: WHERE shop_id=1 AND ledger_month='2025-01' AND ledger_status='confirmed'
├─ Sum amounts → total_earnings/spendings
└─ Return stats for shop 1 only
        ↓
Frontend renders:
  - Total confirmed: 1
  - Scam count: 1
  - P&L updated
```

---

## Security Considerations

### Principle: Defense in Depth

1. **JWT Secret** (first line)
   - Stored in environment variable (never hardcoded)
   - Generated with `secrets.token_urlsafe(32)`
   - Rotated quarterly (post-hackathon)

2. **Shop ID Extraction** (second line)
   - Always from JWT token, NEVER from request body/params
   - Middleware enforces this pattern
   - Endpoint developers cannot override

3. **Query Filtering** (third line)
   - All queries include WHERE shop_id = :shop_id
   - Code review verifies 100% coverage
   - Missing filter = critical bug

4. **Password Hashing**
   - bcrypt with random salt (not MD5, not SHA256)
   - Never stored or logged
   - Compared using bcrypt.checkpw()

5. **Rate Limiting**
   - Per-shop, not per-IP
   - 300 requests/minute per shop
   - Return 429 with Retry-After header

6. **Error Messages**
   - Never leak internal details (e.g., "User not found" vs "Email or password incorrect")
   - No stack traces in API responses
   - Detailed errors in server logs only

---

## Deployment Checklist

- [ ] JWT_SECRET environment variable set (not in code)
- [ ] SQLite database file has correct permissions
- [ ] All queries verified to include shop_id filters
- [ ] Middleware JWT extraction tested
- [ ] Demo data (two merchants) seeded at startup
- [ ] CORS headers allow frontend domain
- [ ] HTTPS enabled (if deployed to production)
- [ ] Rate limiting active
- [ ] Error handling returns no stack traces
- [ ] Logging includes user/shop context

---

## Post-Hackathon Improvements

- Migrate SQLite → PostgreSQL (better concurrency)
- Implement token refresh endpoint
- Add role-based access control (staff, analyst roles)
- Webhook signature validation (HMAC)
- Advanced audit logging
- Real-time WebSocket updates
- API versioning (/api/v2/)
