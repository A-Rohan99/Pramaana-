"""
Satark Setu Auth Module

Provides JWT authentication infrastructure:
- Password hashing (bcrypt)
- JWT token generation and validation
- Database models for User and Shop
"""

from auth.password import hash_password, verify_password
from auth.jwt_utils import create_access_token, decode_token

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_token",
]
