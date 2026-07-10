"""
Database models for User and Shop tables.

These are the core entities for merchant authentication and multi-tenancy.
The User table stores merchant credentials (email, password_hash).
The Shop table stores merchant business details and is referenced by all data tables.
"""

from typing import Optional, Dict, Any
import datetime
from dataclasses import dataclass


@dataclass
class User:
    """
    Merchant user account.
    
    Attributes:
        id: Unique user ID (primary key)
        shop_id: Reference to the merchant's shop (foreign key)
        email: Unique email address
        password_hash: Bcrypt-hashed password (never store plaintext)
        full_name: User's display name (optional)
        is_active: Account status (default True)
        created_at: Account creation timestamp (ISO format)
        updated_at: Last modified timestamp (ISO format, optional)
    """
    id: int
    shop_id: int
    email: str
    password_hash: str
    full_name: Optional[str] = None
    is_active: bool = True
    created_at: str = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding password_hash for API responses."""
        return {
            "id": self.id,
            "shop_id": self.shop_id,
            "email": self.email,
            "full_name": self.full_name,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Shop:
    """
    Merchant shop / business entity.
    
    Multiple merchants can have shops, and each shop is isolated for data access.
    Shop ID is embedded in JWT tokens to enforce row-level security.
    
    Attributes:
        id: Unique shop ID (primary key)
        name: Business name
        phone: Contact phone (optional)
        address: Physical address (optional)
        created_at: Creation timestamp (ISO format)
        updated_at: Last modified timestamp (ISO format, optional)
    """
    id: int
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    created_at: str = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "address": self.address,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# Database schema (SQL) — define the structure for create statements
# These are called from db.py during init_db()

USERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    shop_id         INTEGER NOT NULL UNIQUE,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    is_active       BOOLEAN DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT,
    FOREIGN KEY (shop_id) REFERENCES shops(id)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_shop ON users(shop_id);
"""

SHOPS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS shops (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    phone       TEXT,
    address     TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT
);
"""
