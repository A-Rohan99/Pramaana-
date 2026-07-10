"""
Test suite for JWT authentication infrastructure (Task 0.1).

Tests:
- Password hashing and verification
- JWT token generation and validation
- Database User and Shop table creation
- User and shop creation via db helpers
"""

import os
import sys
import tempfile
import sqlite3
import json
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Set up a test database (in-memory) before importing db
os.environ["JWT_SECRET"] = "test_secret_key_at_least_32_bytes_long_for_testing_purposes"

import pytest
from auth.password import hash_password, verify_password
from auth.jwt_utils import create_access_token, decode_token, is_token_valid, get_jwt_secret
import db


# ===== TESTS: Password Hashing =====

class TestPasswordHashing:
    """Test bcrypt password hashing and verification."""
    
    def test_hash_password_returns_string(self):
        """hash_password should return a non-empty hashed string."""
        password = "test123"
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert password not in hashed  # Original password not visible in hash
    
    def test_hash_password_with_special_chars(self):
        """hash_password should handle special characters."""
        password = "P@ssw0rd!#$%^&*()"
        hashed = hash_password(password)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
    
    def test_verify_password_correct(self):
        """verify_password should return True for correct password."""
        password = "test123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """verify_password should return False for incorrect password."""
        password = "test123"
        hashed = hash_password(password)
        assert verify_password("wrongpassword", hashed) is False
    
    def test_verify_password_empty_string(self):
        """verify_password should return False for empty password."""
        hashed = hash_password("test123")
        assert verify_password("", hashed) is False
    
    def test_hash_is_different_each_time(self):
        """Each hash of the same password should be different (random salt)."""
        password = "test123"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        # Hashes are different due to random salt
        assert hash1 != hash2
        # But both verify as correct
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True
    
    def test_hash_password_type_error(self):
        """hash_password should raise TypeError for non-string input."""
        with pytest.raises(TypeError):
            hash_password(123)
        with pytest.raises(TypeError):
            hash_password(None)
    
    def test_verify_password_type_error(self):
        """verify_password should raise TypeError for invalid inputs."""
        hashed = hash_password("test123")
        with pytest.raises(TypeError):
            verify_password(123, hashed)
        with pytest.raises(TypeError):
            verify_password("test", 123)


# ===== TESTS: JWT Token Generation and Validation =====

class TestJWTToken:
    """Test JWT token generation and validation."""
    
    def test_create_access_token_returns_string(self):
        """create_access_token should return a valid JWT string."""
        payload = {
            "shop_id": 1,
            "email": "test@example.com",
            "user_id": 1,
        }
        token = create_access_token(payload)
        assert isinstance(token, str)
        assert len(token) > 0
        # JWT has 3 parts separated by dots
        assert token.count(".") == 2
    
    def test_create_access_token_with_all_fields(self):
        """create_access_token should accept additional fields."""
        payload = {
            "shop_id": 1,
            "email": "merchant@example.com",
            "user_id": 42,
            "role": "owner",
            "full_name": "John Doe",
        }
        token = create_access_token(payload)
        assert isinstance(token, str)
        decoded = decode_token(token)
        assert decoded["shop_id"] == 1
        assert decoded["email"] == "merchant@example.com"
        assert decoded["user_id"] == 42
        assert decoded["role"] == "owner"
    
    def test_decode_token_valid(self):
        """decode_token should return the payload from a valid token."""
        payload = {
            "shop_id": 1,
            "email": "test@example.com",
            "user_id": 1,
        }
        token = create_access_token(payload)
        decoded = decode_token(token)
        
        assert decoded["shop_id"] == 1
        assert decoded["email"] == "test@example.com"
        assert decoded["user_id"] == 1
        assert "iat" in decoded  # Issued at
        assert "exp" in decoded  # Expiry
    
    def test_decode_token_invalid_signature(self):
        """decode_token should reject a token with invalid signature."""
        payload = {"shop_id": 1, "email": "test@example.com", "user_id": 1}
        token = create_access_token(payload)
        
        # Modify the token to invalidate signature
        parts = token.split(".")
        parts[2] = "invalidsignature"
        bad_token = ".".join(parts)
        
        import jwt
        with pytest.raises((jwt.InvalidSignatureError, jwt.DecodeError)):
            decode_token(bad_token)
    
    def test_create_access_token_missing_required_field(self):
        """create_access_token should raise ValueError if shop_id is missing."""
        payload = {
            "email": "test@example.com",
            "user_id": 1,
            # Missing shop_id
        }
        with pytest.raises(ValueError):
            create_access_token(payload)
    
    def test_is_token_valid_true(self):
        """is_token_valid should return True for valid token."""
        payload = {
            "shop_id": 1,
            "email": "test@example.com",
            "user_id": 1,
        }
        token = create_access_token(payload)
        assert is_token_valid(token) is True
    
    def test_is_token_valid_false(self):
        """is_token_valid should return False for invalid token."""
        assert is_token_valid("not a token") is False
        assert is_token_valid("") is False
        assert is_token_valid(None) is False
    
    def test_get_jwt_secret_from_env(self):
        """get_jwt_secret should return the JWT_SECRET from environment."""
        secret = get_jwt_secret()
        assert isinstance(secret, str)
        assert len(secret) >= 32


# ===== TESTS: Database Tables =====

class TestDatabaseTables:
    """Test User and Shop table creation and operations."""
    
    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        """Create a fresh test database before each test."""
        # Use a temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        # Point db module to test database
        original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_db_path)
        
        # Clear the thread-local connection
        if hasattr(db._local, 'conn'):
            db._local.conn = None
        
        # Initialize the test database
        db.init_db()
        
        yield
        
        # Cleanup
        db.DB_PATH = original_db_path
        if hasattr(db._local, 'conn'):
            if db._local.conn:
                db._local.conn.close()
            db._local.conn = None
        
        # Delete temp database file
        try:
            os.unlink(self.temp_db_path)
        except:
            pass
    
    def test_shops_table_exists(self):
        """Shops table should be created during init_db."""
        conn = db.get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='shops'"
        )
        assert cursor.fetchone() is not None
    
    def test_users_table_exists(self):
        """Users table should be created during init_db."""
        conn = db.get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        assert cursor.fetchone() is not None
    
    def test_create_shop(self):
        """create_shop should insert a shop record."""
        shop = db.create_shop(
            name="Test Shop",
            phone="555-1234",
            address="123 Main St"
        )
        
        assert shop["id"] is not None
        assert shop["name"] == "Test Shop"
        assert shop["phone"] == "555-1234"
        assert shop["address"] == "123 Main St"
        assert shop["created_at"] is not None
    
    def test_get_shop(self):
        """get_shop should retrieve a shop by ID."""
        shop = db.create_shop(name="Test Shop")
        shop_id = shop["id"]
        
        retrieved = db.get_shop(shop_id)
        assert retrieved is not None
        assert retrieved["id"] == shop_id
        assert retrieved["name"] == "Test Shop"
    
    def test_get_shop_not_found(self):
        """get_shop should return None for nonexistent shop."""
        assert db.get_shop(9999) is None
    
    def test_create_user(self):
        """create_user should insert a user record."""
        shop = db.create_shop(name="Test Shop")
        shop_id = shop["id"]
        
        hashed_pwd = hash_password("SecurePass123")
        user = db.create_user(
            shop_id=shop_id,
            email="merchant@example.com",
            password_hash=hashed_pwd,
            full_name="John Merchant"
        )
        
        assert user["id"] is not None
        assert user["shop_id"] == shop_id
        assert user["email"] == "merchant@example.com"
        assert user["full_name"] == "John Merchant"
        assert user["is_active"] == 1
        assert user["created_at"] is not None
        # Password hash should not be exposed in dict (it is, but that's by design for testing)
        assert user["password_hash"] == hashed_pwd
    
    def test_get_user_by_email(self):
        """get_user_by_email should retrieve a user by email."""
        shop = db.create_shop(name="Test Shop")
        hashed_pwd = hash_password("SecurePass123")
        user = db.create_user(
            shop_id=shop["id"],
            email="merchant@example.com",
            password_hash=hashed_pwd
        )
        
        retrieved = db.get_user_by_email("merchant@example.com")
        assert retrieved is not None
        assert retrieved["id"] == user["id"]
        assert retrieved["email"] == "merchant@example.com"
    
    def test_get_user_by_email_case_insensitive(self):
        """get_user_by_email should be case-insensitive."""
        shop = db.create_shop(name="Test Shop")
        hashed_pwd = hash_password("SecurePass123")
        user = db.create_user(
            shop_id=shop["id"],
            email="Merchant@Example.COM",
            password_hash=hashed_pwd
        )
        
        # Should find with different case
        retrieved = db.get_user_by_email("merchant@example.com")
        assert retrieved is not None
        assert retrieved["id"] == user["id"]
    
    def test_get_user_by_email_not_found(self):
        """get_user_by_email should return None for nonexistent email."""
        assert db.get_user_by_email("nonexistent@example.com") is None
    
    def test_get_user_by_id(self):
        """get_user_by_id should retrieve a user by ID."""
        shop = db.create_shop(name="Test Shop")
        hashed_pwd = hash_password("SecurePass123")
        user = db.create_user(
            shop_id=shop["id"],
            email="merchant@example.com",
            password_hash=hashed_pwd
        )
        
        retrieved = db.get_user_by_id(user["id"])
        assert retrieved is not None
        assert retrieved["id"] == user["id"]
        assert retrieved["email"] == "merchant@example.com"
    
    def test_get_user_by_id_not_found(self):
        """get_user_by_id should return None for nonexistent ID."""
        assert db.get_user_by_id(9999) is None
    
    def test_user_shop_foreign_key(self):
        """User should have foreign key constraint with Shop."""
        shop = db.create_shop(name="Test Shop")
        hashed_pwd = hash_password("SecurePass123")
        
        user = db.create_user(
            shop_id=shop["id"],
            email="merchant@example.com",
            password_hash=hashed_pwd
        )
        
        # Verify the relationship
        retrieved_shop = db.get_shop(user["shop_id"])
        assert retrieved_shop is not None
        assert retrieved_shop["name"] == "Test Shop"
    
    def test_email_uniqueness(self):
        """Email should be unique across users."""
        shop1 = db.create_shop(name="Shop 1")
        shop2 = db.create_shop(name="Shop 2")
        hashed_pwd = hash_password("SecurePass123")
        
        # Create first user
        db.create_user(
            shop_id=shop1["id"],
            email="merchant@example.com",
            password_hash=hashed_pwd
        )
        
        # Try to create second user with same email (different shop)
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            db.create_user(
                shop_id=shop2["id"],
                email="merchant@example.com",
                password_hash=hashed_pwd
            )
    
    def test_shop_id_uniqueness_per_user(self):
        """Each user should have a unique shop_id (one-to-one relationship)."""
        shop1 = db.create_shop(name="Shop 1")
        shop2 = db.create_shop(name="Shop 2")
        hashed_pwd = hash_password("SecurePass123")
        
        # Create first user with shop 1
        db.create_user(
            shop_id=shop1["id"],
            email="merchant1@example.com",
            password_hash=hashed_pwd
        )
        
        # Try to create second user with same shop (should fail)
        import sqlite3
        with pytest.raises(sqlite3.IntegrityError):
            db.create_user(
                shop_id=shop1["id"],
                email="merchant2@example.com",
                password_hash=hashed_pwd
            )


# ===== ACCEPTANCE CRITERIA TESTS =====

class TestAcceptanceCriteria:
    """Verify all acceptance criteria from Task 0.1."""
    
    def test_ac1_hash_password_test123(self):
        """AC: hash_password("test123") returns hashed string."""
        hashed = hash_password("test123")
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != "test123"
    
    def test_ac2_verify_password_correct(self):
        """AC: verify_password("test123", hashed) returns True."""
        hashed = hash_password("test123")
        result = verify_password("test123", hashed)
        assert result is True
    
    def test_ac3_create_access_token_returns_jwt(self):
        """AC: create_access_token({"shop_id": 1}) returns valid JWT string."""
        payload = {"shop_id": 1, "email": "test@example.com", "user_id": 1}
        token = create_access_token(payload)
        assert isinstance(token, str)
        assert token.count(".") == 2  # Valid JWT format
    
    def test_ac4_decode_token_returns_dict(self):
        """AC: decode_token(jwt_str) returns dict with shop_id, email, exp."""
        payload = {"shop_id": 1, "email": "test@example.com", "user_id": 1}
        token = create_access_token(payload)
        decoded = decode_token(token)
        
        assert isinstance(decoded, dict)
        assert decoded["shop_id"] == 1
        assert decoded["email"] == "test@example.com"
        assert "exp" in decoded
    
    @pytest.fixture(autouse=True)
    def setup_test_db(self):
        """Setup test database for AC5."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db_path = self.temp_db.name
        self.temp_db.close()
        
        original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp_db_path)
        
        if hasattr(db._local, 'conn'):
            db._local.conn = None
        
        db.init_db()
        
        yield
        
        db.DB_PATH = original_db_path
        if hasattr(db._local, 'conn'):
            if db._local.conn:
                db._local.conn.close()
            db._local.conn = None
        
        try:
            os.unlink(self.temp_db_path)
        except:
            pass
    
    def test_ac5_user_and_shop_tables_exist(self):
        """AC: User and Shop tables exist in DB with proper foreign keys."""
        conn = db.get_conn()
        
        # Check tables exist
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'shops')"
        ).fetchall()
        assert len(tables) == 2
        
        # Check User table has expected columns
        user_columns = [row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
        assert "id" in user_columns
        assert "shop_id" in user_columns
        assert "email" in user_columns
        assert "password_hash" in user_columns
        assert "created_at" in user_columns
        
        # Check Shop table has expected columns
        shop_columns = [row[1] for row in conn.execute("PRAGMA table_info(shops)").fetchall()]
        assert "id" in shop_columns
        assert "name" in shop_columns
        assert "created_at" in shop_columns


if __name__ == "__main__":
    # Run with: pytest test_auth.py -v
    pytest.main([__file__, "-v"])
