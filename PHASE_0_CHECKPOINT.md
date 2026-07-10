# Phase 0 Checkpoint — Satark Setu Merchant MVP (48h)

## ✅ Completion Status

**All 8 Tasks Complete:**
- [x] Task 0.1: JWT Infrastructure
- [x] Task 0.2: JWT Middleware  
- [x] Task 0.3: Signup Endpoint
- [x] Task 0.4: Login Endpoint
- [x] Task 0.5: Demo Merchant Fixture
- [x] Task 0.6: Pipeline Regression Tests
- [x] Task 0.7: Frontend Auth UI
- [x] Task 0.8: Phase 0 Checkpoint

---

## 🚀 Quick Start

### 1. Start the Server

```bash
cd c:\Users\rohan\OneDrive\project\satark_setu
.venv\Scripts\activate
uvicorn api:app --reload --port 8000
```

**Expected output:**
```
INFO: Demo merchants created: demo@merchant.local, demo2@merchant.local
```

---

## 🧪 Verification Tests

### Test 1: Demo Merchant Login

```powershell
# Login as demo merchant 1
$response = Invoke-RestMethod `
  -Uri "http://localhost:8000/auth/login" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"email":"demo@merchant.local","password":"DemoPass123!"}'

Write-Host "Token: $($response.access_token)"
Write-Host "Shop ID: $($response.shop_id)"
```

### Test 2: Shop Isolation

```powershell
# Login as merchant 2
$response2 = Invoke-RestMethod `
  -Uri "http://localhost:8000/auth/login" `
  -Method Post `
  -Headers @{"Content-Type"="application/json"} `
  -Body '{"email":"demo2@merchant.local","password":"DemoPass456!"}'

Write-Host "Shop ID 2: $($response2.shop_id)"
```

### Test 3: Frontend Login

1. Open browser: `http://localhost:8000`
2. Login modal should appear
3. Login with: demo@merchant.local / DemoPass123!
4. Check localStorage for authToken
5. Dashboard should load

### Test 4: Protected Endpoint

```powershell
$token = "YOUR_JWT_HERE"
$headers = @{"Authorization" = "Bearer $token"}

$stats = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/dashboard/stats" `
  -Method Get `
  -Headers $headers

Write-Host "Stats: $($stats | ConvertTo-Json)"
```

---

## 📋 Files Modified

**Created:**
- `auth/__init__.py`
- `auth/password.py`
- `auth/jwt_utils.py`
- `auth/models.py`
- `auth/middleware.py`
- `scripts/setup_demo_merchants.py`
- `test_auth.py`

**Modified:**
- `api.py` - Auth endpoints + middleware
- `db.py` - User & Shop tables
- `frontend/index.html` - Auth modal
- `.env` - JWT_SECRET

---

## 🎯 Success Criteria

✅ JWT auth working
✅ Two demo merchants
✅ Shop isolation active
✅ Frontend auth UI added
✅ Zero regressions
✅ All tests passing

**Phase 0 COMPLETE** - Ready for hackathon demo!
