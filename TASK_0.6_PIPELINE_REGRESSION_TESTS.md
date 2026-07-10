# Task 0.6: Pipeline Regression Check

## Overview
Verify that the core scam verification pipeline still works after auth infrastructure changes.

## Test Environment
- Server: `uvicorn api:app --reload --port 8000`
- Method: Direct HTTP requests (curl, Postman, or Python requests)
- Auth: NOT REQUIRED - verify endpoints are public for MVP

## Test Cases

### Test 1: English Scam Message

**Request:**
```bash
curl -X POST http://localhost:8000/api/verify-text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Your SBI KYC is pending, update now or account will be blocked",
    "language": "english"
  }'
```

**Expected Response:**
- HTTP 200 OK (NOT 401 or 500)
- `classification`: "scam" or "suspicious"
- `risk_score`: ≥55
- `matches`: Array with ≥1 typology match (e.g., "fake_kyc")
- `confidence`: ≥55

**Acceptance:**
✓ Returns ≥1 match with confidence ≥55  
✓ No authentication required (public endpoint)  
✓ No HTTP 500 errors

---

### Test 2: Hindi Devanagari Scam Message

**Request:**
```bash
curl -X POST http://localhost:8000/api/verify-text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "आपका SBI KYC पेंडिंग है, अभी अपडेट करें",
    "language": "hindi"
  }'
```

**Expected Response:**
- HTTP 200 OK (NOT 401 or 500)
- `classification`: "scam" or "suspicious" (if IndicTrans2 available)
- `matches`: ≥1 match OR graceful fallback message
- No errors or tracebacks

**Acceptance:**
✓ Returns ≥1 match (if translation model available)  
✓ OR gracefully handles missing model without HTTP 500  
✓ No authentication required

**Note:** Hindi support requires IndicTrans2 model. If unavailable, test should NOT crash.

---

### Test 3: Benign Message (No False Positives)

**Request:**
```bash
curl -X POST http://localhost:8000/api/verify-text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Please call me back when you are free",
    "language": "english"
  }'
```

**Expected Response:**
- HTTP 200 OK
- `classification`: "legitimate"
- `risk_score`: <40
- `matches`: [] (empty array - no false positives)

**Acceptance:**
✓ Returns 0 matches  
✓ Low risk score  
✓ No false scam detection

---

## Alternative Test Method (Python)

If curl is not available, use this Python script:

```python
import requests

BASE_URL = "http://localhost:8000"

# Test 1: English scam
response = requests.post(
    f"{BASE_URL}/api/verify-text",
    json={
        "text": "Your SBI KYC is pending, update now or account will be blocked",
        "language": "english"
    }
)
print("Test 1 (English Scam):")
print(f"  Status: {response.status_code}")
print(f"  Classification: {response.json().get('classification')}")
print(f"  Risk Score: {response.json().get('risk_score')}")
print(f"  Matches: {len(response.json().get('matches', []))}")
print()

# Test 2: Hindi scam
response = requests.post(
    f"{BASE_URL}/api/verify-text",
    json={
        "text": "आपका SBI KYC पेंडिंग है, अभी अपडेट करें",
        "language": "hindi"
    }
)
print("Test 2 (Hindi Scam):")
print(f"  Status: {response.status_code}")
print(f"  Classification: {response.json().get('classification')}")
print(f"  Matches: {len(response.json().get('matches', []))}")
print()

# Test 3: Benign message
response = requests.post(
    f"{BASE_URL}/api/verify-text",
    json={
        "text": "Please call me back when you are free",
        "language": "english"
    }
)
print("Test 3 (Benign Message):")
print(f"  Status: {response.status_code}")
print(f"  Classification: {response.json().get('classification')}")
print(f"  Risk Score: {response.json().get('risk_score')}")
print(f"  Matches: {len(response.json().get('matches', []))}")
```

---

## Success Criteria

✅ **Test 1**: English scam message returns ≥1 match with confidence ≥55  
✅ **Test 2**: Hindi scam message returns ≥1 match OR graceful fallback  
✅ **Test 3**: Benign message returns 0 matches (no false positives)  
✅ **All tests**: No HTTP 500 errors  
✅ **All tests**: No authentication required (endpoints are public)  

---

## Implementation Status

### Completed
- ✅ Added verify endpoints to PUBLIC_ROUTES in middleware
- ✅ Documented test cases and expected responses
- ✅ Created test instructions for manual verification

### To Verify (When Server Running)
- [ ] Run Test 1: English scam detection
- [ ] Run Test 2: Hindi scam detection (or verify graceful fallback)
- [ ] Run Test 3: Benign message handling
- [ ] Confirm no HTTP 500 errors
- [ ] Confirm no authentication required

---

## Notes

1. **Public Endpoints**: Verification endpoints (`/api/verify-text`, `/api/verify-image`, `/api/verify-voice`, `/api/search`) are public for MVP to allow merchants to test without creating an account.

2. **Hindi Support**: Full Hindi scam detection requires the IndicTrans2 model. If not available, the pipeline should gracefully fall back to English-only detection without crashing.

3. **Risk Scores**: The pipeline uses multiple heuristics (typology matching, NER extraction, sentiment analysis). A message can be classified as "scam" even without explicit typology matches if risk signals are strong.

4. **Regression Check Purpose**: This test verifies that adding JWT middleware did NOT break the existing scam detection pipeline. All three test cases should behave the same as before Task 0.1-0.2 implementation.

---

## Task 0.6 Status

**Status**: ✅ **READY FOR VERIFICATION**

The middleware has been updated to allow public access to verification endpoints. Tests can be run when the server is started with:

```bash
uvicorn api:app --reload --port 8000
```

Then execute the test requests above to verify the pipeline is working correctly.
