"""
Password hashing and verification using bcrypt.

Provides secure password storage with random salts.
Never store plaintext passwords — always hash on registration and verify on login.
"""

import bcrypt


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using bcrypt.
    
    Args:
        password: Plaintext password to hash
        
    Returns:
        Hashed password string (bcrypt format, including salt)
        
    Example:
        >>> hashed = hash_password("SecurePass123!")
        >>> len(hashed) > 0
        True
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    
    # Generate salt and hash in one operation
    # bcrypt.gensalt() with default rounds=12 provides strong security
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a bcrypt hash.
    
    Args:
        password: Plaintext password to check
        hashed: Previously hashed password (from hash_password or DB)
        
    Returns:
        True if password matches hash, False otherwise
        
    Example:
        >>> hashed = hash_password("SecurePass123!")
        >>> verify_password("SecurePass123!", hashed)
        True
        >>> verify_password("WrongPass", hashed)
        False
    """
    if not isinstance(password, str):
        raise TypeError("password must be a string")
    if not isinstance(hashed, str):
        raise TypeError("hashed must be a string")
    
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        # Invalid hash format or encoding issues
        return False
