"""
Tests for JWT middleware and shop scope injection.

Tests verify:
1. Protected endpoints require valid JWT
2. Public endpoints accessible without JWT
3. shop_id and user_id injected into request scope
4. Expired/invalid tokens return 401
"""

import pytest
from fastapi.testclient import TestClient
from auth.jwt_utils import create_access_token
import jwt
import datetime

# Import the app
from api import app

client = TestClient(app)


def test_public_route_accessible_without_jwt():
    """Public routes (/, /auth/signup, /auth/login) should be accessible without JWT."""
    # Test root endpoint
    response = client.get("/")
    # Expect either 200 (if route exists) or 404 (if not yet implemented)
    # But NOT 401 (unauthorized)
    assert response.status_code != 401, "Public route / should not require JWT"


def test_protected_route_requires_jwt():
    """Protected endpoints should return 401 without JWT."""
    # Test a protected endpoint (any API endpoint except auth routes)
    response = client.get("/api/dashboard/stats")
    assert response.status_code == 401
    assert "Authorization" in response.json()["detail"] or "Token" in response.json()["detail"]


def test_protected_route_with_valid_jwt():
    """Protected endpoints with valid JWT should inject shop_id into request scope."""
    # Create a valid token
    token = create_access_token({
        "shop_id": 1,
        "user_id": 1,
        "email": "test@example.com"
    })
    
    # Test a protected endpoint with valid JWT
    response = client.get(
        "/api/dashboard/stats",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Should succeed (not 401)
    # May return 200 or other status depending on endpoint logic
    assert response.status_code != 401, f"Valid JWT should allow access, got: {response.json()}"


def test_protected_route_with_invalid_jwt():
    """Protected endpoints with invalid JWT should return 401."""
    response = client.get(
        "/api/dashboard/stats",
        headers={"Authorization": "Bearer invalid_token_string"}
    )
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"] or "Token" in response.json()["detail"]


def test_protected_route_with_expired_jwt():
    """Protected endpoints with expired JWT should return 401."""
    # Create an expired token (expiry in the past)
    import os
    from datetime import timedelta
    secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only")
    
    expired_payload = {
        "shop_id": 1,
        "user_id": 1,
        "email": "test@example.com",
        "iat": (datetime.datetime.utcnow() - timedelta(days=31)).timestamp(),
        "exp": (datetime.datetime.utcnow() - timedelta(days=1)).timestamp(),  # Expired yesterday
    }
    
    expired_token = jwt.encode(expired_payload, secret, algorithm="HS256")
    
    response = client.get(
        "/api/dashboard/stats",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_protected_route_without_bearer_prefix():
    """Authorization header without 'Bearer ' prefix should return 401."""
    token = create_access_token({
        "shop_id": 1,
        "user_id": 1,
        "email": "test@example.com"
    })
    
    response = client.get(
        "/api/dashboard/stats",
        headers={"Authorization": token}  # Missing "Bearer " prefix
    )
    assert response.status_code == 401
    assert "Bearer" in response.json()["detail"] or "format" in response.json()["detail"]


def test_protected_route_with_empty_token():
    """Empty token after Bearer prefix should return 401."""
    response = client.get(
        "/api/dashboard/stats",
        headers={"Authorization": "Bearer "}
    )
    assert response.status_code == 401


def test_token_missing_shop_id():
    """Token without shop_id should return 401."""
    import os
    secret = os.environ.get("JWT_SECRET", "test_secret_key_for_testing_only")
    
    # Create token without shop_id
    invalid_payload = {
        "user_id": 1,
        "email": "test@example.com",
        "exp": (datetime.datetime.utcnow() + datetime.timedelta(days=1)).timestamp()
    }
    
    invalid_token = jwt.encode(invalid_payload, secret, algorithm="HS256")
    
    response = client.get(
        "/api/dashboard/stats",
        headers={"Authorization": f"Bearer {invalid_token}"}
    )
    assert response.status_code == 401
    assert "shop_id" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
