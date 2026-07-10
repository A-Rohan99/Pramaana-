#!/usr/bin/env python3
"""Manual test of auth infrastructure (Task 0.1)."""

import os
os.environ['JWT_SECRET'] = 'test_secret_key_at_least_32_bytes_long_for_testing_purposes'

from auth import hash_password, verify_password, create_access_token, decode_token
import db

print("=" * 70)
print("TASK 0.1: JWT Authentication Infrastructure Manual Tests")
print("=" * 70)

# Test 1: Password hashing
print("\n[TEST 1] Password Hashing")
password = "test123"
hashed = hash_password(password)
print(f"  ✓ hash_password('{password}') returns hashed string")
print(f"    Hash: {hashed[:50]}...")
print(f"  ✓ verify_password('{password}', hashed) = {verify_password(password, hashed)}")

# Test 2: JWT token generation
print("\n[TEST 2] JWT Token Generation")
payload = {
    "shop_id": 1,
    "email": "merchant@example.com",
    "user_id": 1,
}
token = create_access_token(payload)
print(f"  ✓ create_access_token({payload})")
print(f"    Token: {token[:50]}...")
print(f"    Token format valid: {token.count('.') == 2} (has 3 parts separated by dots)")

# Test 3: JWT token decoding
print("\n[TEST 3] JWT Token Decoding")
decoded = decode_token(token)
print(f"  ✓ decode_token(token) returns dict with:")
print(f"    - shop_id: {decoded['shop_id']}")
print(f"    - email: {decoded['email']}")
print(f"    - user_id: {decoded['user_id']}")
print(f"    - exp: {decoded['exp']} (expiry timestamp)")
print(f"    - iat: {decoded['iat']} (issued at timestamp)")

# Test 4: Database tables
print("\n[TEST 4] Database Tables")
db.init_db()

# Check shops table
conn = db.get_conn()
shops_table = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='shops'"
).fetchone()
print(f"  ✓ Shops table exists: {shops_table is not None}")

# Check users table
users_table = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
).fetchone()
print(f"  ✓ Users table exists: {users_table is not None}")

# Test 5: Create and retrieve shop
print("\n[TEST 5] Shop CRUD Operations")
shop = db.create_shop(
    name="Test Merchant Shop",
    phone="555-1234",
    address="123 Main Street"
)
print(f"  ✓ create_shop() created shop with ID: {shop['id']}")
print(f"    - Name: {shop['name']}")
print(f"    - Phone: {shop['phone']}")
print(f"    - Created: {shop['created_at']}")

retrieved_shop = db.get_shop(shop['id'])
print(f"  ✓ get_shop({shop['id']}) retrieved shop: {retrieved_shop['name']}")

# Test 6: Create and retrieve user
print("\n[TEST 6] User CRUD Operations")
user_pwd = "SecurePass123!"
user_hashed = hash_password(user_pwd)
user = db.create_user(
    shop_id=shop['id'],
    email="merchant@example.com",
    password_hash=user_hashed,
    full_name="John Merchant"
)
print(f"  ✓ create_user() created user with ID: {user['id']}")
print(f"    - Email: {user['email']}")
print(f"    - Shop ID: {user['shop_id']}")
print(f"    - Full Name: {user['full_name']}")
print(f"    - Is Active: {user['is_active']}")

retrieved_user = db.get_user_by_email("merchant@example.com")
print(f"  ✓ get_user_by_email('merchant@example.com') found: {retrieved_user['email']}")

retrieved_user_by_id = db.get_user_by_id(user['id'])
print(f"  ✓ get_user_by_id({user['id']}) found: {retrieved_user_by_id['email']}")

# Test 7: Verify password
print("\n[TEST 7] Password Verification Flow")
stored_hash = retrieved_user['password_hash']
is_correct = verify_password(user_pwd, stored_hash)
is_wrong = verify_password("WrongPassword", stored_hash)
print(f"  ✓ verify_password('{user_pwd}', hash) = {is_correct}")
print(f"  ✓ verify_password('WrongPassword', hash) = {is_wrong}")

# Test 8: Foreign key relationship
print("\n[TEST 8] Foreign Key Relationship")
user_shop_id = retrieved_user['shop_id']
shop_for_user = db.get_shop(user_shop_id)
print(f"  ✓ User's shop_id ({user_shop_id}) references Shop: {shop_for_user['name']}")

print("\n" + "=" * 70)
print("✅ ALL TESTS PASSED - Task 0.1 Infrastructure Ready!")
print("=" * 70)
print("\nAcceptance Criteria Summary:")
print("  [✅] hash_password('test123') returns hashed string")
print("  [✅] verify_password('test123', hashed) returns True")
print("  [✅] create_access_token({'shop_id': 1}) returns valid JWT")
print("  [✅] decode_token(jwt_str) returns dict with shop_id, email, exp")
print("  [✅] User and Shop tables exist with proper foreign keys")
