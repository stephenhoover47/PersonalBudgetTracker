#!/usr/bin/env python3
"""
Test script for transaction syncing in sandbox environment

This script helps test the transaction sync functionality using Plaid's sandbox data.
It creates a test user, links a sandbox account, and runs a sync to verify everything works.

Usage:
    python scripts/test_sync_sandbox.py
"""

import os
import sys
import logging
from datetime import datetime

# Add the backend directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import get_db, engine, Base
from app.db.models import User, PlaidItem, Account, Transaction
from app.plaid_client import create_sandbox_public_token, get_access_token, sync_accounts
from app.services.plaid_service import sync_transactions

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_user(db):
    """Create a test user for sandbox testing"""
    from passlib.context import CryptContext
    
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Check if test user already exists
    test_user = db.query(User).filter(User.email == "test@example.com").first()
    if test_user:
        logger.info(f"Test user already exists: {test_user.full_name}")
        return test_user
    
    # Create new test user
    test_user = User(
        email="test@example.com",
        hashed_password=pwd_context.hash("testpassword123"),
        full_name="Sandbox Test User",
        is_active=True
    )
    
    db.add(test_user)
    db.commit()
    db.refresh(test_user)
    
    logger.info(f"Created test user: {test_user.full_name} (ID: {test_user.id})")
    return test_user

def link_sandbox_account(db, user):
    """Link a sandbox account for testing"""
    try:
        # Create sandbox public token
        logger.info("Creating sandbox public token...")
        public_token = create_sandbox_public_token()
        logger.info(f"Created sandbox public token: {public_token[:20]}...")
        
        # Exchange for access token
        logger.info("Exchanging public token for access token...")
        access_token = get_access_token(public_token)
        logger.info(f"Got access token: {access_token[:20]}...")
        
        # Create Plaid item
        plaid_item = PlaidItem(
            user_id=user.id,
            plaid_access_token=access_token,
            institution_id="ins_109508",  # First Platypus Bank
            institution_name="First Platypus Bank"
        )
        
        db.add(plaid_item)
        db.commit()
        db.refresh(plaid_item)
        
        logger.info(f"Created Plaid item: {plaid_item.id}")
        
        # Sync accounts to get account data
        logger.info("Syncing accounts...")
        accounts_data = sync_accounts(access_token)
        
        for account_data in accounts_data:
            account = Account(
                user_id=user.id,
                plaid_item_id=plaid_item.id,
                plaid_account_id=account_data.get("account_id"),
                name=account_data.get("name"),
                official_name=account_data.get("official_name"),
                account_type=account_data.get("type"),
                account_subtype=account_data.get("subtype"),
                mask=account_data.get("mask"),
                available_balance=account_data.get("balances", {}).get("available"),
                current_balance=account_data.get("balances", {}).get("current"),
                currency_code=account_data.get("balances", {}).get("iso_currency_code", "USD")
            )
            db.add(account)
        
        db.commit()
        logger.info(f"Synced {len(accounts_data)} accounts")
        
        return plaid_item
        
    except Exception as e:
        logger.error(f"Error linking sandbox account: {str(e)}")
        db.rollback()
        raise

def test_transaction_sync(db, plaid_item):
    """Test transaction syncing"""
    try:
        logger.info("Testing transaction sync...")
        
        # Run the sync
        sync_result = sync_transactions(db, plaid_item.plaid_access_token, plaid_item.user_id)
        
        logger.info(f"Sync result: {sync_result}")
        
        # Check what transactions were added
        transactions = db.query(Transaction).filter(
            Transaction.plaid_item_id == plaid_item.id
        ).all()
        
        logger.info(f"Total transactions in database: {len(transactions)}")
        
        # Show some sample transactions
        for i, tx in enumerate(transactions[:5]):  # Show first 5
            logger.info(f"Transaction {i+1}: {tx.name} - ${tx.amount} on {tx.date}")
        
        return sync_result
        
    except Exception as e:
        logger.error(f"Error testing transaction sync: {str(e)}")
        raise

def main():
    """Main test function"""
    logger.info("Starting sandbox sync test...")
    
    try:
        # Ensure database tables exist
        Base.metadata.create_all(bind=engine)
        
        # Get database session
        db = next(get_db())
        
        # Create test user
        user = create_test_user(db)
        
        # Check if user already has a linked account
        existing_item = db.query(PlaidItem).filter(PlaidItem.user_id == user.id).first()
        
        if existing_item:
            logger.info(f"User already has linked account (Item ID: {existing_item.id})")
            plaid_item = existing_item
        else:
            # Link sandbox account
            plaid_item = link_sandbox_account(db, user)
        
        # Test transaction sync
        sync_result = test_transaction_sync(db, plaid_item)
        
        # Summary
        logger.info("=" * 50)
        logger.info("SANDBOX TEST SUMMARY")
        logger.info("=" * 50)
        logger.info(f"User: {user.full_name} (ID: {user.id})")
        logger.info(f"Plaid Item: {plaid_item.id}")
        logger.info(f"Sync Status: {sync_result['status']}")
        logger.info(f"Transactions Added: {sync_result['added_count']}")
        logger.info(f"Transactions Modified: {sync_result['modified_count']}")
        logger.info(f"Transactions Removed: {sync_result['removed_count']}")
        
        if sync_result['added_count'] > 0:
            logger.info("✅ SUCCESS: Transactions were synced successfully!")
        else:
            logger.info("⚠️  WARNING: No new transactions were added (this might be normal for sandbox)")
        
        logger.info("=" * 50)
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 