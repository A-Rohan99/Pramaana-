"""
Demo merchant fixture script.

Creates two demo merchants on startup:
1. demo@merchant.local / DemoPass123! → "Demo Merchant 1" (shop_id=1)
2. demo2@merchant.local / DemoPass456! → "Demo Merchant 2" (shop_id=2)

Script is idempotent — checks for existing email before creating.
"""

import logging
import db
from auth.password import hash_password

logger = logging.getLogger(__name__)


def setup_demo_merchants():
    """
    Create demo merchants if they don't already exist.
    Called from api.py startup event.
    """
    demo_accounts = [
        {
            "email": "demo@merchant.local",
            "password": "DemoPass123!",
            "shop_name": "Demo Merchant 1",
        },
        {
            "email": "demo2@merchant.local",
            "password": "DemoPass456!",
            "shop_name": "Demo Merchant 2",
        },
    ]
    
    created = []
    
    for account in demo_accounts:
        email = account["email"]
        password = account["password"]
        shop_name = account["shop_name"]
        
        # Check if email already exists
        existing_user = db.get_user_by_email(email)
        if existing_user:
            logger.info(f"Demo merchant {email} already exists (shop_id={existing_user['shop_id']})")
            continue
        
        # Create shop
        shop = db.create_shop(name=shop_name)
        shop_id = shop["id"]
        
        # Create user with hashed password
        password_hash = hash_password(password)
        user = db.create_user(
            shop_id=shop_id,
            email=email,
            password_hash=password_hash,
        )
        
        created.append(f"{email} (shop_id={shop_id})")
        logger.info(f"Created demo merchant: {email} (shop_id={shop_id})")
    
    if created:
        logger.info(f"Demo merchants created: {', '.join(created)}")
    else:
        logger.info("All demo merchants already exist")


if __name__ == "__main__":
    # Allow running this script standalone for setup
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    setup_demo_merchants()
