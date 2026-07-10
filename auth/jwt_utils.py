"""
JWT token generation and validation.

Creates and decodes JWT tokens for merchant authentication.
Token payload includes shop_id, email, and expiry (30 days).
JWT_SECRET must be set in environment variables.
"""

import os
import jwt
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any


def get_jwt_secret() -> str:
    """
    Get JWT_SECRET from environment, or generate a new one if missing.
    
    Returns:
        JWT_SECRET string (32+ bytes)
        
    Raises:
        RuntimeError: If JWT_SECRET is empty or invalid
    """
    secret = os.environ.get("JWT_SECRET", "").strip()
    
    if not secret:
        # Generate a new secret if not set
        secret = secrets.token_urlsafe(32)
        print(f"⚠️  JWT_SECRET not set in environment. Generated: {secret}")
        print("   Please add this to your .env file:")
        print(f"   JWT_SECRET={secret}")
        os.environ["JWT_SECRET"] = secret
    
    if len(secret) < 32:
        raise RuntimeError(
            f"JWT_SECRET too short ({len(secret)} bytes). "
            f"Must be at least 32 bytes. "
            f"Generate with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    
    return secret


def create_access_token(
    payload: Dict[str, Any],
    expires_in_days: int = 30,
) -> str:
    """
    Generate a JWT access token.
    
    Args:
        payload: Dict containing at minimum: shop_id, email, user_id
        expires_in_days: Token lifetime in days (default 30)
        
    Returns:
        Encoded JWT token string
        
    Example:
        >>> token = create_access_token({
        ...     "shop_id": 1,
        ...     "email": "merchant@example.com",
        ...     "user_id": 1,
        ... })
        >>> len(token) > 0
        True
        >>> "." in token  # Valid JWT has 3 parts separated by dots
        True
    """
    if not isinstance(payload, dict):
        raise TypeError("payload must be a dict")
    
    # Required fields
    required_fields = {"shop_id", "email", "user_id"}
    missing = required_fields - set(payload.keys())
    if missing:
        raise ValueError(f"payload missing required fields: {missing}")
    
    # Build the complete token payload
    now = datetime.utcnow()
    expiry = now + timedelta(days=expires_in_days)
    
    token_payload = {
        **payload,
        "iat": now.timestamp(),  # Issued at
        "exp": expiry.timestamp(),  # Expiry
    }
    
    secret = get_jwt_secret()
    token = jwt.encode(
        token_payload,
        secret,
        algorithm="HS256"
    )
    
    return token


def decode_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT token string (from Authorization header)
        
    Returns:
        Decoded token payload dict
        
    Raises:
        jwt.ExpiredSignatureError: If token has expired
        jwt.InvalidSignatureError: If token signature is invalid
        jwt.DecodeError: If token format is invalid
        
    Example:
        >>> payload = decode_token(token)
        >>> payload["shop_id"]
        1
    """
    if not isinstance(token, str):
        raise TypeError("token must be a string")
    
    secret = get_jwt_secret()
    
    try:
        decoded = jwt.decode(
            token,
            secret,
            algorithms=["HS256"]
        )
        return decoded
    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("Token has expired")
    except jwt.InvalidSignatureError:
        raise jwt.InvalidSignatureError("Token signature is invalid")
    except jwt.DecodeError:
        raise jwt.DecodeError("Invalid token format")


def is_token_valid(token: str) -> bool:
    """
    Quick check if a token is valid without raising exceptions.
    
    Args:
        token: JWT token string
        
    Returns:
        True if token is valid and not expired, False otherwise
    """
    if not isinstance(token, str):
        return False
    
    try:
        decode_token(token)
        return True
    except (jwt.ExpiredSignatureError, jwt.InvalidSignatureError, jwt.DecodeError):
        return False
